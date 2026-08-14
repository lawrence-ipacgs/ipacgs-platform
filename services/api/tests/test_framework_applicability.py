"""Service-level tests. Only flush()es via db_session — same non-leaking
caveat as test_framework_registry.py and test_stage_engine.py."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from ipacgs.models.framework import Framework, FrameworkApplicabilityRule
from ipacgs.models.organisation import Organisation
from ipacgs.models.project import Project, ProjectStatus, Stage
from ipacgs.models.tenant import Tenant
from ipacgs.services.framework_applicability import applicable_frameworks_for_project


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


async def _make_project(db_session: AsyncSession, *, sector: str | None) -> Project:
    tenant = Tenant(id=uuid.uuid4(), name="Test Tenant", slug=_unique("t"), created_by="seed")
    db_session.add(tenant)
    await db_session.flush()
    org = Organisation(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        legal_name="Test Sponsor Ltd",
        created_by="seed",
        updated_by="seed",
    )
    db_session.add(org)
    await db_session.flush()
    stage = Stage(
        id=uuid.uuid4(),
        code=_unique("stg"),
        name="Stage",
        sequence=uuid.uuid4().int % 1_000_000,
        is_active=True,
        created_by="seed",
        updated_by="seed",
    )
    db_session.add(stage)
    await db_session.flush()
    project = Project(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        organisation_id=org.id,
        name="Test Project",
        sector=sector,
        current_stage_id=stage.id,
        status=ProjectStatus.ACTIVE,
        created_by="seed",
        updated_by="seed",
    )
    db_session.add(project)
    await db_session.flush()
    return project


async def _make_framework(db_session: AsyncSession, *, is_active: bool) -> Framework:
    framework = Framework(
        id=uuid.uuid4(),
        code=_unique("fw"),
        name="Test Framework",
        is_active=is_active,
        created_by="seed",
        updated_by="seed",
    )
    db_session.add(framework)
    await db_session.flush()
    return framework


async def test_a_framework_with_no_rules_applies_to_every_project(
    db_session: AsyncSession,
) -> None:
    project = await _make_project(db_session, sector="infrastructure")
    framework = await _make_framework(db_session, is_active=True)

    applicable = await applicable_frameworks_for_project(db_session, project)

    assert framework.id in {f.id for f in applicable}


async def test_a_rule_restricts_to_matching_sector_only(db_session: AsyncSession) -> None:
    matching_project = await _make_project(db_session, sector="infrastructure")
    other_project = await _make_project(db_session, sector="agriculture")
    framework = await _make_framework(db_session, is_active=True)
    db_session.add(
        FrameworkApplicabilityRule(
            id=uuid.uuid4(),
            framework_id=framework.id,
            sector="infrastructure",
            created_by="seed",
            updated_by="seed",
        )
    )
    await db_session.flush()

    matching_result = await applicable_frameworks_for_project(db_session, matching_project)
    other_result = await applicable_frameworks_for_project(db_session, other_project)

    assert framework.id in {f.id for f in matching_result}
    assert framework.id not in {f.id for f in other_result}


async def test_a_sector_agnostic_rule_applies_to_any_project(db_session: AsyncSession) -> None:
    project = await _make_project(db_session, sector="agriculture")
    framework = await _make_framework(db_session, is_active=True)
    db_session.add(
        FrameworkApplicabilityRule(
            id=uuid.uuid4(),
            framework_id=framework.id,
            sector=None,
            created_by="seed",
            updated_by="seed",
        )
    )
    await db_session.flush()

    applicable = await applicable_frameworks_for_project(db_session, project)

    assert framework.id in {f.id for f in applicable}


async def test_an_inactive_framework_never_appears_regardless_of_rules(
    db_session: AsyncSession,
) -> None:
    project = await _make_project(db_session, sector="infrastructure")
    framework = await _make_framework(db_session, is_active=False)
    db_session.add(
        FrameworkApplicabilityRule(
            id=uuid.uuid4(),
            framework_id=framework.id,
            sector="infrastructure",
            created_by="seed",
            updated_by="seed",
        )
    )
    await db_session.flush()

    applicable = await applicable_frameworks_for_project(db_session, project)

    assert framework.id not in {f.id for f in applicable}
