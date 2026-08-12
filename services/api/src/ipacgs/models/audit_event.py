"""The append-only audit log — `FR-AUD-001…002`, distinct from the
`AuditedMixin` row-level columns (see `models/base.py`'s docstring for why
both exist). Every create/change/delete/approve/export anywhere in the
system writes one of these. Nothing ever updates or deletes a row here —
there is deliberately no `updated_at` column, and application code must never
issue an UPDATE or DELETE against this table.
"""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import DateTime, Enum, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ipacgs.models.base import Base, TenantScopedMixin


class AuditAction(StrEnum):
    CREATE = "create"
    CHANGE = "change"
    DELETE = "delete"
    APPROVE = "approve"
    REJECT = "reject"
    EXPORT = "export"


class AuditEvent(Base, TenantScopedMixin):
    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    actor_object_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    action: Mapped[AuditAction] = mapped_column(
        # Same values_callable fix as Tenant.status (models/tenant.py) — same
        # root cause, just not yet exercised by a passing test before that
        # one blocked on it first.
        Enum(
            AuditAction,
            name="audit_action",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
    )

    entity_type: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True, doc="e.g. 'organisation', 'opboh_assessment'"
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)

    before_values: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    after_values: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    correlation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        doc="Shared across every audit event produced by one request/workflow "
        "run, so a single user action that touches several tables can be "
        "reconstructed as one story rather than N unrelated rows.",
    )
