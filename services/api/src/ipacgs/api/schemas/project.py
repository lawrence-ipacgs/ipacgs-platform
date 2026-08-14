"""Request/response shapes for the Stage Engine routes."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from ipacgs.models.project import ProjectStatus


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


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    organisation_id: uuid.UUID
    name: str
    description: str | None
    current_stage_id: uuid.UUID
    status: ProjectStatus
    created_at: datetime
    updated_at: datetime


class AdvanceStageRequest(BaseModel):
    supporting_assessment_id: uuid.UUID
    notes: str | None = None


class StageGateDecisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    from_stage_id: uuid.UUID
    to_stage_id: uuid.UUID
    supporting_assessment_id: uuid.UUID
    decided_by: str
    decided_at: datetime
    notes: str | None
