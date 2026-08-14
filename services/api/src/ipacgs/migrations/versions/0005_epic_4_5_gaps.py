"""Epic 4/5 gap-closing — applicability rules, reopen support, RAG inputs

Written by hand, same caveat as every migration before it: no live
database to autogenerate against in this sandbox — review carefully
against ipacgs/models/ before deploying.

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-15
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "framework_applicability_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "framework_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("frameworks.id"),
            nullable=False,
        ),
        sa.Column("sector", sa.String(100)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("updated_by", sa.String(), nullable=False),
    )
    op.create_index(
        "ix_framework_applicability_rules_framework_id",
        "framework_applicability_rules",
        ["framework_id"],
    )

    op.add_column("projects", sa.Column("sector", sa.String(100)))
    op.add_column("projects", sa.Column("risk_rating", sa.String(20)))
    op.add_column("projects", sa.Column("assigned_to", sa.String(36)))
    op.add_column("projects", sa.Column("stage_due_date", sa.Date()))

    # Unlike opboh_assessment_status/project_status in earlier migrations
    # (both created inline as part of create_table, where SQLAlchemy's DDL
    # compiler auto-creates a referenced enum type as a dependency), a
    # bare `op.add_column` on an *existing* table does not — the type has
    # to exist before the ALTER TABLE runs, or Postgres errors with
    # "type ... does not exist" (caught by CI: the ADD COLUMN statement
    # ran with no CREATE TYPE ever having happened first).
    stage_gate_decision_kind = postgresql.ENUM(
        "advance", "reopen", name="stage_gate_decision_kind", create_type=False
    )
    stage_gate_decision_kind.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "stage_gate_decisions",
        sa.Column(
            "kind",
            stage_gate_decision_kind,
            nullable=False,
            server_default="advance",
        ),
    )
    op.alter_column(
        "stage_gate_decisions",
        "supporting_assessment_id",
        existing_type=postgresql.UUID(),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "stage_gate_decisions",
        "supporting_assessment_id",
        existing_type=postgresql.UUID(),
        nullable=False,
    )
    op.drop_column("stage_gate_decisions", "kind")
    sa.Enum(name="stage_gate_decision_kind").drop(op.get_bind(), checkfirst=True)

    op.drop_column("projects", "stage_due_date")
    op.drop_column("projects", "assigned_to")
    op.drop_column("projects", "risk_rating")
    op.drop_column("projects", "sector")

    op.drop_index(
        "ix_framework_applicability_rules_framework_id",
        table_name="framework_applicability_rules",
    )
    op.drop_table("framework_applicability_rules")
