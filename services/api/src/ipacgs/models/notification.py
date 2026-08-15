"""Epic 7 — Command Centre & Notifications (basic).

Ticket references are FR-RPT-001…002 (subset), FR-NTF-001…002, WF-ESC-001…002.

Two honesty notes:

1. This is an in-app, queryable notification record — `GET /me/notifications`
   is the "personal work queue" FR-RPT-001 asks for. There is no actual
   delivery mechanism (no email/SMS/push integration exists in this
   platform) — a notification exists the moment something creates one,
   and a recipient finds out about it by asking, not by being told.
2. `GATE_READY` and `EVIDENCE_REQUEST` are declared here as kinds but
   nothing in services/notifications.py triggers them yet — both need a
   real "who's eligible to see this" answer that doesn't exist without
   RBAC (infra/scripts/create-app-registrations.sh, still not run).
   `ASSIGNMENT` and `DUE_DATE`/`ESCALATION` have a real, unambiguous
   recipient already (Project.assigned_to, OpbohFinding.owner) and are
   the ones actually wired up.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, Enum, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from ipacgs.models.base import Base, TenantScopedMixin

_VALUES_CALLABLE = lambda enum_cls: [e.value for e in enum_cls]  # noqa: E731


class NotificationKind(StrEnum):
    ASSIGNMENT = "assignment"
    DUE_DATE = "due_date"
    ESCALATION = "escalation"
    GATE_READY = "gate_ready"
    EVIDENCE_REQUEST = "evidence_request"


class Notification(Base, TenantScopedMixin):
    """No AuditedMixin — a notification is an immutable event except for
    the read/unread flag, same reasoning as GateVote/StageGateDecision
    not carrying updated_by: nobody should be able to edit what a
    notification said after the fact, only acknowledge having seen it."""

    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recipient: Mapped[str] = mapped_column(String(36), nullable=False)
    kind: Mapped[NotificationKind] = mapped_column(
        Enum(NotificationKind, name="notification_kind", values_callable=_VALUES_CALLABLE),
        nullable=False,
    )
    # Generic reference, same pattern core/audit.py's AuditEvent already
    # uses for entity_type/entity_id — a notification can be about a
    # Project, an OpbohFinding, or anything else with an id, without this
    # table needing a nullable FK column per possible source.
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
