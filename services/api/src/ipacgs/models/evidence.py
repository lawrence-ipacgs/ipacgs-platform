"""Evidence — `FR-EVD-001…005`, the minimal slice of Epic 1 that Epic 3
(OPBOH) actually needs to function: a document record with the review-state
machine Figure 2 of the architecture document describes, not the full
blob-upload/malware-scan/data-room wiring (`FR-EVD-006…007`), which stays a
separate follow-up.

Evidence is deliberately generic, not owned by OPBOH — Framework
Orchestration Rule 3 ("no framework may create a duplicate fact; all
frameworks must reference shared master records") means the same evidence
item (a certificate of incorporation, say) should be reusable across
whichever questions, in whichever frameworks, actually need it. The link to
what an evidence item is evidence *for* lives on the linking table on the
consuming side (see `models/opboh.py`'s `OpbohResponseEvidence`), not here.
"""

import uuid
from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from ipacgs.models.base import AuditedMixin, Base, TenantScopedMixin


class EvidenceStatus(StrEnum):
    """Figure 2's states: submitted → (extraction, if AI-assisted) → human
    review → accepted/rejected. REQUESTED exists for the case where the
    platform is asking for something that hasn't been provided yet."""

    REQUESTED = "requested"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"
    SUPERSEDED = "superseded"


_VALUES_CALLABLE = lambda enum_cls: [e.value for e in enum_cls]  # noqa: E731


class EvidenceDocument(Base, TenantScopedMixin, AuditedMixin):
    __tablename__ = "evidence_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    document_type: Mapped[str | None] = mapped_column(
        String(100), doc="Free text for now, e.g. 'certificate_of_incorporation', 'id_document'."
    )
    source: Mapped[str | None] = mapped_column(String(255), doc="Who/where this came from.")

    # Storage wiring deferred — FR-EVD-001…003 (upload, malware scan,
    # hashing against Azure Blob) is not built yet. This column exists so
    # the review-state machine and scoring engine have something real to
    # point at once it is.
    blob_uri: Mapped[str | None] = mapped_column(String(1024))
    file_hash: Mapped[str | None] = mapped_column(String(128))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    superseded_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evidence_documents.id")
    )

    status: Mapped[EvidenceStatus] = mapped_column(
        Enum(EvidenceStatus, name="evidence_status", values_callable=_VALUES_CALLABLE),
        nullable=False,
        default=EvidenceStatus.REQUESTED,
    )

    # Sufficiency dimensions — FW-OPBOH-004: type/source/owner/validity/
    # freshness/independence/confidentiality.
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_until: Mapped[date | None] = mapped_column(
        Date, doc="Freshness — null means no expiry tracked."
    )
    is_independent_source: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    confidentiality_level: Mapped[str | None] = mapped_column(String(50))

    submitted_by: Mapped[str | None] = mapped_column(String(36))
    reviewed_by: Mapped[str | None] = mapped_column(String(36))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
