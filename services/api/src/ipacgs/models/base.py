"""Base classes every model inherits from.

Two mixins are applied to nearly everything, on purpose, from the very first
migration — retrofitting either after real data exists is the expensive path
the architecture document explicitly warns against (Section 3, Epic 2):

- `TenantScopedMixin` — every row belongs to exactly one tenant. Milestone 1.1
  only has one real tenant (KMI Africa) but the schema is built for the
  multi-tenant reality confirmed in this document's Section 3 decision card
  ("design for a second tenant now").
- `AuditedMixin` — who created/last-changed this row, and when. This is
  *row-level* audit metadata; the full before/after event log (FR-AUD-001…002)
  is a separate table — see `models/audit_event.py` — because "who touched
  this row last" and "the complete history of every change to it" are
  different questions with different retention/query needs.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class TenantScopedMixin:
    """FK to tenants.id. Query layers must filter by this — there is no
    row-level security policy enforcing it at the database level yet
    (worth revisiting before a second tenant's data is live; tracked as a
    follow-up, not blocking Milestone 1.1 with only one tenant)."""

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )


class AuditedMixin:
    """Row-level audit metadata. `created_by`/`updated_by` are Entra ID
    object IDs (strings, not FKs to a users table — this platform doesn't
    own identity, Entra ID does)."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_by: Mapped[str] = mapped_column(nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    updated_by: Mapped[str] = mapped_column(nullable=False)
