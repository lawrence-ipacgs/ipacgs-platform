"""Request/response shapes for the notifications routes."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from ipacgs.models.notification import NotificationKind


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    recipient: str
    kind: NotificationKind
    entity_type: str
    entity_id: uuid.UUID
    message: str
    created_at: datetime
    is_read: bool
    read_at: datetime | None
