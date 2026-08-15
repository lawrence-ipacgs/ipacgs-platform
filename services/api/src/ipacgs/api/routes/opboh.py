"""OPBOH HTTP routes.

Role-based authorization (`require_roles(...)`) is deliberately not wired in
yet — the Entra ID app roles it would check against don't exist until
`infra/scripts/create-app-registrations.sh` is actually run (still a
pending manual step from Epic 0). Every route below still requires a valid
authenticated identity (`get_current_user`) so segregation-of-duties has a
real actor to check against; it just doesn't yet restrict *which*
authenticated users may call which route. Tightening that is a follow-up,
not an oversight — tracked here rather than silently deferred.
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ipacgs.api.schemas.opboh import (
    AssessmentOut,
    AssignFindingRequest,
    CreateAssessmentRequest,
    CriticalFailureOut,
    DecideRequest,
    DomainResultOut,
    FindingOut,
    ResponseOut,
    ScoreOut,
    UpsertResponseRequest,
)
from ipacgs.core.db import get_db
from ipacgs.core.security import CurrentUser, get_current_user
from ipacgs.models.opboh import (
    OpbohAssessment,
    OpbohAssessmentStatus,
    OpbohFinding,
    OpbohFrameworkVersion,
    OpbohResponse,
    OpbohResponseEvidence,
)
from ipacgs.models.organisation import Organisation
from ipacgs.models.project import Project
from ipacgs.services import opboh_findings, opboh_workflow
from ipacgs.services.opboh_query import compute_assessment_score
from ipacgs.services.opboh_scoring import AssessmentResult

router = APIRouter(prefix="/opboh", tags=["opboh"])

_DECIDED_STATES = frozenset(
    {
        OpbohAssessmentStatus.ACCEPTED,
        OpbohAssessmentStatus.REJECTED,
        OpbohAssessmentStatus.SUPERSEDED,
    }
)


async def _get_assessment_or_404(
    session: AsyncSession, assessment_id: uuid.UUID
) -> OpbohAssessment:
    assessment = await session.get(OpbohAssessment, assessment_id)
    if assessment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No OPBOH assessment {assessment_id}.")
    return assessment


def _score_to_schema(result: AssessmentResult) -> ScoreOut:
    return ScoreOut(
        overall_score=result.overall_score,
        is_clean=result.is_clean,
        has_critical_failure=result.has_critical_failure,
        domain_results=[
            DomainResultOut(
                domain_id=dr.domain_id,
                name=dr.name,
                score=dr.score,
                meets_threshold=dr.meets_threshold,
                critical_failures=[
                    CriticalFailureOut(
                        question_id=f.question_id,
                        control_objective=f.control_objective,
                        reason=f.reason,
                    )
                    for f in dr.critical_failures
                ],
                unanswered_count=dr.unanswered_count,
            )
            for dr in result.domain_results
        ],
    )


@router.post("/assessments", response_model=AssessmentOut, status_code=status.HTTP_201_CREATED)
async def create_assessment(
    body: CreateAssessmentRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> OpbohAssessment:
    organisation = await db.get(Organisation, body.organisation_id)
    if organisation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No organisation {body.organisation_id}.")

    if body.project_id is not None:
        project = await db.get(Project, body.project_id)
        if project is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"No project {body.project_id}.")
        if project.organisation_id != organisation.id:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"Project {body.project_id} belongs to a different organisation "
                f"than {body.organisation_id}.",
            )

    framework_version_id = body.framework_version_id
    if framework_version_id is None:
        # ORDER BY, deliberately — a bare LIMIT 1 with no tiebreaker is
        # nondeterministic the moment more than one row has is_active=True
        # (which nothing currently prevents — unlike the generic Framework
        # Registry, OpbohFrameworkVersion never got an "activating one
        # deactivates the others" rule). Picking arbitrarily which
        # "active" catalogue version an assessment lands on is wrong for
        # a governance platform regardless of whether tests catch it —
        # this makes the choice deterministic (most recently effective
        # wins) rather than leaving it to however Postgres happens to
        # scan the table today.
        active = await db.execute(
            select(OpbohFrameworkVersion)
            .where(OpbohFrameworkVersion.is_active.is_(True))
            .order_by(OpbohFrameworkVersion.effective_from.desc())
            .limit(1)
        )
        version = active.scalars().first()
        if version is None:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "No active OPBOH framework version — none has been loaded yet.",
            )
        framework_version_id = version.id

    assessment = OpbohAssessment(
        id=uuid.uuid4(),
        tenant_id=organisation.tenant_id,
        framework_version_id=framework_version_id,
        organisation_id=organisation.id,
        project_id=body.project_id,
        status=OpbohAssessmentStatus.DRAFT,
        prepared_by=user.object_id,
        has_critical_failure=False,
        created_by=user.object_id,
        updated_by=user.object_id,
    )
    db.add(assessment)
    await db.commit()
    await db.refresh(assessment)
    return assessment


@router.get("/assessments/{assessment_id}", response_model=AssessmentOut)
async def get_assessment(
    assessment_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> OpbohAssessment:
    return await _get_assessment_or_404(db, assessment_id)


@router.get("/assessments/{assessment_id}/score", response_model=ScoreOut)
async def get_assessment_score(
    assessment_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> ScoreOut:
    assessment = await _get_assessment_or_404(db, assessment_id)
    result = await compute_assessment_score(db, assessment)
    return _score_to_schema(result)


@router.post("/assessments/{assessment_id}/responses", response_model=ResponseOut)
async def upsert_response(
    assessment_id: uuid.UUID,
    body: UpsertResponseRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> OpbohResponse:
    assessment = await _get_assessment_or_404(db, assessment_id)
    if assessment.status in _DECIDED_STATES:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Assessment {assessment_id} is {assessment.status.value} — "
            "reopen it before changing responses.",
        )

    existing = await db.execute(
        select(OpbohResponse).where(
            OpbohResponse.assessment_id == assessment_id,
            OpbohResponse.question_id == body.question_id,
        )
    )
    response = existing.scalars().first()
    now = datetime.now(UTC)
    if response is None:
        response = OpbohResponse(
            id=uuid.uuid4(),
            assessment_id=assessment_id,
            question_id=body.question_id,
            created_by=user.object_id,
            updated_by=user.object_id,
        )
        db.add(response)

    response.score = body.score
    response.evidence_sufficient = body.evidence_sufficient
    response.notes = body.notes
    response.answered_by = user.object_id
    response.answered_at = now
    response.updated_by = user.object_id
    await db.flush()

    existing_links = await db.execute(
        select(OpbohResponseEvidence.evidence_document_id).where(
            OpbohResponseEvidence.response_id == response.id
        )
    )
    already_linked = {row[0] for row in existing_links.all()}
    for evidence_id in body.evidence_document_ids:
        if evidence_id not in already_linked:
            db.add(
                OpbohResponseEvidence(
                    id=uuid.uuid4(), response_id=response.id, evidence_document_id=evidence_id
                )
            )

    await db.commit()
    await db.refresh(response)
    return response


@router.post("/assessments/{assessment_id}/submit", response_model=AssessmentOut)
async def submit_assessment(
    assessment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> OpbohAssessment:
    assessment = await _get_assessment_or_404(db, assessment_id)
    await opboh_workflow.simple_transition(
        db,
        assessment,
        target=OpbohAssessmentStatus.SUBMITTED,
        actor=user.object_id,
        correlation_id=uuid.uuid4(),
    )
    await db.commit()
    await db.refresh(assessment)
    return assessment


@router.post("/assessments/{assessment_id}/begin-assessment", response_model=AssessmentOut)
async def begin_assessment_route(
    assessment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> OpbohAssessment:
    assessment = await _get_assessment_or_404(db, assessment_id)
    await opboh_workflow.begin_assessment(
        db, assessment, actor=user.object_id, correlation_id=uuid.uuid4()
    )
    await db.commit()
    await db.refresh(assessment)
    return assessment


@router.post("/assessments/{assessment_id}/independently-review", response_model=AssessmentOut)
async def independently_review_route(
    assessment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> OpbohAssessment:
    assessment = await _get_assessment_or_404(db, assessment_id)
    await opboh_workflow.independently_review(
        db, assessment, actor=user.object_id, correlation_id=uuid.uuid4()
    )
    await db.commit()
    await db.refresh(assessment)
    return assessment


@router.post("/assessments/{assessment_id}/decide", response_model=AssessmentOut)
async def decide_route(
    assessment_id: uuid.UUID,
    body: DecideRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> OpbohAssessment:
    """Computes the score fresh at decision time — never trusts a
    client-supplied score — then hands it to the workflow layer, which is
    where FW-OPBOH-015's fatal-flaw block actually lives."""
    assessment = await _get_assessment_or_404(db, assessment_id)
    result = await compute_assessment_score(db, assessment)

    await opboh_workflow.decide(
        db,
        assessment,
        decision=OpbohAssessmentStatus(body.decision),
        actor=user.object_id,
        has_critical_failure=result.has_critical_failure,
        overall_score=result.overall_score,
        decision_summary=body.decision_summary,
        correlation_id=uuid.uuid4(),
    )
    await db.commit()
    await db.refresh(assessment)
    return assessment


@router.get("/assessments/{assessment_id}/findings", response_model=list[FindingOut])
async def list_findings(
    assessment_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> list[OpbohFinding]:
    await _get_assessment_or_404(db, assessment_id)
    result = await db.execute(
        select(OpbohFinding).where(OpbohFinding.assessment_id == assessment_id)
    )
    return list(result.scalars().all())


async def _get_finding_or_404(session: AsyncSession, finding_id: uuid.UUID) -> OpbohFinding:
    finding = await session.get(OpbohFinding, finding_id)
    if finding is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No OPBOH finding {finding_id}.")
    return finding


@router.post("/findings/{finding_id}/assign", response_model=FindingOut)
async def assign_finding(
    finding_id: uuid.UUID,
    body: AssignFindingRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> OpbohFinding:
    finding = await _get_finding_or_404(db, finding_id)
    await opboh_findings.assign_owner(
        db,
        finding,
        owner=body.owner,
        due_date=body.due_date,
        actor=user.object_id,
        correlation_id=uuid.uuid4(),
    )
    await db.commit()
    await db.refresh(finding)
    return finding


@router.post("/findings/{finding_id}/close", response_model=FindingOut)
async def close_finding_route(
    finding_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> OpbohFinding:
    finding = await _get_finding_or_404(db, finding_id)
    await opboh_findings.close_finding(
        db, finding, actor=user.object_id, correlation_id=uuid.uuid4()
    )
    await db.commit()
    await db.refresh(finding)
    return finding


@router.post("/findings/{finding_id}/escalate", response_model=FindingOut)
async def escalate_finding_route(
    finding_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> OpbohFinding:
    finding = await _get_finding_or_404(db, finding_id)
    await opboh_findings.escalate_finding(
        db, finding, actor=user.object_id, correlation_id=uuid.uuid4()
    )
    await db.commit()
    await db.refresh(finding)
    return finding
