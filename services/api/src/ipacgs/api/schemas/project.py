"""Request/response shapes for the Stage Engine routes."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from ipacgs.models.project import ProjectStatus, StageGateDecisionKind
from ipacgs.models.stage_checklist import ChecklistResponseValue, StageDecisionOutcome
from ipacgs.services.stage_engine import RagStatus


class StageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    description: str | None
    sequence: int
    is_active: bool


class CreateProjectRequest(BaseModel):
    organisation_id: uuid.UUID
    name: str
    description: str | None = None
    sector: str | None = None
    risk_rating: str | None = None


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    organisation_id: uuid.UUID
    name: str
    description: str | None
    sector: str | None
    risk_rating: str | None
    current_stage_id: uuid.UUID
    status: ProjectStatus
    assigned_to: str | None
    stage_due_date: date | None
    created_at: datetime
    updated_at: datetime


class AdvanceStageRequest(BaseModel):
    # Optional since the Stage Checklist Engine: a stage with its own
    # checklist configured (services/stage_engine.py) advances on a
    # recorded StageDecision instead — see that module's docstring.
    supporting_assessment_id: uuid.UUID | None = None
    notes: str | None = None


class ReopenStageRequest(BaseModel):
    target_stage_id: uuid.UUID
    reason: str


class AssignStageRequest(BaseModel):
    assigned_to: str
    due_date: date | None = None


class StageGateDecisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    kind: StageGateDecisionKind
    from_stage_id: uuid.UUID
    to_stage_id: uuid.UUID
    supporting_assessment_id: uuid.UUID | None
    decided_by: str
    decided_at: datetime
    notes: str | None


class RagOut(BaseModel):
    status: RagStatus


class ChecklistItemOut(BaseModel):
    """One checklist item paired with this project's current response to
    it (if any) — not `from_attributes`, same reasoning `ProjectSummaryOut`
    documents for itself: built by hand from two separately-queried
    pieces, not one ORM row."""

    item_id: uuid.UUID
    sequence: int
    criterion: str
    response_value: ChecklistResponseValue | None
    comment: str | None
    answered_by: str | None
    answered_at: datetime | None


class RespondChecklistRequest(BaseModel):
    response_value: ChecklistResponseValue
    comment: str | None = None


class ChecklistResponseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    item_id: uuid.UUID
    response_value: ChecklistResponseValue | None
    comment: str | None
    answered_by: str | None
    answered_at: datetime | None


class StageDecisionRequest(BaseModel):
    outcome: StageDecisionOutcome
    conditions: str | None = None


class StageDecisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    stage_id: uuid.UUID
    outcome: StageDecisionOutcome
    conditions: str | None
    decided_by: str
    decided_at: datetime


class ProjectSummaryOut(BaseModel):
    """Not from_attributes — built by hand in the route from several
    separately-computed pieces (RAG, blocking gate), same reasoning
    ScoreOut's manual construction in api/routes/opboh.py already has."""

    id: uuid.UUID
    name: str
    organisation_id: uuid.UUID
    current_stage_code: str | None
    current_stage_name: str | None
    status: ProjectStatus
    rag_status: RagStatus
    blocking_gate_code: str | None
    assigned_to: str | None
    stage_due_date: date | None
