"""The OPBOH assessment state machine — `FW-OPBOH-006` (segregation of
duties) and `FW-OPBOH-007` (controlled states), and the fatal-flaw block
that's the whole point of `FW-OPBOH-015`.

Every transition here does three things, in order: validate the transition
is legal from the current state, enforce whatever segregation-of-duties rule
applies to it, then persist the change with an audit event — the same
create-inside-the-same-transaction pattern `core/audit.py` documents.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from ipacgs.core.audit import record_audit_event
from ipacgs.core.security import MakerCheckerViolation
from ipacgs.models.audit_event import AuditAction
from ipacgs.models.opboh import OpbohAssessment, OpbohAssessmentStatus

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
    into EVIDENCE_REQUESTED, SUBMITTED, CLARIFICATION_REQUESTED, REOPENED.
    Still validated against the state graph and still audited; just no
    `_require_distinct` check, because nothing in the SRS calls for one at
    these points."""
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
