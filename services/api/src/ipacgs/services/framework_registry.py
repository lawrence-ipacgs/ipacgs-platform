"""Epic 4 — Framework Registry service layer.

Deliberately small: registering a framework or a version is a plain insert,
not a state machine like OPBOH's assessment lifecycle. The one real rule
enforced here is "at most one active version per framework" — the same
invariant OPBOH's seed script docstring already assumed informally
(`seed_opboh_catalogue.py`'s note about marking the illustrative version
`is_active = False` once a real one replaces it); this module is what makes
that an enforced fact rather than a convention someone has to remember.
"""

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ipacgs.models.framework import Framework, FrameworkVersion


class DuplicateFrameworkCode(Exception):
    """Raised when registering a framework whose code is already taken."""


async def register_framework(
    session: AsyncSession,
    *,
    code: str,
    name: str,
    description: str | None,
    actor: str,
) -> Framework:
    existing = await session.execute(select(Framework).where(Framework.code == code))
    if existing.scalars().first() is not None:
        raise DuplicateFrameworkCode(f"A framework with code {code!r} is already registered.")

    framework = Framework(
        id=uuid.uuid4(),
        code=code,
        name=name,
        description=description,
        is_active=True,
        created_by=actor,
        updated_by=actor,
    )
    session.add(framework)
    await session.flush()
    return framework


async def create_framework_version(
    session: AsyncSession,
    framework: Framework,
    *,
    version_label: str,
    effective_from: date,
    actor: str,
) -> FrameworkVersion:
    """Created inactive by default — a version becomes the one live version
    only through `activate_framework_version`, never implicitly at
    creation. That's the opposite default from `OpbohFrameworkVersion`
    (which defaults `is_active=True`), a deliberate difference: OPBOH's
    catalogue only ever had one version in flight so far, so "active on
    creation" was harmless there; the registry expects several frameworks
    each with their own version history, where that default would let a
    half-drafted version silently start being used."""
    version = FrameworkVersion(
        id=uuid.uuid4(),
        framework_id=framework.id,
        version_label=version_label,
        effective_from=effective_from,
        is_active=False,
        created_by=actor,
        updated_by=actor,
    )
    session.add(version)
    await session.flush()
    return version


async def activate_framework_version(
    session: AsyncSession,
    version: FrameworkVersion,
    *,
    actor: str,
) -> FrameworkVersion:
    """Makes `version` the framework's one active version, deactivating any
    others — mirrors `seed_opboh_catalogue.py`'s note that only one
    version should be active for new assessments at a time, enforced here
    instead of left to whoever runs the next import to remember."""
    siblings = await session.execute(
        select(FrameworkVersion).where(
            FrameworkVersion.framework_id == version.framework_id,
            FrameworkVersion.id != version.id,
            FrameworkVersion.is_active.is_(True),
        )
    )
    for sibling in siblings.scalars().all():
        sibling.is_active = False
        sibling.updated_by = actor

    version.is_active = True
    version.updated_by = actor
    await session.flush()
    return version
