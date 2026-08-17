"""The OPBOH assessment state machine — `FW-OPBOH-006` (segregation of
duties) and `FW-OPBOH-007` (controlled states), and the fatal-flaw block
that's the whole point of `FW-OPBOH-015`.

Every transition here does three things, in order: validate the transition
is legal from the current state, enforce whatever segregation-of-duties rule
applies to it, then persist the change with an audit event — the same
create-inside-the-same-transaction pattern `core/audit.py` documents.

`decide` also closes a gap flagged since the bill-of-health report shipped:
a critical-control failure used to produce nothing but a number — nothing in
this codebase ever called `opboh_findings.create_finding`. It now does,
right here, the one place a critical failure is confirmed as part of a real
decision (see `_create_findings_for_critical_failures` below) — `FW-OPBOH-008`
("owned, dated, escalating actions"), not just a score on a report.

`reopen_assessment` closes the gap that surfaced building the finding
idempotency test above: the state graph has always allowed moving an
ACCEPTED/CONDITIONALLY_ACCEPTED/REJECTED assessment back through REOPENED
to DRAFT, but nothing exposed it — `simple_transition` refuses both targets
outright now, specifically so `reopen_assessment`'s required reason can't be
bypassed by calling the generic function instead.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ipacgs.core.audit import record_audit_event
from ipacgs.core.security import MakerCheckerViolation
from ipacgs.models.audit_event import AuditAction
from ipacgs.models.opboh import (
    FindingStatus,
    OpbohAssessment,
    OpbohAssessmentStatus,
    OpbohFinding,
    OpbohResponse,
)
from ipacgs.services import opboh_findings
from ipacgs.services.opboh_scoring import CriticalFailure

# Same set opboh_report.py's bill-of-health report already uses for "still
# needs attention" — deliberately wider than stage_engine's own
# OPEN/IN_PROGRESS-only set, which exists to answer a different question.
_OPEN_FINDING_STATUSES = frozenset(
    {FindingStatus.OPEN, FindingStatus.IN_PROGRESS, FindingStatus.ESCALATED}
)

# The legal state graph. A transition not listed here is refused outright —
# FW-OPBOH-007 describes controlled states, not a free-for-all status field.
_ALLOWED_TRANSITIONS: dict[OpbohAssessmentStatus, frozenset[OpbohAssessmentStatus]] = {
    OpbohAssessmentStatus.DRAFT: frozenset(
        {OpbohAssessmentStatus.EVIDENCE_REQUESTED, OpbohAssessmentStatus.SUBMITTED}
    ),
    OpbohAssessmentStatus.EVIDENCE_REQUESTED: frozenset({OpbohAssessmentStatus.SUBMITTED}),
    OpbohAssessmentStatus.SUBMITTED: frozenset({OpbohAssessmentStatus.UNDER_ASSESSMENT}),
    OpbohAssessmentStatus.UNDER_ASSESSMENT: frozenset(
        {
            OpbohAssessmentStatus.CLARIFICATION_REQUESTED,
            OpbohAssessmentStatus.INDEPENDENTLY_REVIEWED,
            OpbohAssessmentStatus.REJECTED,
        }
    ),
    OpbohAssessmentStatus.CLARIFICATION_REQUESTED: frozenset(
        {OpbohAssessmentStatus.SUBMITTED, OpbohAssessmentStatus.UNDER_ASSESSMENT}
    ),
    OpbohAssessmentStatus.INDEPENDENTLY_REVIEWED: frozenset(
        {
            OpbohAssessmentStatus.CONDITIONALLY_ACCEPTED,
            OpbohAssessmentStatus.ACCEPTED,
            OpbohAssessmentStatus.REJECTED,
            OpbohAssessmentStatus.CLARIFICATION_REQUESTED,
        }
    ),
    OpbohAssessmentStatus.CONDITIONALLY_ACCEPTED: frozenset(
        {OpbohAssessmentStatus.ACCEPTED, OpbohAssessmentStatus.REOPENED}
    ),
    OpbohAssessmentStatus.ACCEPTED: frozenset(
        {OpbohAssessmentStatus.REOPENED, OpbohAssessmentStatus.SUPERSEDED}
    ),
    OpbohAssessmentStatus.REJECTED: frozenset({OpbohAssessmentStatus.REOPENED}),
    OpbohAssessmentStatus.REOPENED: frozenset({OpbohAssessmentStatus.DRAFT}),
    OpbohAssessmentStatus.SUPERSEDED: frozenset(),
}


class IllegalTransition(Exception):
    """Raised when a transition isn't in the state graph at all — a
    different failure mode from MakerCheckerViolation, which fires when the
    transition would be legal for someone else, just not this actor."""


@dataclass(frozen=True)
class TransitionResult:
    assessment_id: uuid.UUID
    previous_status: OpbohAssessmentStatus
    new_status: OpbohAssessmentStatus


def _require_legal(current: OpbohAssessmentStatus, target: OpbohAssessmentStatus) -> None:
    if target not in _ALLOWED_TRANSITIONS.get(current, frozenset()):
        raise IllegalTransition(
            f"Cannot move an OPBOH assessment from {current.value} to {target.value}."
        )


def _require_distinct(actor: str, *prior_actors: str | None) -> None:
    """SOD-001/002 generalised to more than two parties — the actor taking
    this step must not be any of the people who already held an earlier
    seat on this same assessment."""
    for prior in prior_actors:
        if prior is not None and prior == actor:
            raise MakerCheckerViolation(
                f"User {actor} already acted on this assessment in an earlier role and "
                "cannot also take this step — see SOD-001/002."
            )


async def begin_assessment(
    session: AsyncSession, assessment: OpbohAssessment, *, actor: str, correlation_id: uuid.UUID
) -> TransitionResult:
    """SUBMITTED -> UNDER_ASSESSMENT. `actor` becomes the assessor and must
    not be the preparer."""
    _require_legal(assessment.status, OpbohAssessmentStatus.UNDER_ASSESSMENT)
    _require_distinct(actor, assessment.prepared_by)

    previous = assessment.status
    assessment.status = OpbohAssessmentStatus.UNDER_ASSESSMENT
    assessment.assessed_by = actor
    await record_audit_event(
        session,
        tenant_id=assessment.tenant_id,
        actor_object_id=actor,
        action=AuditAction.CHANGE,
        entity_type="opboh_assessment",
        entity_id=assessment.id,
        correlation_id=correlation_id,
        before_values={"status": previous.value},
        after_values={"status": assessment.status.value, "assessed_by": actor},
    )
    return TransitionResult(assessment.id, previous, assessment.status)


async def independently_review(
    session: AsyncSession, assessment: OpbohAssessment, *, actor: str, correlation_id: uuid.UUID
) -> TransitionResult:
    """UNDER_ASSESSMENT -> INDEPENDENTLY_REVIEWED. `actor` becomes the
    independent reviewer and must not be the preparer or the assessor —
    "independent" is enforced here, not just implied by the field name."""
    _require_legal(assessment.status, OpbohAssessmentStatus.INDEPENDENTLY_REVIEWED)
    _require_distinct(actor, assessment.prepared_by, assessment.assessed_by)

    previous = assessment.status
    assessment.status = OpbohAssessmentStatus.INDEPENDENTLY_REVIEWED
    assessment.reviewed_by = actor
    await record_audit_event(
        session,
        tenant_id=assessment.tenant_id,
        actor_object_id=actor,
        action=AuditAction.CHANGE,
        entity_type="opboh_assessment",
        entity_id=assessment.id,
        correlation_id=correlation_id,
        before_values={"status": previous.value},
        after_values={"status": assessment.status.value, "reviewed_by": actor},
    )
    return TransitionResult(assessment.id, previous, assessment.status)


async def decide(
    session: AsyncSession,
    assessment: OpbohAssessment,
    *,
    decision: OpbohAssessmentStatus,
    actor: str,
    has_critical_failure: bool,
    assurance_score: float,
    decision_summary: str | None,
    correlation_id: uuid.UUID,
    critical_failures: tuple[CriticalFailure, ...] = (),
) -> TransitionResult:
    """INDEPENDENTLY_REVIEWED -> ACCEPTED / CONDITIONALLY_ACCEPTED / REJECTED.
    `actor` becomes the approver — the final decision authority — and must
    not be the preparer, assessor, or reviewer.

    `has_critical_failure` comes from the scoring engine
    (`AssessmentResult.has_critical_failure`), computed just before this is
    called — FW-OPBOH-015's fatal-flaw block: an assessment with an
    unresolved critical-control failure cannot reach ACCEPTED, full stop,
    no matter who approves it or how the rest of the score looks. Only
    CONDITIONALLY_ACCEPTED (with the condition on record) or REJECTED are
    reachable in that state.

    `critical_failures` — `AssessmentResult.critical_failures`, the same
    source `has_critical_failure` was derived from — is what actually turns
    each failure into an `OpbohFinding` (`_create_findings_for_critical_failures`,
    below) once the decision itself is legal. Defaults to empty for callers
    that only care about the fatal-flaw block itself, same as
    `has_critical_failure` alone did before this parameter existed.
    """
    if decision not in {
        OpbohAssessmentStatus.ACCEPTED,
        OpbohAssessmentStatus.CONDITIONALLY_ACCEPTED,
        OpbohAssessmentStatus.REJECTED,
    }:
        raise IllegalTransition(f"{decision.value} is not a valid decision outcome.")
    _require_legal(assessment.status, decision)
    _require_distinct(actor, assessment.prepared_by, assessment.assessed_by, assessment.reviewed_by)

    if has_critical_failure and decision == OpbohAssessmentStatus.ACCEPTED:
        raise IllegalTransition(
            "FW-OPBOH-015: cannot ACCEPT an assessment with an unresolved critical-control "
            "failure. Use CONDITIONALLY_ACCEPTED (with the condition recorded) or REJECTED."
        )

    previous = assessment.status
    assessment.status = decision
    assessment.approved_by = actor
    assessment.has_critical_failure = has_critical_failure
    assessment.assurance_score = assurance_score
    assessment.decision_summary = decision_summary

    audit_action = (
        AuditAction.APPROVE if decision != OpbohAssessmentStatus.REJECTED else AuditAction.REJECT
    )
    await record_audit_event(
        session,
        tenant_id=assessment.tenant_id,
        actor_object_id=actor,
        action=audit_action,
        entity_type="opboh_assessment",
        entity_id=assessment.id,
        correlation_id=correlation_id,
        before_values={"status": previous.value},
        after_values={
            "status": assessment.status.value,
            "approved_by": actor,
            "assurance_score": assurance_score,
            "has_critical_failure": has_critical_failure,
        },
    )

    if critical_failures:
        await _create_findings_for_critical_failures(
            session, assessment, critical_failures, actor=actor, correlation_id=correlation_id
        )

    return TransitionResult(assessment.id, previous, assessment.status)


async def _create_findings_for_critical_failures(
    session: AsyncSession,
    assessment: OpbohAssessment,
    critical_failures: tuple[CriticalFailure, ...],
    *,
    actor: str,
    correlation_id: uuid.UUID,
) -> None:
    """Idempotent across repeated `decide()` calls on the same assessment —
    a REOPENED assessment that gets decided again with the same control
    still failing reuses its still-open finding rather than piling up a
    second one for the same underlying problem. Dedup key is `response_id`
    when a response exists; a critical control can fail as "unanswered"
    (see `opboh_scoring._question_failure_reason`) with no `OpbohResponse`
    row to key off at all, so an unanswered failure dedupes on its own
    (stable, since it always names the same control) description text
    instead.
    """
    question_ids = [uuid.UUID(cf.question_id) for cf in critical_failures]
    responses_result = await session.execute(
        select(OpbohResponse).where(
            OpbohResponse.assessment_id == assessment.id,
            OpbohResponse.question_id.in_(question_ids),
        )
    )
    response_by_question = {r.question_id: r for r in responses_result.scalars().all()}

    existing_result = await session.execute(
        select(OpbohFinding).where(
            OpbohFinding.assessment_id == assessment.id,
            OpbohFinding.status.in_(_OPEN_FINDING_STATUSES),
        )
    )
    existing_findings = list(existing_result.scalars().all())
    existing_by_response = {f.response_id for f in existing_findings if f.response_id is not None}
    existing_descriptions = {f.description for f in existing_findings if f.response_id is None}

    for critical_failure in critical_failures:
        response = response_by_question.get(uuid.UUID(critical_failure.question_id))
        description = (
            f"Critical control {critical_failure.control_objective!r} failed: "
            f"{critical_failure.reason}."
        )

        if response is not None:
            if response.id in existing_by_response:
                continue
        elif description in existing_descriptions:
            continue

        await opboh_findings.create_finding(
            session,
            tenant_id=assessment.tenant_id,
            assessment_id=assessment.id,
            response_id=response.id if response is not None else None,
            severity=opboh_findings.severity_for_critical_failure(critical_failure),
            description=description,
            created_by=actor,
            correlation_id=correlation_id,
        )


async def reopen_assessment(
    session: AsyncSession,
    assessment: OpbohAssessment,
    *,
    reason: str,
    actor: str,
    correlation_id: uuid.UUID,
) -> TransitionResult:
    """The other direction FW-OPBOH-015's fatal-flaw block doesn't cover:
    not "can this be accepted" but "what happens when confidence in an
    already-decided assessment turns out to be wrong" (evidence withdrawn,
    a fraud indicator, a reviewer catching something later) — same
    reasoning `stage_engine.reopen_stage` documents for itself. No
    segregation-of-duties check: reopening withdraws confidence, it isn't a
    new decision that needs its own distinct decision-maker — but a reason
    is required, so this can never be a silent, unexplained rewind.

    Moves straight through REOPENED to DRAFT in one call, recorded as two
    separate audit events even though the assessment's own observable
    status lands on DRAFT — REOPENED on its own is a transient marker
    nobody needs to act on separately, not a state worth stopping at.
    """
    if not reason.strip():
        raise IllegalTransition("Reopening an assessment requires a reason.")
    _require_legal(assessment.status, OpbohAssessmentStatus.REOPENED)

    previous = assessment.status
    assessment.status = OpbohAssessmentStatus.REOPENED
    await record_audit_event(
        session,
        tenant_id=assessment.tenant_id,
        actor_object_id=actor,
        action=AuditAction.CHANGE,
        entity_type="opboh_assessment",
        entity_id=assessment.id,
        correlation_id=correlation_id,
        before_values={"status": previous.value},
        after_values={"status": assessment.status.value, "reason": reason},
    )

    before_draft = assessment.status
    assessment.status = OpbohAssessmentStatus.DRAFT
    await record_audit_event(
        session,
        tenant_id=assessment.tenant_id,
        actor_object_id=actor,
        action=AuditAction.CHANGE,
        entity_type="opboh_assessment",
        entity_id=assessment.id,
        correlation_id=correlation_id,
        before_values={"status": before_draft.value},
        after_values={"status": assessment.status.value},
    )

    return TransitionResult(assessment.id, previous, assessment.status)


async def simple_transition(
    session: AsyncSession,
    assessment: OpbohAssessment,
    *,
    target: OpbohAssessmentStatus,
    actor: str,
    correlation_id: uuid.UUID,
) -> TransitionResult:
    """The transitions with no segregation-of-duties rule attached — moving
    into EVIDENCE_REQUESTED, SUBMITTED, CLARIFICATION_REQUESTED. Still
    validated against the state graph and still audited; just no
    `_require_distinct` check, because nothing in the SRS calls for one at
    these points.

    REOPENED and DRAFT (only reachable from REOPENED) are deliberately
    refused here even though `_ALLOWED_TRANSITIONS` permits them — use
    `reopen_assessment` instead, which requires a reason this function has
    no parameter for. Without this guard, this function would be a second,
    weaker path to the exact same state that skips that requirement."""
    if target in {OpbohAssessmentStatus.REOPENED, OpbohAssessmentStatus.DRAFT}:
        raise IllegalTransition(
            f"Use reopen_assessment to reach {target.value} — reopening requires a reason."
        )
    _require_legal(assessment.status, target)

    previous = assessment.status
    assessment.status = target
    await record_audit_event(
        session,
        tenant_id=assessment.tenant_id,
        actor_object_id=actor,
        action=AuditAction.CHANGE,
        entity_type="opboh_assessment",
        entity_id=assessment.id,
        correlation_id=correlation_id,
        before_values={"status": previous.value},
        after_values={"status": assessment.status.value},
    )
    return TransitionResult(assessment.id, previous, assessment.status)
