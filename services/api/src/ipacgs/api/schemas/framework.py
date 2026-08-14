"""Request/response shapes for the Framework Registry routes."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class CreateFrameworkRequest(BaseModel):
    code: str
    name: str
    description: str | None = None


class FrameworkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class CreateFrameworkVersionRequest(BaseModel):
    version_label: str
    effective_from: date


class FrameworkVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    framework_id: uuid.UUID
    version_label: str
    effective_from: date
    effective_until: date | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
