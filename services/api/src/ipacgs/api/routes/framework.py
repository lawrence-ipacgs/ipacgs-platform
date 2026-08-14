"""Framework Registry HTTP routes — Epic 4.

Role-based authorization is not wired in yet, same gap and same reason as
`api/routes/opboh.py`: the Entra ID app roles it would check against don't
exist until `infra/scripts/create-app-registrations.sh` is run. Every
route still requires a valid authenticated identity.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ipacgs.api.schemas.framework import (
    CreateFrameworkRequest,
    CreateFrameworkVersionRequest,
    FrameworkOut,
    FrameworkVersionOut,
)
from ipacgs.core.db import get_db
from ipacgs.core.security import CurrentUser, get_current_user
from ipacgs.models.framework import Framework, FrameworkVersion
from ipacgs.services import framework_registry

router = APIRouter(prefix="/frameworks", tags=["frameworks"])


async def _get_framework_or_404(session: AsyncSession, framework_id: uuid.UUID) -> Framework:
    framework = await session.get(Framework, framework_id)
    if framework is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No framework {framework_id}.")
    return framework


async def _get_version_or_404(
    session: AsyncSession, framework_id: uuid.UUID, version_id: uuid.UUID
) -> FrameworkVersion:
    version = await session.get(FrameworkVersion, version_id)
    if version is None or version.framework_id != framework_id:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"No version {version_id} for framework {framework_id}.",
        )
    return version


@router.post("", response_model=FrameworkOut, status_code=status.HTTP_201_CREATED)
async def create_framework(
    body: CreateFrameworkRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> Framework:
    framework = await framework_registry.register_framework(
        db,
        code=body.code,
        name=body.name,
        description=body.description,
        actor=user.object_id,
    )
    await db.commit()
    await db.refresh(framework)
    return framework


@router.get("", response_model=list[FrameworkOut])
async def list_frameworks(db: AsyncSession = Depends(get_db)) -> list[Framework]:
    result = await db.execute(select(Framework).order_by(Framework.code))
    return list(result.scalars().all())


@router.get("/{framework_id}", response_model=FrameworkOut)
async def get_framework(framework_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> Framework:
    return await _get_framework_or_404(db, framework_id)


@router.post(
    "/{framework_id}/versions",
    response_model=FrameworkVersionOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_version(
    framework_id: uuid.UUID,
    body: CreateFrameworkVersionRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> FrameworkVersion:
    framework = await _get_framework_or_404(db, framework_id)
    version = await framework_registry.create_framework_version(
        db,
        framework,
        version_label=body.version_label,
        effective_from=body.effective_from,
        actor=user.object_id,
    )
    await db.commit()
    await db.refresh(version)
    return version


@router.get("/{framework_id}/versions", response_model=list[FrameworkVersionOut])
async def list_versions(
    framework_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> list[FrameworkVersion]:
    await _get_framework_or_404(db, framework_id)
    result = await db.execute(
        select(FrameworkVersion)
        .where(FrameworkVersion.framework_id == framework_id)
        .order_by(FrameworkVersion.effective_from)
    )
    return list(result.scalars().all())


@router.post("/{framework_id}/versions/{version_id}/activate", response_model=FrameworkVersionOut)
async def activate_version(
    framework_id: uuid.UUID,
    version_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> FrameworkVersion:
    version = await _get_version_or_404(db, framework_id, version_id)
    await framework_registry.activate_framework_version(db, version, actor=user.object_id)
    await db.commit()
    await db.refresh(version)
    return version
