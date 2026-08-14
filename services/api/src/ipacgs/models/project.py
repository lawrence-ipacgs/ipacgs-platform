"""Epic 5 — Stage Engine.

`OpbohAssessment.organisation_id` (`models/opboh.py`) has carried a comment
since Epic 3 explaining it's tied to an Organisation rather than a Project
"because no Project model exists yet ... revisit once Epic 5 introduces a
real Project entity." This module is that entity, plus the stage-gate
mechanism PRN-001 depends on: a project's progression from one stage to the
next is a decision, backed by an accepted assessment, made by someone,
recorded — never just a date passing.

Two design choices worth calling out:

1. `Stage` is configuration (a DB table with an order), not a hardcoded
   enum — the exact stage names/count in KMI Africa's real SRS aren't
   confirmed source material yet (same situation OPBOH's illustrative
   catalogue is in), so baking a specific S1…S4 naming into code would be
   asserting something not actually verified. `scripts/seed_stages.py`
   seeds an explicitly illustrative sequence, same honesty as OPBOH's own
   seed script.
2. `StageGateDecision.supporting_assessment_id` points at an
   `OpbohAssessment` specifically, not a generic "Assessment" — OPBOH is
   still the only concrete assessment type that exists after Epic 4's
   Framework Registry (that epic generalized *which frameworks exist*,
   not assessment *instances* across frameworks). Narrow and concrete
   for Milestone 1.1; generalizing this FK is a real follow-up once a
   second framework has its own assessment table, not attempted here.
"""

import uuid
from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ipacgs.models.base import AuditedMixin, Base, TenantScopedMixin

_VALUES_CALLABLE = lambda enum_cls: [e.value for e in enum_cls]  # noqa: E731


class Stage(Base, AuditedMixin):
    """Not tenant-scoped — same reasoning as `Framework`/`OpbohFrameworkVersion`:
    the lifecycle sequence itself is shared platform configuration. `sequence`
    is the ordering `services/stage_engine.py` advances projects through;
    gaps are fine (10, 20, 30…), duplicates are not enforced at the DB level
    but would make "the next stage" ambiguous — keep them unique in practice."""

    __tablename__ = "stages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ProjectStatus(StrEnum):
    ACTIVE = "active"
    ON_HOLD = "on_hold"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class Project(Base, TenantScopedMixin, AuditedMixin):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organisations.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    # Free-text for Milestone 1.1, same reasoning as Organisation.organisation_type
    # — becomes a controlled vocabulary once a second sector shows up that
    # needs one. Feeds FrameworkApplicabilityRule matching (models/framework.py).
    sector: Mapped[str | None] = mapped_column(String(100))
    risk_rating: Mapped[str | None] = mapped_column(String(20))

    current_stage_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stages.id"), nullable=False
    )
    current_stage: Mapped["Stage"] = relationship()

    status: Mapped[ProjectStatus] = mapped_column(
        Enum(ProjectStatus, name="project_status", values_callable=_VALUES_CALLABLE),
        nullable=False,
        default=ProjectStatus.ACTIVE,
    )

    # Single owner, not OPBOH's full preparer/assessor/reviewer/approver
    # chain — that SOD chain already exists on whichever assessment is
    # driving this stage; this is just "who's accountable for moving the
    # stage itself forward", reset on every advance/reopen.
    assigned_to: Mapped[str | None] = mapped_column(String(36))
    stage_due_date: Mapped[date | None] = mapped_column(Date)


class StageGateDecisionKind(StrEnum):
    ADVANCE = "advance"
    REOPEN = "reopen"


class StageGateDecision(Base, TenantScopedMixin):
    """One recorded transition — deliberately no `updated_at`/`updated_by`
    (no `AuditedMixin`): a gate decision is an immutable event, not a row
    anyone should be editing after the fact. Get the decision right before
    recording it, not after."""

    __tablename__ = "stage_gate_decisions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False
    )
    kind: Mapped[StageGateDecisionKind] = mapped_column(
        Enum(
            StageGateDecisionKind,
            name="stage_gate_decision_kind",
            values_callable=_VALUES_CALLABLE,
        ),
        nullable=False,
        default=StageGateDecisionKind.ADVANCE,
    )
    from_stage_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stages.id"), nullable=False
    )
    to_stage_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stages.id"), nullable=False
    )

    # PRN-001 — "date alone never authorizes progression" — for an ADVANCE.
    # Nullable because a REOPEN is a different kind of event: withdrawing
    # confidence in prior evidence, not adding new evidence, so it has a
    # `notes` reason instead (enforced as required for REOPEN in
    # services/stage_engine.py, not at the schema level, same pattern as
    # the ADVANCE requirement already used).
    supporting_assessment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("opboh_assessments.id")
    )

    decided_by: Mapped[str] = mapped_column(String(36), nullable=False)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
