"""Organisation HTTP routes — `FR-MDM-002`. A small, previously-missing
slice: `models/organisation.py` and the seed/test fixtures that create
`Organisation` rows directly have existed since Epic 0, but nothing exposed
listing or creating one over HTTP — every other route that needs an
`organisation_id` (OPBOH assessments, projects) has had to be given one
from outside the API entirely. `apps/web` is the first caller that actually
needs to discover or create one itself.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ipacgs.api.schemas.organisation import CreateOrganisationRequest, OrganisationOut
from ipacgs.core.db import get_db
from ipacgs.core.security import CurrentUser, get_current_user
from ipacgs.models.organisation import Organisation
from ipacgs.models.tenant import Tenant

router = APIRouter(tags=["organisations"])


@router.get("/organisations", response_model=list[OrganisationOut])
async def list_organisations(db: AsyncSession = Depends(get_db)) -> list[Organisation]:
    """Unscoped across tenants, same as every other list route in this
    repo (`GET /frameworks`, `GET /gates`, `GET /stages`, `GET /projects`)
    — real tenant-scoping is the same pre-existing, already-flagged gap
    `TenantScopedMixin`'s own docstring names."""
    result = await db.execute(select(Organisation).order_by(Organisation.legal_name))
    return list(result.scalars().all())


@router.post("/organisations", response_model=OrganisationOut, status_code=status.HTTP_201_CREATED)
async def create_organisation(
    body: CreateOrganisationRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> Organisation:
    """No request-scoped tenant resolution exists yet anywhere in this
    codebase (a real, tracked gap — see `TenantScopedMixin`'s own
    docstring) — Milestone 1.1 only has one real tenant in practice, so
    this picks whichever one exists, oldest first, same pragmatic
    "there's only one that matters yet" reasoning `create_assessment`
    already applies picking an OPBOH framework version. Fails clearly
    rather than guessing if none exists at all."""
    tenant_result = await db.execute(select(Tenant).order_by(Tenant.created_at).limit(1))
    tenant = tenant_result.scalars().first()
    if tenant is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "No tenant exists yet — nothing to register this under."
        )

    organisation = Organisation(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        legal_name=body.legal_name,
        country_of_registration=body.country_of_registration,
        organisation_type=body.organisation_type,
        created_by=user.object_id,
        updated_by=user.object_id,
    )
    db.add(organisation)
    await db.commit()
    await db.refresh(organisation)
    return organisation
