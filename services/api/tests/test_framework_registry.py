"""Service-level Framework Registry tests. Codes are randomized per test,
same reason as test_framework_routes.py: these tests only `flush()` via
`db_session` (never `commit()`), so nothing here currently leaks across
tests — but that's an implicit property of `register_framework` never
committing, not something this file should quietly depend on staying
true forever."""

import uuid
from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ipacgs.models.framework import Framework
from ipacgs.services.framework_registry import (
    DuplicateFrameworkCode,
    activate_framework_version,
    create_framework_version,
    register_framework,
)

_ESG_NAME = "Environmental & Social Governance"


def _unique_code(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


async def _register_esg(db_session: AsyncSession, *, actor: str = "alice") -> Framework:
    return await register_framework(
        db_session, code=_unique_code("esg"), name=_ESG_NAME, description=None, actor=actor
    )


async def test_register_framework(db_session: AsyncSession) -> None:
    framework = await _register_esg(db_session)
    assert framework.code.startswith("esg-")
    assert framework.is_active is True


async def test_duplicate_code_is_rejected(db_session: AsyncSession) -> None:
    code = _unique_code("esg")
    await register_framework(db_session, code=code, name=_ESG_NAME, description=None, actor="alice")
    with pytest.raises(DuplicateFrameworkCode):
        await register_framework(
            db_session, code=code, name="A different name entirely", description=None, actor="bob"
        )


async def test_new_version_is_inactive_by_default(db_session: AsyncSession) -> None:
    framework = await _register_esg(db_session)
    version = await create_framework_version(
        db_session, framework, version_label="1.0", effective_from=date(2026, 1, 1), actor="alice"
    )
    assert version.is_active is False


async def test_activating_a_version_deactivates_its_siblings(db_session: AsyncSession) -> None:
    framework = await _register_esg(db_session)
    v1 = await create_framework_version(
        db_session, framework, version_label="1.0", effective_from=date(2026, 1, 1), actor="alice"
    )
    v2 = await create_framework_version(
        db_session, framework, version_label="2.0", effective_from=date(2026, 6, 1), actor="alice"
    )

    await activate_framework_version(db_session, v1, actor="alice")
    assert v1.is_active is True
    assert v2.is_active is False

    await activate_framework_version(db_session, v2, actor="alice")
    assert v1.is_active is False
    assert v2.is_active is True


async def test_activating_a_version_does_not_touch_other_frameworks_versions(
    db_session: AsyncSession,
) -> None:
    """Two frameworks' versions must never cross-deactivate each other —
    the sibling query is scoped by framework_id, not just "any active
    version anywhere"."""
    esg = await _register_esg(db_session)
    financial = await register_framework(
        db_session,
        code=_unique_code("fin-gov"),
        name="Financial Governance",
        description=None,
        actor="alice",
    )
    esg_version = await create_framework_version(
        db_session, esg, version_label="1.0", effective_from=date(2026, 1, 1), actor="alice"
    )
    financial_version = await create_framework_version(
        db_session, financial, version_label="1.0", effective_from=date(2026, 1, 1), actor="alice"
    )

    await activate_framework_version(db_session, esg_version, actor="alice")
    await activate_framework_version(db_session, financial_version, actor="alice")

    assert esg_version.is_active is True
    assert financial_version.is_active is True
