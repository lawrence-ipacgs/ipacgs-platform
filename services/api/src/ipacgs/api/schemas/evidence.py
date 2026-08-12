import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from ipacgs.models.evidence import EvidenceStatus


class CreateEvidenceRequest(BaseModel):
    title: str
    document_type: str | None = None
    source: str | None = None
    valid_from: date | None = None
    valid_until: date | None = None
    is_independent_source: bool = False
    confidentiality_level: str | None = None


class EvidenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    document_type: str | None
    source: str | None
    version: int
    status: EvidenceStatus
    valid_from: date | None
    valid_until: date | None
    is_independent_source: bool
    confidentiality_level: str | None
    submitted_by: str | None
    reviewed_by: str | None
    reviewed_at: datetime | None


class RejectEvidenceRequest(BaseModel):
    reason: str
