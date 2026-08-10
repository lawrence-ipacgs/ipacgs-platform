"""Legal entities — sponsors, funders, contractors, chambers of commerce
(UACOC), KMI Africa itself. `FR-MDM-002`.

Deliberately thin for Milestone 1.1: enough to identify and register an
organisation and confirm it's real (S4 — Sponsor & Entity Readiness). Fields
that belong to a *specific framework's* assessment of an organisation
(beneficial ownership verification, financial capacity scoring, ...) live in
Epic 3's OPBOH tables, not here — this table is the shared fact, not any one
framework's opinion about it.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from ipacgs.models.base import AuditedMixin, Base, TenantScopedMixin


class Organisation(Base, TenantScopedMixin, AuditedMixin):
    __tablename__ = "organisations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    legal_name: Mapped[str] = mapped_column(String(255), nullable=False)
    registration_number: Mapped[str | None] = mapped_column(String(100))
    country_of_registration: Mapped[str | None] = mapped_column(String(2))  # ISO 3166-1 alpha-2
    incorporation_date: Mapped[date | None] = mapped_column(Date)

    # Free-text for Milestone 1.1; becomes a controlled vocabulary once a
    # second organisation type shows up that needs one (e.g. distinguishing
    # UACOC's "chamber of commerce" from a project sponsor's "private company").
    organisation_type: Mapped[str | None] = mapped_column(String(100))

    is_own_tenant_entity: Mapped[bool] = mapped_column(
        default=False,
        doc="True for the organisation record representing the tenant's own "
        "legal entity (e.g. KMI Africa's own KMI Africa row) — distinguishes "
        "'us' from every other organisation this tenant registers.",
    )


class OrganisationDuplicateCheck(Base):
    """FR-MDM-005 — records that a duplicate check was performed and its
    result, so the check itself is auditable, not just its outcome."""

    __tablename__ = "organisation_duplicate_checks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organisations.id"), nullable=False
    )
    matched_organisation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organisations.id")
    )
    match_confidence: Mapped[float | None] = mapped_column()
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    checked_by: Mapped[str] = mapped_column(nullable=False)
