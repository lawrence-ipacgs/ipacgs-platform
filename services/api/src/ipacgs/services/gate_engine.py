"""Epic 6 — Gate Engine service layer.

`cast_vote` is where GATE-0[0-1]-004's authority/quorum/conflict rule and
GATE-0[0-1]-005's decision-scope rule actually live — same pattern as
every other domain rule in this codebase (FW-OPBOH-015's fatal-flaw block
in opboh_workflow.decide, PRN-001 in stage_engine.advance_stage): the rule
is a function precondition, not a schema constraint.

One deliberate asymmetry, worth stating plainly: a single HOLD vote
finalizes the decision to HOLD immediately, regardless of quorum or how
many PROCEED votes already exist — but PROCEED only finalizes once
`required_quorum` distinct PROCEED votes are in. This mirrors the "no
averaging concealment" principle FW-OPBOH-015 already established for
OPBOH scoring: one real objection should be able to stop something, but
moving forward needs actual consensus, not just an absence of objection
so far.
"""

import hashlib
import json
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ipacgs.models.gate import (
    Gate,
    GateCertificate,
    GateDecision,
    GateDecisionStatus,
    GateVote,
    GateVoteOutcome,
)
from ipacgs.models.opboh import OpbohAssessment
from ipacgs.models.project import Project
from ipacgs.services.stage_engine import (
    RagStatus,
    compute_project_rag,
    list_open_findings_for_project,
)

_OPEN_DECISION_STATES = frozenset({GateDecisionStatus.PENDING})


class GateEngineError(Exception):
    """Base class for this module's domain exceptions."""


class IllegalGateDecision(GateEngineError):
    """Raised when open_gate_decision, cast_vote or suspend_gate_decision's
    preconditions aren't met."""


class ReadinessPack:
    """GATE-0[0-1]-002 — "automatic readiness-pack assembly". Computed,
    not stored, same reasoning as RagStatus: assembled fresh from data
    that's already real (the project's current RAG status and open
    findings), not a second copy of it that could go stale."""

    def __init__(
        self,
        *,
        project_id: uuid.UUID,
        gate_code: str,
        rag_status: RagStatus,
        open_finding_count: int,
    ) -> None:
        self.project_id = project_id
        self.gate_code = gate_code
        self.rag_status = rag_status
        self.open_finding_count = open_finding_count


async def assemble_readiness_pack(
    session: AsyncSession, project: Project, gate: Gate
) -> ReadinessPack:
    rag_status = await compute_project_rag(session, project)
    findings = await list_open_findings_for_project(session, project)
    return ReadinessPack(
        project_id=project.id,
        gate_code=gate.code,
        rag_status=rag_status,
        open_finding_count=len(findings),
    )


async def _latest_decision(
    session: AsyncSession, project: Project, gate: Gate
) -> GateDecision | None:
    result = await session.execute(
        select(GateDecision)
        .where(GateDecision.project_id == project.id, GateDecision.gate_id == gate.id)
        .order_by(GateDecision.created_at.desc())
        .limit(1)
    )
    return result.scalars().first()


async def open_gate_decision(
    session: AsyncSession, project: Project, gate: Gate, *, actor: str
) -> GateDecision:
    if not gate.is_active:
        raise IllegalGateDecision(f"Gate {gate.code} is not active.")
    if project.current_stage_id != gate.trigger_stage_id:
        raise IllegalGateDecision(
            f"Project {project.id} is not at gate {gate.code}'s trigger stage — "
            "nothing to open a decision against yet."
        )

    existing = await _latest_decision(session, project, gate)
    if existing is not None and existing.status in _OPEN_DECISION_STATES:
        raise IllegalGateDecision(
            f"Gate {gate.code} already has an open decision for project {project.id} "
            "— vote on it rather than opening a new one."
        )
    if existing is not None and existing.status == GateDecisionStatus.PROCEED:
        raise IllegalGateDecision(
            f"Gate {gate.code} already proceeded for project {project.id} — "
            "suspend the existing decision before opening a new one."
        )

    decision = GateDecision(
        id=uuid.uuid4(),
        tenant_id=project.tenant_id,
        project_id=project.id,
        gate_id=gate.id,
        status=GateDecisionStatus.PENDING,
        opened_by=actor,
        created_by=actor,
        updated_by=actor,
    )
    session.add(decision)
    await session.flush()
    return decision


async def _conflicted_voter(session: AsyncSession, project: Project, voter: str) -> bool:
    """SOD, extended to gates: whoever prepared the project's most recent
    linked assessment can't also be the one voting it through a gate."""
    result = await session.execute(
        select(OpbohAssessment)
        .where(OpbohAssessment.project_id == project.id)
        .order_by(OpbohAssessment.created_at.desc())
        .limit(1)
    )
    assessment = result.scalars().first()
    return assessment is not None and assessment.prepared_by == voter


async def cast_vote(
    session: AsyncSession,
    decision: GateDecision,
    project: Project,
    *,
    voter: str,
    outcome: GateVoteOutcome,
    notes: str | None = None,
) -> GateVote:
    if decision.status != GateDecisionStatus.PENDING:
        raise IllegalGateDecision(
            f"Decision {decision.id} is {decision.status.value} — no further votes accepted."
        )
    if await _conflicted_voter(session, project, voter):
        raise IllegalGateDecision(
            f"{voter} prepared the assessment behind this decision and cannot also vote on it."
        )

    existing_vote = await session.execute(
        select(GateVote).where(GateVote.gate_decision_id == decision.id, GateVote.voter == voter)
    )
    if existing_vote.scalars().first() is not None:
        raise IllegalGateDecision(f"{voter} has already voted on decision {decision.id}.")

    vote = GateVote(
        id=uuid.uuid4(),
        gate_decision_id=decision.id,
        voter=voter,
        outcome=outcome,
        voted_at=datetime.now(UTC),
        notes=notes,
    )
    session.add(vote)
    await session.flush()

    if outcome == GateVoteOutcome.HOLD:
        decision.status = GateDecisionStatus.HOLD
        decision.decided_at = datetime.now(UTC)
        decision.updated_by = voter
        await session.flush()
        return vote

    gate = await session.get(Gate, decision.gate_id)
    assert gate is not None  # the gate a decision was opened against can't vanish
    proceed_votes = await session.execute(
        select(GateVote).where(
            GateVote.gate_decision_id == decision.id,
            GateVote.outcome == GateVoteOutcome.PROCEED,
        )
    )
    proceed_count = len(proceed_votes.scalars().all())
    if proceed_count >= gate.required_quorum:
        decision.status = GateDecisionStatus.PROCEED
        decision.decided_at = datetime.now(UTC)
        decision.updated_by = voter
        await session.flush()
        await _issue_certificate(session, decision)

    return vote


async def _issue_certificate(session: AsyncSession, decision: GateDecision) -> GateCertificate:
    votes_result = await session.execute(
        select(GateVote).where(GateVote.gate_decision_id == decision.id).order_by(GateVote.voter)
    )
    votes = votes_result.scalars().all()

    canonical = {
        "decision_id": str(decision.id),
        "project_id": str(decision.project_id),
        "gate_id": str(decision.gate_id),
        "status": decision.status.value,
        "decided_at": decision.decided_at.isoformat() if decision.decided_at else None,
        "votes": [
            {"voter": v.voter, "outcome": v.outcome.value, "voted_at": v.voted_at.isoformat()}
            for v in votes
        ],
    }
    content_hash = hashlib.sha256(json.dumps(canonical, sort_keys=True).encode("utf-8")).hexdigest()

    certificate = GateCertificate(
        id=uuid.uuid4(),
        gate_decision_id=decision.id,
        content_hash=content_hash,
        issued_at=datetime.now(UTC),
    )
    session.add(certificate)
    await session.flush()
    return certificate


async def suspend_gate_decision(
    session: AsyncSession, decision: GateDecision, *, actor: str, reason: str
) -> GateDecision:
    if not reason.strip():
        raise IllegalGateDecision("Suspending a gate decision requires a reason.")
    if decision.status != GateDecisionStatus.PROCEED:
        raise IllegalGateDecision(
            f"Decision {decision.id} is {decision.status.value}, not proceed — nothing to suspend."
        )

    decision.status = GateDecisionStatus.SUSPENDED
    decision.suspended_at = datetime.now(UTC)
    decision.suspended_by = actor
    decision.suspension_reason = reason
    decision.updated_by = actor
    await session.flush()
    return decision


async def gate_blocking_advancement(
    session: AsyncSession, project: Project, stage_id: uuid.UUID
) -> Gate | None:
    """Used by stage_engine.advance_stage to enforce GATE-0[0-1]-006 —
    an exact-match lookup on `stage_id`, not an ambient scan (see
    models/gate.py's module docstring for why that distinction matters
    in this repo). Returns the Gate itself, so the caller can report
    which one is blocking — None means either no gate is configured at
    this stage, or it already has a PROCEED decision and isn't blocking
    anything."""
    gate_result = await session.execute(
        select(Gate).where(Gate.is_active.is_(True), Gate.trigger_stage_id == stage_id)
    )
    gate = gate_result.scalars().first()
    if gate is None:
        return None

    decision = await _latest_decision(session, project, gate)
    if decision is not None and decision.status == GateDecisionStatus.PROCEED:
        return None
    return gate
