"""Stage Checklist Engine — the real per-stage entry/exit criteria that
`services/stage_engine.py`'s own docstring has been describing as a gap since
Epic 5: `advance_stage` used to require an *accepted OPBOH assessment* to leave
ANY stage, unconditionally, which is the wrong rule for UACOC's seven real
`INTK-*` intake stages (`scripts/seed_stages.py`) — their own documented gate is
administrative approval against stage-specific criteria, not an OPBOH-style
compliance assessment.

Same architectural shape this codebase already uses twice — OPBOH's
catalogue -> response -> decision (`models/opboh.py`), and the Gate Engine's
definition -> decision (`models/gate.py`) — applied to a third, genuinely
different kind of gate: an administrative checklist, not a scored assessment
and not a quorum vote. Deliberately configuration, not code, same reasoning as
`Stage` itself and `OpbohQuestion`: which stages get a checklist, and what's on
it, is a data question, not a code question — a stage with no active
`StageChecklistItem` rows simply falls back to `stage_engine.advance_stage`'s
older OPBOH-assessment path unchanged, which is exactly where a future
OPBOH-gated stage (the docstring names Phase 2's "Diagnostic Assessment," the
step right after Onboarding, as the one place OPBOH plausibly belongs) will
keep working with zero code change.

`StageChecklistItem.criterion` content is sourced verbatim (lightly trimmed)
from each INTK stage's own Exit Criteria panel in
`docs/Project Intake Full Process Map.pdf` — see `scripts/seed_stage_checklists.py`
for the transcription. `StageDecisionOutcome`'s seven values are the union of
two decision vocabularies KMI shared in
`docs/Combined_Project_Admission_and_Onboarding_Publication FV1.docx`: Section
33.1's "Initial Admission Outcome" (5 options) and Section 27's "Onboarding
Decision" (7 options, a superset — adds Require Due Diligence and Hold/Pending).
Only PROCEED and PROCEED_WITH_CONDITIONS let `advance_stage` succeed; the other
five are real, named ways to *not* proceed, not just an implicit "anything else
blocks."
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ipacgs.models.base import AuditedMixin, Base, TenantScopedMixin

_VALUES_CALLABLE = lambda enum_cls: [e.value for e in enum_cls]  # noqa: E731


class ChecklistResponseValue(StrEnum):
    """Yes / No / Not Applicable — mirrors `OpbohResponseValue`'s vocabulary
    (`models/opboh.py`) and Section 33's own "Admission & Onboarding Screen"
    table shape exactly, but kept as its own type rather than importing
    OPBOH's: this checklist isn't an OPBOH response and shouldn't be able to
    silently start meaning one just because the three values happen to
    coincide — same reasoning `opboh_scoring.ResponseValue`'s own docstring
    gives for not importing the ORM enum into that module either."""

    YES = "yes"
    NO = "no"
    NOT_APPLICABLE = "not_applicable"


class StageChecklistItem(Base, AuditedMixin):
    """Configuration, not code. Not tenant-scoped — same reasoning as `Stage`
    itself: the checklist content is shared platform configuration, not
    per-tenant data."""

    __tablename__ = "stage_checklist_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    stage_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stages.id"), nullable=False
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    criterion: Mapped[str] = mapped_column(
        Text, nullable=False, doc="The exit criterion itself, as the Process Map states it."
    )
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)


class StageChecklistResponse(Base, TenantScopedMixin, AuditedMixin):
    """One project's answer to one checklist item. Upsert semantics on
    (project_id, item_id) — same pattern as `OpbohResponse`'s
    (assessment_id, question_id) uniqueness in `services/opboh_workflow.py`'s
    caller (`api/routes/opboh.py`'s `upsert_response`)."""

    __tablename__ = "stage_checklist_responses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stage_checklist_items.id"), nullable=False
    )
    item: Mapped["StageChecklistItem"] = relationship()

    response_value: Mapped[ChecklistResponseValue | None] = mapped_column(
        Enum(
            ChecklistResponseValue,
            name="checklist_response_value",
            values_callable=_VALUES_CALLABLE,
        ),
        doc="Null until answered.",
    )
    # Free text, not an OpbohResponseEvidence-style evidence-document link —
    # a deliberately smaller mechanism for this first slice. A real gap, not
    # silently worked around: see services/stage_engine.py's module docstring.
    comment: Mapped[str | None] = mapped_column(Text)
    answered_by: Mapped[str | None] = mapped_column(String(36))
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class StageDecisionOutcome(StrEnum):
    PROCEED = "proceed"
    PROCEED_WITH_CONDITIONS = "proceed_with_conditions"
    RETURN_FOR_INFORMATION = "return_for_information"
    REQUIRE_DUE_DILIGENCE = "require_due_diligence"
    ESCALATE_FOR_SPECIALIST_REVIEW = "escalate_for_specialist_review"
    HOLD_PENDING = "hold_pending"
    DECLINE = "decline"


class StageDecision(Base, TenantScopedMixin):
    """One recorded admission decision for one (project, stage). Deliberately
    no `AuditedMixin` — an immutable event, not a row anyone should be
    editing after the fact, same reasoning `StageGateDecision` documents for
    itself (`models/project.py`)."""

    __tablename__ = "stage_decisions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False
    )
    stage_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stages.id"), nullable=False
    )
    outcome: Mapped[StageDecisionOutcome] = mapped_column(
        Enum(StageDecisionOutcome, name="stage_decision_outcome", values_callable=_VALUES_CALLABLE),
        nullable=False,
    )
    conditions: Mapped[str | None] = mapped_column(
        Text, doc="Section 27's 'Conditions / Outstanding Requirements'."
    )
    decided_by: Mapped[str] = mapped_column(String(36), nullable=False)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
