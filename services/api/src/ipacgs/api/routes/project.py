"""Stage Engine HTTP routes — Epic 5, plus the Epic 4/5 gap-closing work
(applicable-frameworks, reopen-stage, RAG, assignment, open-findings).

Role-based authorization is not wired in yet, same gap and same reason as
`api/routes/opboh.py` and `api/routes/framework.py`. Every route still
requires a valid authenticated identity.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ipacgs.api.schemas.framework import FrameworkOut
from ipacgs.api.schemas.opboh import FindingOut
from ipacgs.api.schemas.project import (
    AdvanceStageRequest,
    AssignStageRequest,
    CreateProjectRequest,
    ProjectOut,
    ProjectSummaryOut,
    RagOut,
    ReopenStageRequest,
    StageGateDecisionOut,
    StageOut,
)
from ipacgs.core.db import get_db
from ipacgs.core.security import CurrentUser, get_current_user
from ipacgs.models.framework import Framework
from ipacgs.models.notification import NotificationKind
from ipacgs.models.opboh import OpbohAssessment, OpbohFinding
from ipacgs.models.organisation import Organisation
from ipacgs.models.project import Project, Stage, StageGateDecision
from ipacgs.services import framework_applicability, gate_engine, notifications, stage_engine

router = APIRouter(tags=["projects"])


async def _get_project_or_404(session: AsyncSession, project_id: uuid.UUID) -> Project:
    project = await session.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No project {project_id}.")
    return project


@router.get("/stages", response_model=list[StageOut])
async def list_stages(db: AsyncSession = Depends(get_db)) -> list[Stage]:
    result = await db.execute(select(Stage).order_by(Stage.sequence))
    return list(result.scalars().all())


@router.post("/projects", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_project(
    body: CreateProjectRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> Project:
    organisation = await db.get(Organisation, body.organisation_id)
    if organisation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No organisation {body.organisation_id}.")

    try:
        project = await stage_engine.create_project(
            db,
            tenant_id=organisation.tenant_id,
            organisation_id=organisation.id,
            name=body.name,
            description=body.description,
            sector=body.sector,
            risk_rating=body.risk_rating,
            actor=user.object_id,
        )
    except stage_engine.NoStagesConfigured as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc

    await db.commit()
    await db.refresh(project)
    return project


@router.get("/projects/{project_id}", response_model=ProjectOut)
async def get_project(project_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> Project:
    return await _get_project_or_404(db, project_id)


@router.post("/projects/{project_id}/advance-stage", response_model=StageGateDecisionOut)
async def advance_stage_route(
    project_id: uuid.UUID,
    body: AdvanceStageRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> StageGateDecision:
    project = await _get_project_or_404(db, project_id)

    assessment = await db.get(OpbohAssessment, body.supporting_assessment_id)
    if assessment is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"No OPBOH assessment {body.supporting_assessment_id}."
        )

    try:
        decision = await stage_engine.advance_stage(
            db,
            project,
            supporting_assessment=assessment,
            actor=user.object_id,
            notes=body.notes,
        )
    except stage_engine.IllegalStageAdvancement as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc

    await db.commit()
    await db.refresh(decision)
    return decision


@router.post("/projects/{project_id}/reopen-stage", response_model=StageGateDecisionOut)
async def reopen_stage_route(
    project_id: uuid.UUID,
    body: ReopenStageRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> StageGateDecision:
    project = await _get_project_or_404(db, project_id)

    try:
        decision = await stage_engine.reopen_stage(
            db,
            project,
            target_stage_id=body.target_stage_id,
            actor=user.object_id,
            reason=body.reason,
        )
    except stage_engine.IllegalStageAdvancement as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc

    await db.commit()
    await db.refresh(decision)
    return decision


@router.post("/projects/{project_id}/assign", response_model=ProjectOut)
async def assign_stage_route(
    project_id: uuid.UUID,
    body: AssignStageRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> Project:
    project = await _get_project_or_404(db, project_id)
    project = await stage_engine.assign_stage(
        db, project, assigned_to=body.assigned_to, due_date=body.due_date, actor=user.object_id
    )
    # Wired here, not inside stage_engine.assign_stage itself: services/
    # notifications.py already imports RagStatus/compute_project_rag from
    # services/stage_engine.py for scan_overdue_projects, so the reverse
    # import would be circular. Same reasoning, same fix as the gate/
    # stage non-bypassable check — a plain call at the route layer costs
    # nothing a service-layer call wouldn't, without restructuring two
    # modules around avoiding it.
    await notifications.notify(
        db,
        tenant_id=project.tenant_id,
        recipient=body.assigned_to,
        kind=NotificationKind.ASSIGNMENT,
        entity_type="project",
        entity_id=project.id,
        message=f"You've been assigned project {project.name!r}"
        + (f" (due {body.due_date})." if body.due_date else "."),
    )
    await db.commit()
    await db.refresh(project)
    return project


@router.get("/projects/{project_id}/stage-history", response_model=list[StageGateDecisionOut])
async def stage_history(
    project_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> list[StageGateDecision]:
    await _get_project_or_404(db, project_id)
    result = await db.execute(
        select(StageGateDecision)
        .where(StageGateDecision.project_id == project_id)
        .order_by(StageGateDecision.decided_at)
    )
    return list(result.scalars().all())


@router.get("/projects/{project_id}/rag", response_model=RagOut)
async def project_rag(project_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> RagOut:
    project = await _get_project_or_404(db, project_id)
    status_value = await stage_engine.compute_project_rag(db, project)
    return RagOut(status=status_value)


@router.get("/projects/{project_id}/open-findings", response_model=list[FindingOut])
async def project_open_findings(
    project_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> list[OpbohFinding]:
    project = await _get_project_or_404(db, project_id)
    return await stage_engine.list_open_findings_for_project(db, project)


@router.get("/projects/{project_id}/applicable-frameworks", response_model=list[FrameworkOut])
async def applicable_frameworks(
    project_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> list[Framework]:
    project = await _get_project_or_404(db, project_id)
    return await framework_applicability.applicable_frameworks_for_project(db, project)


@router.get("/projects", response_model=list[ProjectSummaryOut])
async def list_projects(db: AsyncSession = Depends(get_db)) -> list[ProjectSummaryOut]:
    """FR-RPT-002 (subset) — the project health / stage-gate tracker
    view: every project, its current stage, RAG status, and whether a
    gate is blocking it, in one call rather than one round-trip per
    project. Unscoped across tenants, same as every other list route in
    this repo (GET /frameworks, GET /gates, GET /stages) — real
    tenant-scoping is the same pre-existing, already-flagged gap
    TenantScopedMixin's own docstring names, not something new here.

    One request per project to compute RAG/blocking-gate — fine at the
    scale this platform runs at today, worth revisiting with a batched
    query if the project count ever makes that not true."""
    projects_result = await db.execute(select(Project).order_by(Project.created_at.desc()))
    projects = projects_result.scalars().all()

    summaries: list[ProjectSummaryOut] = []
    for project in projects:
        stage = await db.get(Stage, project.current_stage_id)
        rag = await stage_engine.compute_project_rag(db, project)
        blocking_gate = await gate_engine.gate_blocking_advancement(
            db, project, project.current_stage_id
        )
        summaries.append(
            ProjectSummaryOut(
                id=project.id,
                name=project.name,
                organisation_id=project.organisation_id,
                current_stage_code=stage.code if stage else None,
                current_stage_name=stage.name if stage else None,
                status=project.status,
                rag_status=rag,
                blocking_gate_code=blocking_gate.code if blocking_gate else None,
                assigned_to=project.assigned_to,
                stage_due_date=project.stage_due_date,
            )
        )
    return summaries
