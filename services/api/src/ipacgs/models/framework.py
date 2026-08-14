"""Epic 4 — Framework Registry.

OPBOH (`models/opboh.py`) was built as its own, framework-specific set of
tables — the fastest path to a working assurance engine, but one that gives
the platform no generic notion of "a framework" independent of OPBOH itself.
The 7-layer architecture document's Layer 3 calls for multiple framework
assurance engines, not just one, so a second framework arriving later
shouldn't mean a second copy-pasted `*_framework_versions` table.

This module adds that generic layer without touching OPBOH's own tables
beyond one new FK: `Framework` / `FrameworkVersion` are what other
frameworks register into, and `OpbohFrameworkVersion.framework_id` (see
`models/opboh.py`) is OPBOH's own link back into it. Existing OPBOH rows
are backfilled to point at a registered `Framework(code="OPBOH")` by
migration `0003_framework_registry` — see that file for why the FK stays
nullable rather than required.
"""

import uuid
from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ipacgs.models.base import AuditedMixin, Base


class Framework(Base, AuditedMixin):
    """Not tenant-scoped — same reasoning as `OpbohFrameworkVersion`: which
    frameworks exist is shared platform configuration, not a per-tenant
    fact. `is_active` here means "available to register new versions
    against / start assessments under", independent of any one version's
    own `is_active` flag."""

    __tablename__ = "frameworks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True, doc="Short stable identifier, e.g. 'OPBOH'."
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    versions: Mapped[list["FrameworkVersion"]] = relationship(
        back_populates="framework", order_by="FrameworkVersion.effective_from"
    )


class FrameworkVersion(Base, AuditedMixin):
    """The registry's own version record — deliberately thin. A framework
    that needs OPBOH-style domains/questions/scoring still defines those
    itself (see `OpbohDomain`/`OpbohQuestion`); this table only tracks that
    the version exists, when it applies, and whether it's the one currently
    live. `version_label` is unique per framework, not globally — two
    different frameworks are free to both have a "1.0"."""

    __tablename__ = "framework_versions"
    __table_args__ = (
        UniqueConstraint("framework_id", "version_label", name="uq_framework_version_label"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    framework_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("frameworks.id"), nullable=False
    )
    framework: Mapped["Framework"] = relationship(back_populates="versions")

    version_label: Mapped[str] = mapped_column(String(20), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_until: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class FrameworkApplicabilityRule(Base, AuditedMixin):
    """Epic 4's real ticket list (FR-AGA-001…002) calls for applicability
    "by sector / jurisdiction / risk / stage" — a full rules engine across
    all four dimensions. This is deliberately a smaller MVP slice: sector
    only, no jurisdiction/risk matching yet, and a framework with zero
    rules is treated as applicable to every project by default (matches
    how OPBOH already behaves today — any org can start an OPBOH
    assessment unconditionally, no rule gates it). A framework gets
    filtered only once it actually has rules recorded against it. Not
    tenant-scoped, same reasoning as Framework/Stage: shared platform
    configuration.
    """

    __tablename__ = "framework_applicability_rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    framework_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("frameworks.id"), nullable=False
    )
    sector: Mapped[str | None] = mapped_column(
        String(100), doc="Null means this rule matches any sector."
    )
