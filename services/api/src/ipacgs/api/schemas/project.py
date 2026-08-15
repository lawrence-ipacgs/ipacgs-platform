"""Request/response shapes for the Stage Engine routes."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from ipacgs.models.project import ProjectStatus, StageGateDecisionKind
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
    supporting_assessment_id: uuid.UUID
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
