"""Command Centre & Notifications — Epic 7

Written by hand, same caveat as every migration before it: no live
database to autogenerate against in this sandbox — review carefully
against ipacgs/models/ before deploying. The notification_kind enum is
declared inline inside create_table, not added via a later add_column —
see migration 0005's own note on why that ordering matters.

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-15
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False
        ),
        sa.Column("recipient", sa.String(36), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "assignment",
                "due_date",
                "escalation",
                "gate_ready",
                "evidence_request",
                name="notification_kind",
            ),
            nullable=False,
        ),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("read_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_notifications_tenant_id", "notifications", ["tenant_id"])
    op.create_index("ix_notifications_recipient", "notifications", ["recipient"])
    op.create_index(
        "ix_notifications_entity_type_entity_id", "notifications", ["entity_type", "entity_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_notifications_entity_type_entity_id", table_name="notifications")
    op.drop_index("ix_notifications_recipient", table_name="notifications")
    op.drop_index("ix_notifications_tenant_id", table_name="notifications")
    op.drop_table("notifications")
    sa.Enum(name="notification_kind").drop(op.get_bind(), checkfirst=True)
