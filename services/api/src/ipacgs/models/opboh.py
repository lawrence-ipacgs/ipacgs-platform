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

The catalogue content (domains/questions) is still illustrative — see
`scripts/seed_opboh_catalogue.py`. What changed since Epic 3: the response
shape (`OpbohResponseValue`, the 0-5 `score` scale, and
`evidence_sufficiency_factor`) and the persisted `assurance_score` on
`OpbohAssessment` are now real, sourced from an OPBOH Full-Cycle Assessment
Module v1.1 overview KMI shared (`docs/IMG-20260814-WA0011.jpg`) — a
summary infographic, not the underlying question bank, so the exact
Y/N/N-A-to-score relationship and how a reviewer arrives at a specific
evidence factor are this codebase's own documented interpretation, not
confirmed spec. See `services/opboh_scoring.py`.
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
from sqlalchemy.orm import Mapped, mapped_column, relationship

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
    # Nullable, not required: tightening this to NOT NULL would force every
    # existing test fixture that builds an OpbohFrameworkVersion directly
    # (there are several, across test_opboh_scoring.py, workflow, routes)
    # to also construct a Framework row it has no other use for. Migration
    # `0003_framework_registry` backfills every pre-existing row to point
    # at a registered Framework(code="OPBOH") — this column is null only
    # for rows created without going through the registry, which after
    # that migration should be none. A known, flagged gap, same pattern as
    # OpbohAssessment.organisation_id's placeholder-until-Epic-5 note below.
    framework_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("frameworks.id")
    )
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
    # domain level, not just the question level. Default rescaled from 0.6
    # to 3.0 ("Moderate" or better) to match the real 0-5 response scale —
    # see OpbohResponse.score's docstring.
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    min_score_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=3.0)

    questions: Mapped[list["OpbohQuestion"]] = relationship(
        back_populates="domain", order_by="OpbohQuestion.sequence"
    )


class OpbohQuestion(Base):
    __tablename__ = "opboh_questions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    domain_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("opboh_domains.id"), nullable=False
    )
    domain: Mapped["OpbohDomain"] = relationship(back_populates="questions")
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
        default=5.0,
        doc="Minimum response score (0-5 scale) counted as a pass for this question. "
        "Default rescaled from 1.0 to 5.0 — see OpbohResponse.score's docstring.",
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
    # Tied to Organisation, not (only) a Project, because Milestone 1.1's
    # earliest OPBOH assessments genuinely predate any Project existing —
    # sponsor/opportunity screening happens before there's a project to
    # attach to. Epic 5 added project_id below rather than replacing this:
    # both stay populated where they apply, organisation_id never becomes
    # optional. See models/project.py's module docstring for why the FK
    # points at OpbohAssessment specifically rather than a generic
    # "Assessment" table that doesn't exist yet.
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organisations.id"), nullable=False
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id")
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

    # Renamed from overall_score — real, from docs/IMG-20260814-WA0011.jpg:
    # this is the Assurance Score specifically (0-100 = weighted score
    # achieved x evidence sufficiency factor), not the raw 0-5 weighted
    # domain average, which `services/opboh_scoring.py`'s AssessmentResult
    # still calls overall_score. See that module for both formulas.
    assurance_score: Mapped[float | None] = mapped_column(Float, doc="0-100. See opboh_scoring.py.")
    has_critical_failure: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    decision_summary: Mapped[str | None] = mapped_column(Text)


class OpbohResponseValue(StrEnum):
    """Real — from the OPBOH Full-Cycle Assessment Module v1.1 overview
    (`docs/IMG-20260814-WA0011.jpg`): every question's primary answer is
    Yes / No / Not Applicable, distinct from the 0-5 `score`. NOT_APPLICABLE
    questions are excluded from domain scoring entirely rather than scored
    zero — `services/opboh_scoring.py` documents that interpretation, since
    the source material doesn't spell out the exact Y/N/N-A-to-score
    relationship."""

    YES = "yes"
    NO = "no"
    NOT_APPLICABLE = "not_applicable"


class OpbohResponse(Base, AuditedMixin):
    __tablename__ = "opboh_responses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("opboh_assessments.id"), nullable=False
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("opboh_questions.id"), nullable=False
    )

    response_value: Mapped[OpbohResponseValue | None] = mapped_column(
        Enum(OpbohResponseValue, name="opboh_response_value", values_callable=_VALUES_CALLABLE),
        doc="Yes/No/Not Applicable. Null until answered.",
    )
    score: Mapped[int | None] = mapped_column(
        Integer,
        doc="0-5 Likert scale (real — 0 None/Not Met, 1 Minimal, 2 Limited, 3 Moderate, "
        "4 Substantial, 5 Fully Met, per docs/IMG-20260814-WA0011.jpg). Null until answered, "
        "and meaningless when response_value is NOT_APPLICABLE.",
    )
    # Real — the source infographic's "Evidence Sufficiency Factor (0.5-1.0)",
    # a continuous multiplier in the real Assurance Score formula. Replaces
    # the old plain evidence_sufficient boolean (Epic 3); how a reviewer
    # actually arrives at a specific number in that range isn't specified
    # anywhere shared so far, so this is a plain input field, not computed.
    evidence_sufficiency_factor: Mapped[float | None] = mapped_column(
        Float, doc="0.5-1.0. Null until evidence has been reviewed for this response."
    )
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
