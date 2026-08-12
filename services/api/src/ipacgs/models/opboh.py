"""OPBOH — Organisational and Project Bill of Health Framework, IPAC rule
1001-008-01. `FW-OPBOH-001…015`.

Three layers, matching the architecture document's own description of what
this epic builds:

1. **Catalogue** (`OpbohFrameworkVersion`, `OpbohDomain`, `OpbohQuestion`) —
   the configurable, versioned definition of what OPBOH actually checks.
   `FW-OPBOH-001` (versioned) + `FW-OPBOH-003` (configurable catalogue).
2. **Assessment instance** (`OpbohAssessment`, `OpbohResponse`,
   `OpbohResponseEvidence`) — one tenant's run of that catalogue against one
   organisation, evidence-backed per response.
3. **Findings** (`OpbohFinding`) — gaps converted into owned, dated,
   escalating actions. `FW-OPBOH-008`.

Scoring and state-transition *logic* — not just the schema — lives in
`services/opboh.py`, not here; this module only defines what a state or a
score means to store, not how one is computed or when a transition is
legal.
"""

import uuid
from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from ipacgs.models.base import AuditedMixin, Base, TenantScopedMixin

_VALUES_CALLABLE = lambda enum_cls: [e.value for e in enum_cls]  # noqa: E731


# ---------------------------------------------------------------------------
# Catalogue — configuration, not code. Editing a question's wording or
# adding a domain should never require a deployment.
# ---------------------------------------------------------------------------


class OpbohFrameworkVersion(Base, AuditedMixin):
    """Not tenant-scoped — the catalogue itself is shared; which version a
    given tenant's assessments run against is a fact on `OpbohAssessment`,
    not a fact about the catalogue."""

    __tablename__ = "opboh_framework_versions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    version_label: Mapped[str] = mapped_column(
        String(20), nullable=False, unique=True, doc="e.g. '1.1'"
    )
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_until: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class OpbohDomain(Base):
    __tablename__ = "opboh_domains"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    framework_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("opboh_framework_versions.id"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Scoring configuration — FW-OPBOH-013 ("configurable ... readiness
    # thresholds"). weight shapes the composite score; min_score_threshold
    # is this domain's own RAG floor, independent of the composite —
    # exactly the "no averaging concealment" principle applied at the
    # domain level, not just the question level.
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    min_score_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.6)


class OpbohQuestion(Base):
    __tablename__ = "opboh_questions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    domain_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("opboh_domains.id"), nullable=False
    )
    control_objective: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        doc="What this question is actually checking, e.g. 'Sponsor has clear legal existence'.",
    )
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # FW-OPBOH-015 — a failed critical control blocks irreversible action
    # regardless of how the numeric score looks. This is the field that
    # makes that mechanism possible; services/opboh.py's scoring engine is
    # what actually enforces it.
    is_critical_control: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    pass_threshold: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=1.0,
        doc="Minimum response score counted as a pass for this question.",
    )

    evidence_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    evidence_type_hint: Mapped[str | None] = mapped_column(String(255))


# ---------------------------------------------------------------------------
# Assessment instance
# ---------------------------------------------------------------------------


class OpbohAssessmentStatus(StrEnum):
    """FW-OPBOH-007's controlled states, exactly as named in the SRS."""

    DRAFT = "draft"
    EVIDENCE_REQUESTED = "evidence_requested"
    SUBMITTED = "submitted"
    UNDER_ASSESSMENT = "under_assessment"
    CLARIFICATION_REQUESTED = "clarification_requested"
    INDEPENDENTLY_REVIEWED = "independently_reviewed"
    CONDITIONALLY_ACCEPTED = "conditionally_accepted"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    REOPENED = "reopened"
    SUPERSEDED = "superseded"


class OpbohAssessment(Base, TenantScopedMixin, AuditedMixin):
    __tablename__ = "opboh_assessments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    framework_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("opboh_framework_versions.id"), nullable=False
    )
    # Tied to Organisation, not a Project, because no Project model exists
    # yet in Milestone 1.1's schema (Layer 4's stage engine owns that). This
    # is a known, deliberate placeholder — see docs/architecture.md — not an
    # oversight; revisit once Epic 5 introduces a real Project entity.
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organisations.id"), nullable=False
    )

    status: Mapped[OpbohAssessmentStatus] = mapped_column(
        Enum(
            OpbohAssessmentStatus, name="opboh_assessment_status", values_callable=_VALUES_CALLABLE
        ),
        nullable=False,
        default=OpbohAssessmentStatus.DRAFT,
    )

    # SOD-001/002 / FW-OPBOH-006 — four distinct seats, exactly the chain
    # Section 5 of the architecture document names: preparer, assessor,
    # independent reviewer, approver. services/opboh.py's transition
    # functions call enforce_maker_checker() against these before recording
    # any of the transitions that need segregation.
    prepared_by: Mapped[str] = mapped_column(String(36), nullable=False)
    assessed_by: Mapped[str | None] = mapped_column(String(36))
    reviewed_by: Mapped[str | None] = mapped_column(String(36))
    approved_by: Mapped[str | None] = mapped_column(String(36))

    overall_score: Mapped[float | None] = mapped_column(Float)
    has_critical_failure: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    decision_summary: Mapped[str | None] = mapped_column(Text)


class OpbohResponse(Base, AuditedMixin):
    __tablename__ = "opboh_responses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("opboh_assessments.id"), nullable=False
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("opboh_questions.id"), nullable=False
    )

    score: Mapped[float | None] = mapped_column(Float, doc="0.0-1.0. Null until answered.")
    evidence_sufficient: Mapped[bool | None] = mapped_column(Boolean)
    notes: Mapped[str | None] = mapped_column(Text)
    answered_by: Mapped[str | None] = mapped_column(String(36))
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OpbohResponseEvidence(Base):
    """Many-to-many: a response can cite several evidence items, and — per
    Framework Orchestration Rule 3 — the same evidence item can legitimately
    back more than one question rather than being re-uploaded each time."""

    __tablename__ = "opboh_response_evidence"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    response_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("opboh_responses.id"), nullable=False
    )
    evidence_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evidence_documents.id"), nullable=False
    )


# ---------------------------------------------------------------------------
# Findings — FW-OPBOH-008
# ---------------------------------------------------------------------------


class FindingSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FindingStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    CLOSED = "closed"
    ESCALATED = "escalated"


class OpbohFinding(Base, TenantScopedMixin, AuditedMixin):
    __tablename__ = "opboh_findings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("opboh_assessments.id"), nullable=False
    )
    response_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("opboh_responses.id"),
        doc="Null for an assessment-level finding not tied to one specific question.",
    )

    severity: Mapped[FindingSeverity] = mapped_column(
        Enum(FindingSeverity, name="finding_severity", values_callable=_VALUES_CALLABLE),
        nullable=False,
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[FindingStatus] = mapped_column(
        Enum(FindingStatus, name="finding_status", values_callable=_VALUES_CALLABLE),
        nullable=False,
        default=FindingStatus.OPEN,
    )
    owner: Mapped[str | None] = mapped_column(String(36))
    due_date: Mapped[date | None] = mapped_column(Date)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
