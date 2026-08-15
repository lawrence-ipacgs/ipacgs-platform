"""Gate Engine — Epic 6

Written by hand, same caveat as every migration before it: no live
database to autogenerate against in this sandbox — review carefully
against ipacgs/models/ before deploying.

Every enum here is declared inline inside its own create_table, not
added via a later op.add_column — migration 0005 hit UndefinedObjectError
doing that on an existing table (SQLAlchemy auto-creates an enum type as
a table dependency for create_table, not for add_column). Nothing here
needs that pattern, so nothing here can repeat that bug.

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-15
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "gates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(20), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column(
            "trigger_stage_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("stages.id"),
            nullable=False,
        ),
        sa.Column("required_quorum", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("updated_by", sa.String(), nullable=False),
    )
    op.create_index("ix_gates_trigger_stage_id", "gates", ["trigger_stage_id"])

    op.create_table(
        "gate_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False
        ),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id"),
            nullable=False,
        ),
        sa.Column(
            "gate_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("gates.id"), nullable=False
        ),
        sa.Column(
            "status",
            sa.Enum("pending", "proceed", "hold", "suspended", name="gate_decision_status"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("opened_by", sa.String(36), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.Column("suspended_at", sa.DateTime(timezone=True)),
        sa.Column("suspended_by", sa.String(36)),
        sa.Column("suspension_reason", sa.Text()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("updated_by", sa.String(), nullable=False),
    )
    op.create_index("ix_gate_decisions_tenant_id", "gate_decisions", ["tenant_id"])
    op.create_index("ix_gate_decisions_project_id", "gate_decisions", ["project_id"])
    op.create_index("ix_gate_decisions_gate_id", "gate_decisions", ["gate_id"])

    op.create_table(
        "gate_votes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "gate_decision_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("gate_decisions.id"),
            nullable=False,
        ),
        sa.Column("voter", sa.String(36), nullable=False),
        sa.Column(
            "outcome",
            sa.Enum("proceed", "hold", name="gate_vote_outcome"),
            nullable=False,
        ),
        sa.Column("voted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.UniqueConstraint("gate_decision_id", "voter", name="uq_gate_vote_one_per_voter"),
    )
    op.create_index("ix_gate_votes_gate_decision_id", "gate_votes", ["gate_decision_id"])

    op.create_table(
        "gate_certificates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "gate_decision_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("gate_decisions.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("gate_certificates")
    op.drop_index("ix_gate_votes_gate_decision_id", table_name="gate_votes")
    op.drop_table("gate_votes")
    sa.Enum(name="gate_vote_outcome").drop(op.get_bind(), checkfirst=True)
    op.drop_index("ix_gate_decisions_gate_id", table_name="gate_decisions")
    op.drop_index("ix_gate_decisions_project_id", table_name="gate_decisions")
    op.drop_index("ix_gate_decisions_tenant_id", table_name="gate_decisions")
    op.drop_table("gate_decisions")
    sa.Enum(name="gate_decision_status").drop(op.get_bind(), checkfirst=True)
    op.drop_index("ix_gates_trigger_stage_id", table_name="gates")
    op.drop_table("gates")
