"""Findings → owned, dated, escalating actions — `FW-OPBOH-008`. A gap
identified during scoring doesn't stay a number on a report; it becomes a
row someone is accountable for closing.
"""

import uuid
from datetime import UTC, date, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from ipacgs.core.audit import record_audit_event
from ipacgs.models.audit_event import AuditAction
from ipacgs.models.notification import NotificationKind
from ipacgs.models.opboh import FindingSeverity, FindingStatus, OpbohFinding
from ipacgs.services import notifications
from ipacgs.services.opboh_scoring import CriticalFailure


def severity_for_critical_failure(_: CriticalFailure) -> FindingSeverity:
    """Every critical-control failure is CRITICAL severity by definition —
    that's what "critical control" means. A separate function exists so a
    future framework with graded critical controls has somewhere to put
    that logic without touching the caller."""
    return FindingSeverity.CRITICAL


async def create_finding(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    assessment_id: uuid.UUID,
    response_id: uuid.UUID | None,
    severity: FindingSeverity,
    description: str,
    created_by: str,
    correlation_id: uuid.UUID,
    owner: str | None = None,
    due_date: date | None = None,
) -> OpbohFinding:
    finding = OpbohFinding(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        assessment_id=assessment_id,
        response_id=response_id,
        severity=severity,
        description=description,
        status=FindingStatus.OPEN,
        owner=owner,
        due_date=due_date,
        created_by=created_by,
        updated_by=created_by,
    )
    session.add(finding)
    await session.flush()
    await record_audit_event(
        session,
        tenant_id=tenant_id,
        actor_object_id=created_by,
        action=AuditAction.CREATE,
        entity_type="opboh_finding",
        entity_id=finding.id,
        correlation_id=correlation_id,
        after_values={"severity": severity.value, "description": description},
    )
    return finding


async def assign_owner(
    session: AsyncSession,
    finding: OpbohFinding,
    *,
    owner: str,
    due_date: date,
    actor: str,
    correlation_id: uuid.UUID,
) -> OpbohFinding:
    finding.owner = owner
    finding.due_date = due_date
    if finding.status == FindingStatus.OPEN:
        finding.status = FindingStatus.IN_PROGRESS
    await record_audit_event(
        session,
        tenant_id=finding.tenant_id,
        actor_object_id=actor,
        action=AuditAction.CHANGE,
        entity_type="opboh_finding",
        entity_id=finding.id,
        correlation_id=correlation_id,
        after_values={
            "owner": owner,
            "due_date": due_date.isoformat(),
            "status": finding.status.value,
        },
    )
    await notifications.notify(
        session,
        tenant_id=finding.tenant_id,
        recipient=owner,
        kind=NotificationKind.ASSIGNMENT,
        entity_type="opboh_finding",
        entity_id=finding.id,
        message=f"You've been assigned finding {finding.id} (due {due_date}).",
    )
    return finding


async def close_finding(
    session: AsyncSession, finding: OpbohFinding, *, actor: str, correlation_id: uuid.UUID
) -> OpbohFinding:
    finding.status = FindingStatus.CLOSED
    finding.closed_at = datetime.now(UTC)
    await record_audit_event(
        session,
        tenant_id=finding.tenant_id,
        actor_object_id=actor,
        action=AuditAction.CHANGE,
        entity_type="opboh_finding",
        entity_id=finding.id,
        correlation_id=correlation_id,
        after_values={"status": finding.status.value},
    )
    return finding


async def escalate_finding(
    session: AsyncSession, finding: OpbohFinding, *, actor: str, correlation_id: uuid.UUID
) -> OpbohFinding:
    """A finding overdue or too severe for its current owner to close
    unassisted. Escalation is itself an audited event, same as everything
    else here — who escalated what, and when, is exactly the kind of thing
    a later forensic review (PFA, R6) would need to reconstruct."""
    finding.status = FindingStatus.ESCALATED
    await record_audit_event(
        session,
        tenant_id=finding.tenant_id,
        actor_object_id=actor,
        action=AuditAction.CHANGE,
        entity_type="opboh_finding",
        entity_id=finding.id,
        correlation_id=correlation_id,
        after_values={"status": finding.status.value},
    )
    # No RBAC roles yet, so "notify the configured authority" (WF-ESC-001)
    # isn't answerable in general — notifying the existing owner (if any)
    # is what's actually knowable right now. A finding with no owner yet
    # has nobody to escalate *to* beyond whoever's watching the audit log.
    if finding.owner is not None:
        await notifications.notify(
            session,
            tenant_id=finding.tenant_id,
            recipient=finding.owner,
            kind=NotificationKind.ESCALATION,
            entity_type="opboh_finding",
            entity_id=finding.id,
            message=f"Finding {finding.id} has been escalated.",
        )
    return finding
