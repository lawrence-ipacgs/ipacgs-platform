"""OPBOH real scoring — response_value, evidence_sufficiency_factor, 0-5
score scale, assurance_score

Sourced from an OPBOH Full-Cycle Assessment Module v1.1 overview KMI shared
(docs/IMG-20260814-WA0011.jpg) — see services/opboh_scoring.py's module
docstring for the full formula this supports.

Data note: `opboh_responses.score` changes scale from the old [0.0, 1.0]
convention to the real [0, 5] one. Existing scores (illustrative test/seed
data only — nothing in dev represents a real KMI assessment yet) are on the
OLD scale; reinterpreting them as if already on the new scale would produce
silently wrong values (e.g. an old "fully passed" 1.0 truncating to a new
"Minimal" 1 instead of "Fully Met" 5), which is worse than clearing them.
This migration nulls out every existing response's score (and the now
gone evidence_sufficient) rather than attempting a numeric conversion that
can't actually preserve meaning. Same reasoning for
opboh_domains.min_score_threshold and opboh_questions.pass_threshold: both
are rescaled x5 in place (correct, not lossy — every value currently in the
table was seeded under the old [0,1] convention, so a straight x5 preserves
their relative meaning exactly) rather than nulled.

Written by hand, same caveat as every migration before it: no live
database to autogenerate against in this sandbox — review carefully
against ipacgs/models/ before deploying.

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-15
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Existing response scores are on the old [0,1] scale — clear them
    # before retyping the column, rather than let a numeric cast silently
    # reinterpret them on the new [0,5] scale. See module docstring.
    op.execute(sa.text("UPDATE opboh_responses SET score = NULL"))
    op.alter_column(
        "opboh_responses",
        "score",
        existing_type=sa.Float(),
        type_=sa.Integer(),
        postgresql_using="score::integer",
    )

    op.drop_column("opboh_responses", "evidence_sufficient")
    op.add_column("opboh_responses", sa.Column("evidence_sufficiency_factor", sa.Float()))

    # Enum type must exist before add_column references it on this
    # pre-existing table — op.add_column doesn't auto-create a referenced
    # enum the way op.create_table does. See migration 0005's own note.
    opboh_response_value = postgresql.ENUM(
        "yes", "no", "not_applicable", name="opboh_response_value", create_type=False
    )
    opboh_response_value.create(op.get_bind(), checkfirst=True)
    op.add_column("opboh_responses", sa.Column("response_value", opboh_response_value))

    # Rescale existing illustrative thresholds x5 onto the real 0-5 scale —
    # correct, not lossy, since everything currently seeded used the old
    # [0,1] convention. See scripts/seed_opboh_catalogue.py's own docstring
    # for the same rescale applied to its Python source values.
    op.execute(sa.text("UPDATE opboh_domains SET min_score_threshold = min_score_threshold * 5"))
    op.execute(sa.text("UPDATE opboh_questions SET pass_threshold = pass_threshold * 5"))

    op.alter_column("opboh_assessments", "overall_score", new_column_name="assurance_score")


def downgrade() -> None:
    op.alter_column("opboh_assessments", "assurance_score", new_column_name="overall_score")

    op.execute(sa.text("UPDATE opboh_questions SET pass_threshold = pass_threshold / 5"))
    op.execute(sa.text("UPDATE opboh_domains SET min_score_threshold = min_score_threshold / 5"))

    op.drop_column("opboh_responses", "response_value")
    sa.Enum(name="opboh_response_value").drop(op.get_bind(), checkfirst=True)

    op.drop_column("opboh_responses", "evidence_sufficiency_factor")
    op.add_column("opboh_responses", sa.Column("evidence_sufficient", sa.Boolean()))

    op.execute(sa.text("UPDATE opboh_responses SET score = NULL"))
    op.alter_column(
        "opboh_responses",
        "score",
        existing_type=sa.Integer(),
        type_=sa.Float(),
    )
