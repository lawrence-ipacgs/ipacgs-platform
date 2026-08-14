"""Stage Engine — Epic 5

Written by hand, same caveat as 0001-0003: no live database to
autogenerate against in this sandbox — review carefully against
ipacgs/models/ before deploying.

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-14
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "stages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(20), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("sequence", sa.Integer(), nullable=False),
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

    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False
        ),
        sa.Column(
            "organisation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organisations.id"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column(
            "current_stage_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("stages.id"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("active", "on_hold", "closed", "cancelled", name="project_status"),
            nullable=False,
            server_default="active",
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("updated_by", sa.String(), nullable=False),
    )
    op.create_index("ix_projects_tenant_id", "projects", ["tenant_id"])
    op.create_index("ix_projects_organisation_id", "projects", ["organisation_id"])
    op.create_index("ix_projects_current_stage_id", "projects", ["current_stage_id"])

    op.add_column(
        "opboh_assessments",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id")),
    )
    op.create_index("ix_opboh_assessments_project_id", "opboh_assessments", ["project_id"])

    op.create_table(
        "stage_gate_decisions",
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
            "from_stage_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("stages.id"),
            nullable=False,
        ),
        sa.Column(
            "to_stage_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stages.id"), nullable=False
        ),
        sa.Column(
            "supporting_assessment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("opboh_assessments.id"),
            nullable=False,
        ),
        sa.Column("decided_by", sa.String(36), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.Text()),
    )
    op.create_index("ix_stage_gate_decisions_tenant_id", "stage_gate_decisions", ["tenant_id"])
    op.create_index("ix_stage_gate_decisions_project_id", "stage_gate_decisions", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_stage_gate_decisions_project_id", table_name="stage_gate_decisions")
    op.drop_index("ix_stage_gate_decisions_tenant_id", table_name="stage_gate_decisions")
    op.drop_table("stage_gate_decisions")
    op.drop_index("ix_opboh_assessments_project_id", table_name="opboh_assessments")
    op.drop_column("opboh_assessments", "project_id")
    op.drop_index("ix_projects_current_stage_id", table_name="projects")
    op.drop_index("ix_projects_organisation_id", table_name="projects")
    op.drop_index("ix_projects_tenant_id", table_name="projects")
    op.drop_table("projects")
    op.drop_table("stages")
    sa.Enum(name="project_status").drop(op.get_bind(), checkfirst=True)
