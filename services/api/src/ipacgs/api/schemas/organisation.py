"""Request/response shapes for the Organisation routes."""

import uuid

from pydantic import BaseModel, ConfigDict


class OrganisationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    legal_name: str
    registration_number: str | None
    country_of_registration: str | None
    organisation_type: str | None


class CreateOrganisationRequest(BaseModel):
    legal_name: str
    country_of_registration: str | None = None
    organisation_type: str | None = None
