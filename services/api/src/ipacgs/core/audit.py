"""Single entry point for writing audit events — `FR-AUD-001…002`.

Nothing should construct an `AuditEvent` row directly; going through
`record_audit_event` is what guarantees every write gets a correlation ID and
a consistent shape, and gives us exactly one place to change if the audit
event schema ever needs to grow (e.g. adding a reason-code field later).
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from ipacgs.models.audit_event import AuditAction, AuditEvent


async def record_audit_event(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_object_id: str,
    action: AuditAction,
    entity_type: str,
    entity_id: uuid.UUID,
    correlation_id: uuid.UUID,
    before_values: dict | None = None,
    after_values: dict | None = None,
) -> AuditEvent:
    """Adds the event to `session` but does not commit — call within the same
    transaction as the change being audited, so the audit record and the
    change it describes either both land or both roll back together."""
    event = AuditEvent(
        tenant_id=tenant_id,
        actor_object_id=actor_object_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        correlation_id=correlation_id,
        before_values=before_values,
        after_values=after_values,
    )
    session.add(event)
    return event
