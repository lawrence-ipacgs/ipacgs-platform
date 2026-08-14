"""Framework Registry — Epic 4

Written by hand, same caveat as 0001/0002: no live database to
autogenerate against in this sandbox — review carefully against
ipacgs/models/ before deploying.

Backfills a `frameworks` row for OPBOH itself and points every existing
`opboh_framework_versions` row at it, so the registry isn't empty on day
one — OPBOH becomes the first framework registered into it, not a
special case sitting outside it. The row's id is a fixed literal
(generated once, here) rather than `gen_random_uuid()`/`uuid_generate_v4()`
so this migration doesn't depend on an extension (pgcrypto/uuid-ossp)
that was never explicitly enabled anywhere in this repo's Bicep or
migrations.

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-14
"""

import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OPBOH_FRAMEWORK_ID = uuid.UUID("8f14e45f-ceea-4c94-8b8a-9a5b1e6f5a01")


def upgrade() -> None:
    op.create_table(
        "frameworks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(50), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
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
        "framework_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "framework_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("frameworks.id"),
            nullable=False,
        ),
        sa.Column("version_label", sa.String(20), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_until", sa.Date()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("updated_by", sa.String(), nullable=False),
        sa.UniqueConstraint("framework_id", "version_label", name="uq_framework_version_label"),
    )
    op.create_index("ix_framework_versions_framework_id", "framework_versions", ["framework_id"])

    op.add_column(
        "opboh_framework_versions",
        sa.Column("framework_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("frameworks.id")),
    )
    op.create_index(
        "ix_opboh_framework_versions_framework_id",
        "opboh_framework_versions",
        ["framework_id"],
    )

    # Register OPBOH itself, then backfill every pre-existing catalogue
    # version to point at it. Real bind parameters, not an f-string —
    # bandit's B608 correctly flags string-built SQL as a pattern
    # regardless of whether the interpolated value happens to be a
    # hardcoded constant here; a genuinely parameterized statement is the
    # actually-safe version of this, not a suppressed warning about one
    # that only happens to be safe today.
    op.execute(
        sa.text(
            "INSERT INTO frameworks "
            "(id, code, name, description, is_active, created_by, updated_by) "
            "VALUES (:id, :code, :name, :description, :is_active, :created_by, :updated_by)"
        ).bindparams(
            sa.bindparam("id", value=_OPBOH_FRAMEWORK_ID, type_=postgresql.UUID(as_uuid=True)),
            sa.bindparam("code", value="OPBOH"),
            sa.bindparam("name", value="Organisational and Project Bill of Health"),
            sa.bindparam(
                "description",
                value="IPAC rule 1001-008-01 — FW-OPBOH-001…015. See models/opboh.py.",
            ),
            sa.bindparam("is_active", value=True),
            sa.bindparam("created_by", value="migration-0003"),
            sa.bindparam("updated_by", value="migration-0003"),
        )
    )
    op.execute(
        sa.text(
            "UPDATE opboh_framework_versions SET framework_id = :framework_id "
            "WHERE framework_id IS NULL"
        ).bindparams(
            sa.bindparam(
                "framework_id", value=_OPBOH_FRAMEWORK_ID, type_=postgresql.UUID(as_uuid=True)
            )
        )
    )


def downgrade() -> None:
    op.drop_index("ix_opboh_framework_versions_framework_id", table_name="opboh_framework_versions")
    op.drop_column("opboh_framework_versions", "framework_id")
    op.drop_index("ix_framework_versions_framework_id", table_name="framework_versions")
    op.drop_table("framework_versions")
    op.drop_table("frameworks")
