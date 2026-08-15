"""Epic 5 — Stage Engine service layer.

`advance_stage` is where PRN-001 ("date alone never authorizes
progression") actually gets enforced — mirrors how FW-OPBOH-015's
fatal-flaw block lives in `opboh_workflow.decide`, not in the schema: the
rule is a function precondition, not just a column that happens to exist.

Known mismatch, surfaced when `scripts/seed_stages.py` swapped its
illustrative sequence for UACOC's real Phase 1 (Intake & Screening)
stages: `advance_stage` requires an *accepted OPBOH assessment* to leave
ANY stage, unconditionally. That's the right rule for a compliance
checkpoint, but UACOC's own process-map document describes these seven
real stages advancing on administrative approval decisions (e.g.
"Registration Approval", "Meets Quality Standards?") — not an OPBOH-style
assessment. The one place OPBOH plausibly does belong is Phase 2's first
step, "Diagnostic assessment" (the step right after this document ends),
which is an encouraging sign the two will eventually line up — but as
written this precondition applies from stage 1, too early. Not fixed
here: needs either per-stage configurable advancement rules or explicit
confirmation from KMI/UACOC on what actually gates each of these seven
steps.
"""

import uuid
from datetime import UTC, date, datetime
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ipacgs.models.gate import Gate, GateDecision, GateDecisionStatus
from ipacgs.models.opboh import FindingStatus, OpbohAssessment, OpbohAssessmentStatus, OpbohFinding
from ipacgs.models.project import (
    Project,
    ProjectStatus,
    Stage,
    StageGateDecision,
    StageGateDecisionKind,
)
from ipacgs.services.opboh_query import compute_assessment_score

# Deliberately importing Gate/GateDecision models here, not
# services/gate_engine.py — gate_engine already imports RagStatus/
# compute_project_rag/list_open_findings_for_project from this module for
# its readiness pack, so importing gate_engine back from here would be a
# circular import. A plain, exact-match model query costs a few lines of
# duplication against gate_engine.gate_blocking_advancement; that's
# cheaper than restructuring two services around avoiding it.

_ACCEPTED_STATES = frozenset(
    {OpbohAssessmentStatus.ACCEPTED, OpbohAssessmentStatus.CONDITIONALLY_ACCEPTED}
)
_OPEN_FINDING_STATES = frozenset({FindingStatus.OPEN, FindingStatus.IN_PROGRESS})


class StageEngineError(Exception):
    """Base class for this module's domain exceptions."""


class NoStagesConfigured(StageEngineError):
    """No active Stage rows exist to assign a new project to — run
    scripts/seed_stages.py (or register real stages) first."""


class IllegalStageAdvancement(StageEngineError):
    """Raised when advance_stage's preconditions aren't met."""


async def create_project(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    organisation_id: uuid.UUID,
    name: str,
    description: str | None,
    actor: str,
    sector: str | None = None,
    risk_rating: str | None = None,
) -> Project:
    first_stage_result = await session.execute(
        select(Stage).where(Stage.is_active.is_(True)).order_by(Stage.sequence).limit(1)
    )
    first_stage = first_stage_result.scalars().first()
    if first_stage is None:
        raise NoStagesConfigured("No active stages configured — nothing to start a project at.")

    project = Project(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        organisation_id=organisation_id,
        name=name,
        description=description,
        sector=sector,
        risk_rating=risk_rating,
        current_stage_id=first_stage.id,
        status=ProjectStatus.ACTIVE,
        created_by=actor,
        updated_by=actor,
    )
    session.add(project)
    await session.flush()
    return project


async def advance_stage(
    session: AsyncSession,
    project: Project,
    *,
    supporting_assessment: OpbohAssessment,
    actor: str,
    notes: str | None = None,
) -> StageGateDecision:
    if supporting_assessment.status not in _ACCEPTED_STATES:
        raise IllegalStageAdvancement(
            f"Assessment {supporting_assessment.id} is "
            f"{supporting_assessment.status.value} — advancing a stage needs an "
            "accepted (or conditionally accepted) assessment, not a date."
        )
    if supporting_assessment.organisation_id != project.organisation_id:
        raise IllegalStageAdvancement(
            f"Assessment {supporting_assessment.id} is for a different organisation "
            f"than project {project.id} — it can't justify this project's advancement."
        )

    current_stage = await session.get(Stage, project.current_stage_id)
    if current_stage is None:
        raise IllegalStageAdvancement(
            f"Project {project.id}'s current stage {project.current_stage_id} no longer exists."
        )

    # GATE-0[0-1]-006 — non-bypassable effect. If a gate is configured to
    # trigger at the project's current stage, it must have a PROCEED
    # decision before the project can leave that stage — an accepted
    # assessment alone isn't enough once a gate sits in the way. This is
    # what makes "non-bypassable" a real, enforced property rather than a
    # documented promise: it's the one irreversible action this platform
    # actually has (moving a project past a stage), so that's what's
    # blocked, not an invented flag with no real consequence.
    blocking_gate_result = await session.execute(
        select(Gate).where(Gate.is_active.is_(True), Gate.trigger_stage_id == current_stage.id)
    )
    blocking_gate = blocking_gate_result.scalars().first()
    if blocking_gate is not None:
        decision_result = await session.execute(
            select(GateDecision)
            .where(GateDecision.project_id == project.id, GateDecision.gate_id == blocking_gate.id)
            .order_by(GateDecision.created_at.desc())
            .limit(1)
        )
        latest_gate_decision = decision_result.scalars().first()
        if (
            latest_gate_decision is None
            or latest_gate_decision.status != GateDecisionStatus.PROCEED
        ):
            raise IllegalStageAdvancement(
                f"Gate {blocking_gate.code} must reach a PROCEED decision before project "
                f"{project.id} can advance past {current_stage.code}."
            )

    next_stage_result = await session.execute(
        select(Stage)
        .where(Stage.is_active.is_(True), Stage.sequence > current_stage.sequence)
        .order_by(Stage.sequence)
        .limit(1)
    )
    next_stage = next_stage_result.scalars().first()
    if next_stage is None:
        raise IllegalStageAdvancement(
            f"Project {project.id} is already at the final configured stage ({current_stage.code})."
        )

    decision = StageGateDecision(
        id=uuid.uuid4(),
        tenant_id=project.tenant_id,
        project_id=project.id,
        kind=StageGateDecisionKind.ADVANCE,
        from_stage_id=current_stage.id,
        to_stage_id=next_stage.id,
        supporting_assessment_id=supporting_assessment.id,
        decided_by=actor,
        decided_at=datetime.now(UTC),
        notes=notes,
    )
    session.add(decision)

    project.current_stage_id = next_stage.id
    project.updated_by = actor
    # Reset — the assignment was for driving the *previous* stage forward;
    # someone new (or nobody yet) is responsible for the one just entered.
    project.assigned_to = None
    project.stage_due_date = None

    await session.flush()
    return decision


async def reopen_stage(
    session: AsyncSession,
    project: Project,
    *,
    target_stage_id: uuid.UUID,
    actor: str,
    reason: str,
) -> StageGateDecision:
    """The other direction PRN-001 doesn't cover: not "what unlocks the
    next stage" but "what happens when confidence in a stage already
    passed turns out to be wrong" (evidence withdrawn, a fraud indicator,
    a reviewer catching something later). No supporting assessment is
    required or even meaningful here — a reopen is *withdrawing*
    confidence, not adding new evidence — but a reason is, so this can
    never be a silent, unexplained rewind."""
    if not reason.strip():
        raise IllegalStageAdvancement("Reopening a stage requires a reason.")

    current_stage = await session.get(Stage, project.current_stage_id)
    if current_stage is None:
        raise IllegalStageAdvancement(
            f"Project {project.id}'s current stage {project.current_stage_id} no longer exists."
        )

    target_stage = await session.get(Stage, target_stage_id)
    if target_stage is None or not target_stage.is_active:
        raise IllegalStageAdvancement(f"No active stage {target_stage_id} to reopen to.")
    if target_stage.sequence >= current_stage.sequence:
        raise IllegalStageAdvancement(
            f"Reopen must move to a stage earlier than the current one ({current_stage.code}), "
            f"not {target_stage.code}."
        )

    decision = StageGateDecision(
        id=uuid.uuid4(),
        tenant_id=project.tenant_id,
        project_id=project.id,
        kind=StageGateDecisionKind.REOPEN,
        from_stage_id=current_stage.id,
        to_stage_id=target_stage.id,
        supporting_assessment_id=None,
        decided_by=actor,
        decided_at=datetime.now(UTC),
        notes=reason,
    )
    session.add(decision)

    project.current_stage_id = target_stage.id
    project.updated_by = actor
    project.assigned_to = None
    project.stage_due_date = None

    await session.flush()
    return decision


async def assign_stage(
    session: AsyncSession,
    project: Project,
    *,
    assigned_to: str,
    due_date: date | None,
    actor: str,
) -> Project:
    project.assigned_to = assigned_to
    project.stage_due_date = due_date
    project.updated_by = actor
    await session.flush()
    return project


class RagStatus(StrEnum):
    """Computed, not stored — same reasoning as opboh_scoring's
    AssessmentResult: derived from the project's latest assessment every
    time it's asked for, never a column that could go stale. RED/AMBER/GREEN
    mirror opboh_scoring.RagBand's real Assurance Score banding exactly
    (this project-level wrapper just adds GREY, for "no assessment linked
    to this project yet" — a case the assessment-level RagBand has no
    concept of)."""

    RED = "red"
    AMBER = "amber"
    GREEN = "green"
    GREY = "grey"  # no assessment linked to this project yet


async def compute_project_rag(session: AsyncSession, project: Project) -> RagStatus:
    latest_result = await session.execute(
        select(OpbohAssessment)
        .where(OpbohAssessment.project_id == project.id)
        .order_by(OpbohAssessment.created_at.desc())
        .limit(1)
    )
    assessment = latest_result.scalars().first()
    if assessment is None:
        return RagStatus.GREY

    score = await compute_assessment_score(session, assessment)
    return RagStatus(score.rag.value)


async def list_open_findings_for_project(
    session: AsyncSession, project: Project
) -> list[OpbohFinding]:
    """Epic 5's "residual gaps become owned, tracked actions" ticket,
    without a second findings mechanism — OpbohFinding (Epic 3) already
    has severity/owner/due_date/status; this just surfaces the open ones
    across every assessment this project is actually linked to."""
    result = await session.execute(
        select(OpbohFinding)
        .join(OpbohAssessment, OpbohFinding.assessment_id == OpbohAssessment.id)
        .where(
            OpbohAssessment.project_id == project.id,
            OpbohFinding.status.in_(_OPEN_FINDING_STATES),
        )
    )
    return list(result.scalars().all())
