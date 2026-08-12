"""Evidence + OPBOH — Epic 3 / FR-EVD-004…005, FW-OPBOH-001…015

Written by hand, same caveat as 0001: no live database to autogenerate
against in this sandbox — review carefully against ipacgs/models/ before
the first real deploy.

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-12
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -- Evidence ------------------------------------------------------
    op.create_table(
        "evidence_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("document_type", sa.String(100)),
        sa.Column("source", sa.String(255)),
        sa.Column("blob_uri", sa.String(1024)),
        sa.Column("file_hash", sa.String(128)),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("superseded_by_id", postgresql.UUID(as_uuid=True)),
        sa.Column(
            "status",
            sa.Enum(
                "requested",
                "submitted",
                "under_review",
                "accepted",
                "rejected",
                "expired",
                "superseded",
                name="evidence_status",
            ),
            nullable=False,
            server_default="requested",
        ),
        sa.Column("valid_from", sa.Date()),
        sa.Column("valid_until", sa.Date()),
        sa.Column("is_independent_source", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("confidentiality_level", sa.String(50)),
        sa.Column("submitted_by", sa.String(36)),
        sa.Column("reviewed_by", sa.String(36)),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "requested_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
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
    op.create_foreign_key(
        "fk_evidence_documents_superseded_by",
        "evidence_documents",
        "evidence_documents",
        ["superseded_by_id"],
        ["id"],
    )
    op.create_index("ix_evidence_documents_tenant_id", "evidence_documents", ["tenant_id"])

    # -- OPBOH catalogue -------------------------------------------------
    op.create_table(
        "opboh_framework_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("version_label", sa.String(20), nullable=False, unique=True),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_until", sa.Date()),
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
        "opboh_domains",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "framework_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("opboh_framework_versions.id"),
            nullable=False,
        ),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("sequence", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("weight", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("min_score_threshold", sa.Float(), nullable=False, server_default="0.6"),
    )
    op.create_index(
        "ix_opboh_domains_framework_version_id", "opboh_domains", ["framework_version_id"]
    )

    op.create_table(
        "opboh_questions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "domain_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("opboh_domains.id"),
            nullable=False,
        ),
        sa.Column("control_objective", sa.String(500), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_critical_control", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("pass_threshold", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("evidence_required", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("evidence_type_hint", sa.String(255)),
    )
    op.create_index("ix_opboh_questions_domain_id", "opboh_questions", ["domain_id"])

    # -- OPBOH assessment instance ---------------------------------------
    op.create_table(
        "opboh_assessments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False
        ),
        sa.Column(
            "framework_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("opboh_framework_versions.id"),
            nullable=False,
        ),
        sa.Column(
            "organisation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organisations.id"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "draft",
                "evidence_requested",
                "submitted",
                "under_assessment",
                "clarification_requested",
                "independently_reviewed",
                "conditionally_accepted",
                "accepted",
                "rejected",
                "reopened",
                "superseded",
                name="opboh_assessment_status",
            ),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("prepared_by", sa.String(36), nullable=False),
        sa.Column("assessed_by", sa.String(36)),
        sa.Column("reviewed_by", sa.String(36)),
        sa.Column("approved_by", sa.String(36)),
        sa.Column("overall_score", sa.Float()),
        sa.Column("has_critical_failure", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("decision_summary", sa.Text()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("updated_by", sa.String(), nullable=False),
    )
    op.create_index("ix_opboh_assessments_tenant_id", "opboh_assessments", ["tenant_id"])
    op.create_index(
        "ix_opboh_assessments_organisation_id", "opboh_assessments", ["organisation_id"]
    )

    op.create_table(
        "opboh_responses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "assessment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("opboh_assessments.id"),
            nullable=False,
        ),
        sa.Column(
            "question_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("opboh_questions.id"),
            nullable=False,
        ),
        sa.Column("score", sa.Float()),
        sa.Column("evidence_sufficient", sa.Boolean()),
        sa.Column("notes", sa.Text()),
        sa.Column("answered_by", sa.String(36)),
        sa.Column("answered_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("updated_by", sa.String(), nullable=False),
    )
    op.create_index("ix_opboh_responses_assessment_id", "opboh_responses", ["assessment_id"])
    op.create_index("ix_opboh_responses_question_id", "opboh_responses", ["question_id"])

    op.create_table(
        "opboh_response_evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "response_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("opboh_responses.id"),
            nullable=False,
        ),
        sa.Column(
            "evidence_document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("evidence_documents.id"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_opboh_response_evidence_response_id", "opboh_response_evidence", ["response_id"]
    )
    op.create_index(
        "ix_opboh_response_evidence_evidence_document_id",
        "opboh_response_evidence",
        ["evidence_document_id"],
    )

    # -- Findings ----------------------------------------------------------
    op.create_table(
        "opboh_findings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False
        ),
        sa.Column(
            "assessment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("opboh_assessments.id"),
            nullable=False,
        ),
        sa.Column(
            "response_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("opboh_responses.id")
        ),
        sa.Column(
            "severity",
            sa.Enum("low", "medium", "high", "critical", name="finding_severity"),
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("open", "in_progress", "closed", "escalated", name="finding_status"),
            nullable=False,
            server_default="open",
        ),
        sa.Column("owner", sa.String(36)),
        sa.Column("due_date", sa.Date()),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("updated_by", sa.String(), nullable=False),
    )
    op.create_index("ix_opboh_findings_tenant_id", "opboh_findings", ["tenant_id"])
    op.create_index("ix_opboh_findings_assessment_id", "opboh_findings", ["assessment_id"])


def downgrade() -> None:
    op.drop_table("opboh_findings")
    op.drop_table("opboh_response_evidence")
    op.drop_table("opboh_responses")
    op.drop_table("opboh_assessments")
    op.drop_table("opboh_questions")
    op.drop_table("opboh_domains")
    op.drop_table("opboh_framework_versions")
    op.drop_constraint(
        "fk_evidence_documents_superseded_by", "evidence_documents", type_="foreignkey"
    )
    op.drop_table("evidence_documents")
    sa.Enum(name="finding_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="finding_severity").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="opboh_assessment_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="evidence_status").drop(op.get_bind(), checkfirst=True)
