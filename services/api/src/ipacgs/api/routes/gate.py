"""Gate Engine HTTP routes — Epic 6.

Role-based authorization is not wired in yet, same gap and same reason as
every other route module in this repo. Every route still requires a
valid authenticated identity.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ipacgs.api.schemas.gate import (
    CastVoteRequest,
    GateDecisionOut,
    GateOut,
    ReadinessPackOut,
    SuspendGateDecisionRequest,
)
from ipacgs.core.db import get_db
from ipacgs.core.security import CurrentUser, get_current_user
from ipacgs.models.gate import Gate, GateDecision
from ipacgs.models.project import Project
from ipacgs.services import gate_engine

router = APIRouter(tags=["gates"])

_DECISION_LOAD_OPTIONS = (
    selectinload(GateDecision.votes),
    selectinload(GateDecision.certificate),
)


async def _get_project_or_404(session: AsyncSession, project_id: uuid.UUID) -> Project:
    project = await session.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No project {project_id}.")
    return project


async def _get_gate_or_404(session: AsyncSession, gate_id: uuid.UUID) -> Gate:
    gate = await session.get(Gate, gate_id)
    if gate is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No gate {gate_id}.")
    return gate


async def _get_decision_or_404(session: AsyncSession, decision_id: uuid.UUID) -> GateDecision:
    # select().options(), not session.get(..., options=...): `decision` is
    # always already in the session's identity map by the time this runs
    # (every caller acted on it earlier in the same request), and get()
    # can return that cached instance without actually applying eager-load
    # options when no fresh query turns out to be needed.
    #
    # populate_existing=True on top of that: the *first* call to this
    # function in a route (before acting on the decision) already loads
    # `votes`/`certificate` — correctly empty at that point. cast_vote
    # adds a GateVote via its raw gate_decision_id FK, not through the
    # `.decision` relationship attribute, so SQLAlchemy's normal
    # collection-sync-on-relationship-assignment never fires, and the
    # already-loaded `votes` collection on this identity-mapped instance
    # stays stale. A second select() with the same options still won't
    # overwrite an already-populated collection by default — that's what
    # populate_existing actually forces, not just "run a fresh query".
    result = await session.execute(
        select(GateDecision)
        .options(*_DECISION_LOAD_OPTIONS)
        .where(GateDecision.id == decision_id)
        .execution_options(populate_existing=True)
    )
    decision = result.scalars().first()
    if decision is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No gate decision {decision_id}.")
    return decision


@router.get("/gates", response_model=list[GateOut])
async def list_gates(db: AsyncSession = Depends(get_db)) -> list[Gate]:
    result = await db.execute(select(Gate).order_by(Gate.sequence))
    return list(result.scalars().all())


@router.post(
    "/projects/{project_id}/gates/{gate_id}/open",
    response_model=GateDecisionOut,
    status_code=status.HTTP_201_CREATED,
)
async def open_gate_decision_route(
    project_id: uuid.UUID,
    gate_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> GateDecision:
    project = await _get_project_or_404(db, project_id)
    gate = await _get_gate_or_404(db, gate_id)

    try:
        decision = await gate_engine.open_gate_decision(db, project, gate, actor=user.object_id)
    except gate_engine.IllegalGateDecision as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc

    await db.commit()
    return await _get_decision_or_404(db, decision.id)


@router.get(
    "/projects/{project_id}/gates/{gate_id}/readiness-pack", response_model=ReadinessPackOut
)
async def readiness_pack_route(
    project_id: uuid.UUID, gate_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> ReadinessPackOut:
    project = await _get_project_or_404(db, project_id)
    gate = await _get_gate_or_404(db, gate_id)
    pack = await gate_engine.assemble_readiness_pack(db, project, gate)
    return ReadinessPackOut(
        project_id=pack.project_id,
        gate_code=pack.gate_code,
        rag_status=pack.rag_status,
        open_finding_count=pack.open_finding_count,
    )


@router.get("/gate-decisions/{decision_id}", response_model=GateDecisionOut)
async def get_gate_decision(
    decision_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> GateDecision:
    return await _get_decision_or_404(db, decision_id)


@router.post("/gate-decisions/{decision_id}/vote", response_model=GateDecisionOut)
async def cast_vote_route(
    decision_id: uuid.UUID,
    body: CastVoteRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> GateDecision:
    decision = await _get_decision_or_404(db, decision_id)
    project = await _get_project_or_404(db, decision.project_id)

    try:
        await gate_engine.cast_vote(
            db, decision, project, voter=user.object_id, outcome=body.outcome, notes=body.notes
        )
    except gate_engine.IllegalGateDecision as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc

    await db.commit()
    return await _get_decision_or_404(db, decision_id)


@router.post("/gate-decisions/{decision_id}/suspend", response_model=GateDecisionOut)
async def suspend_gate_decision_route(
    decision_id: uuid.UUID,
    body: SuspendGateDecisionRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> GateDecision:
    decision = await _get_decision_or_404(db, decision_id)

    try:
        await gate_engine.suspend_gate_decision(
            db, decision, actor=user.object_id, reason=body.reason
        )
    except gate_engine.IllegalGateDecision as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc

    await db.commit()
    return await _get_decision_or_404(db, decision_id)


@router.get("/projects/{project_id}/blocking-gate", response_model=GateOut | None)
async def blocking_gate_route(
    project_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> Gate | None:
    """Diagnostic route: null if nothing's blocking, otherwise the Gate
    a project can't get past yet. A small piece of what Epic 7's Command
    Centre will eventually surface properly — useful on its own before
    that exists."""
    project = await _get_project_or_404(db, project_id)
    return await gate_engine.gate_blocking_advancement(db, project, project.current_stage_id)
