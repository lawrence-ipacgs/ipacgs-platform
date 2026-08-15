"""Request/response shapes for the OPBOH routes. Kept separate from the
ORM models on purpose — what a client sends and receives is its own
contract, not automatically whatever the database schema happens to be."""

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ipacgs.models.opboh import (
    FindingSeverity,
    FindingStatus,
    OpbohAssessmentStatus,
    OpbohResponseValue,
)


class CreateAssessmentRequest(BaseModel):
    organisation_id: uuid.UUID
    framework_version_id: uuid.UUID | None = Field(
        default=None, description="Defaults to the current active OPBOH version if omitted."
    )
    project_id: uuid.UUID | None = Field(
        default=None,
        description="Links this assessment to a Project (Epic 5) so its stage-gate "
        "decisions and RAG status can reference it. Optional — screening assessments "
        "genuinely predate any Project existing.",
    )


class AssessmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    organisation_id: uuid.UUID
    project_id: uuid.UUID | None
    framework_version_id: uuid.UUID
    status: OpbohAssessmentStatus
    prepared_by: str
    assessed_by: str | None
    reviewed_by: str | None
    approved_by: str | None
    assurance_score: float | None = Field(description="0-100. See services/opboh_scoring.py.")
    has_critical_failure: bool
    decision_summary: str | None
    created_at: datetime
    updated_at: datetime


class UpsertResponseRequest(BaseModel):
    question_id: uuid.UUID
    response_value: OpbohResponseValue
    score: int = Field(ge=0, le=5, description="0-5 Likert scale — see OpbohResponse.score.")
    evidence_sufficiency_factor: float | None = Field(default=None, ge=0.5, le=1.0)
    notes: str | None = None
    evidence_document_ids: list[uuid.UUID] = Field(default_factory=list)


class ResponseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    assessment_id: uuid.UUID
    question_id: uuid.UUID
    response_value: OpbohResponseValue | None
    score: int | None
    evidence_sufficiency_factor: float | None
    notes: str | None
    answered_by: str | None
    answered_at: datetime | None


class DecideRequest(BaseModel):
    decision: Literal["accepted", "conditionally_accepted", "rejected"]
    decision_summary: str | None = None


class CriticalFailureOut(BaseModel):
    question_id: str
    control_objective: str
    reason: str


class DomainResultOut(BaseModel):
    domain_id: str
    name: str
    score: float = Field(description="0-5, weighted average of this domain's answered questions.")
    meets_threshold: bool
    critical_failures: list[CriticalFailureOut]
    unanswered_count: int


class ScoreOut(BaseModel):
    overall_score: float = Field(description="0-5, weighted across domains.")
    evidence_sufficiency_factor: float = Field(description="0.5-1.0, aggregated across responses.")
    assurance_score: float = Field(description="0-100 = (overall_score/5*100) x evidence factor.")
    rag: str = Field(description="red/amber/green — the real Assurance Score banding.")
    is_clean: bool
    has_critical_failure: bool
    domain_results: list[DomainResultOut]


class FindingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    assessment_id: uuid.UUID
    response_id: uuid.UUID | None
    severity: FindingSeverity
    description: str
    status: FindingStatus
    owner: str | None
    due_date: date | None
    closed_at: datetime | None


class AssignFindingRequest(BaseModel):
    owner: str
    due_date: date
