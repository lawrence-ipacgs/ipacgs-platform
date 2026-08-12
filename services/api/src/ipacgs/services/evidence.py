"""Evidence review — Figure 2 of the architecture document, made real: a
submitted document only becomes something the rest of the system can rely
on after a named person, who isn't the person who submitted it, accepts it.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from ipacgs.core.audit import record_audit_event
from ipacgs.core.security import MakerCheckerViolation
from ipacgs.models.audit_event import AuditAction
from ipacgs.models.evidence import EvidenceDocument, EvidenceStatus

_REVIEWABLE_STATES = frozenset({EvidenceStatus.SUBMITTED, EvidenceStatus.UNDER_REVIEW})


class IllegalEvidenceTransition(Exception):
    pass


async def submit_evidence(
    session: AsyncSession, evidence: EvidenceDocument, *, submitter: str, correlation_id: uuid.UUID
) -> EvidenceDocument:
    if evidence.status not in {EvidenceStatus.REQUESTED, EvidenceStatus.REJECTED}:
        raise IllegalEvidenceTransition(
            f"Cannot submit evidence currently in status {evidence.status.value}."
        )
    previous = evidence.status
    evidence.status = EvidenceStatus.SUBMITTED
    evidence.submitted_by = submitter
    await record_audit_event(
        session,
        tenant_id=evidence.tenant_id,
        actor_object_id=submitter,
        action=AuditAction.CHANGE,
        entity_type="evidence_document",
        entity_id=evidence.id,
        correlation_id=correlation_id,
        before_values={"status": previous.value},
        after_values={"status": evidence.status.value, "submitted_by": submitter},
    )
    return evidence


async def accept_evidence(
    session: AsyncSession, evidence: EvidenceDocument, *, reviewer: str, correlation_id: uuid.UUID
) -> EvidenceDocument:
    """The Human Review Gate. A reviewer cannot accept their own submission —
    this is the mechanism, not a policy statement about it."""
    if evidence.status not in _REVIEWABLE_STATES:
        raise IllegalEvidenceTransition(
            f"Cannot review evidence in status {evidence.status.value}."
        )
    if evidence.submitted_by is not None and evidence.submitted_by == reviewer:
        raise MakerCheckerViolation(
            f"User {reviewer} submitted this evidence and cannot also accept it — see SOD-001/002."
        )

    previous = evidence.status
    evidence.status = EvidenceStatus.ACCEPTED
    evidence.reviewed_by = reviewer
    evidence.reviewed_at = datetime.now(UTC)
    await record_audit_event(
        session,
        tenant_id=evidence.tenant_id,
        actor_object_id=reviewer,
        action=AuditAction.APPROVE,
        entity_type="evidence_document",
        entity_id=evidence.id,
        correlation_id=correlation_id,
        before_values={"status": previous.value},
        after_values={"status": evidence.status.value, "reviewed_by": reviewer},
    )
    return evidence


async def reject_evidence(
    session: AsyncSession,
    evidence: EvidenceDocument,
    *,
    reviewer: str,
    reason: str,
    correlation_id: uuid.UUID,
) -> EvidenceDocument:
    if evidence.status not in _REVIEWABLE_STATES:
        raise IllegalEvidenceTransition(
            f"Cannot review evidence in status {evidence.status.value}."
        )
    if evidence.submitted_by is not None and evidence.submitted_by == reviewer:
        raise MakerCheckerViolation(
            f"User {reviewer} submitted this evidence and cannot also reject it — see SOD-001/002."
        )

    previous = evidence.status
    evidence.status = EvidenceStatus.REJECTED
    evidence.reviewed_by = reviewer
    evidence.reviewed_at = datetime.now(UTC)
    await record_audit_event(
        session,
        tenant_id=evidence.tenant_id,
        actor_object_id=reviewer,
        action=AuditAction.REJECT,
        entity_type="evidence_document",
        entity_id=evidence.id,
        correlation_id=correlation_id,
        before_values={"status": previous.value},
        after_values={"status": evidence.status.value, "reviewed_by": reviewer, "reason": reason},
    )
    return evidence
