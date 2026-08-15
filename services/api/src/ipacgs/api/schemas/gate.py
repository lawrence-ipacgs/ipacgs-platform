"""Request/response shapes for the Gate Engine routes."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from ipacgs.models.gate import GateDecisionStatus, GateVoteOutcome
from ipacgs.services.stage_engine import RagStatus


class GateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    description: str | None
    sequence: int
    trigger_stage_id: uuid.UUID
    required_quorum: int
    is_active: bool


class ReadinessPackOut(BaseModel):
    project_id: uuid.UUID
    gate_code: str
    rag_status: RagStatus
    open_finding_count: int


class GateVoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    voter: str
    outcome: GateVoteOutcome
    voted_at: datetime
    notes: str | None


class GateCertificateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    gate_decision_id: uuid.UUID
    content_hash: str
    issued_at: datetime


class GateDecisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    gate_id: uuid.UUID
    status: GateDecisionStatus
    opened_by: str
    decided_at: datetime | None
    suspended_at: datetime | None
    suspended_by: str | None
    suspension_reason: str | None
    votes: list[GateVoteOut]
    certificate: GateCertificateOut | None


class CastVoteRequest(BaseModel):
    outcome: GateVoteOutcome
    notes: str | None = None


class SuspendGateDecisionRequest(BaseModel):
    reason: str
