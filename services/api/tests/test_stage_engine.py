"""Service-level Stage Engine tests. These only `flush()` via `db_session`
(never `commit()`), so nothing here leaks across tests today — same
caveat as test_framework_registry.py, and codes/sequences are still
randomized rather than quietly relying on that staying true forever."""

import uuid
from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ipacgs.models.opboh import OpbohAssessment, OpbohAssessmentStatus, OpbohFrameworkVersion
from ipacgs.models.organisation import Organisation
from ipacgs.models.project import Stage
from ipacgs.models.tenant import Tenant
from ipacgs.services.stage_engine import (
    IllegalStageAdvancement,
    NoStagesConfigured,
    advance_stage,
    create_project,
)


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


async def _make_tenant_and_org(db_session: AsyncSession) -> Organisation:
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
    return org


async def _make_stages(db_session: AsyncSession, count: int) -> list[Stage]:
    """A widely-separated random base per call, so two tests' stages can
    never numerically interleave — Stage.sequence is global, unscoped
    ordering, unlike a simple unique code."""
    base = uuid.uuid4().int % 1_000_000 * 100
    stages = [
        Stage(
            id=uuid.uuid4(),
            code=_unique("stg"),
            name=f"Stage {i}",
            sequence=base + i * 10,
            is_active=True,
            created_by="seed",
            updated_by="seed",
        )
        for i in range(count)
    ]
    db_session.add_all(stages)
    await db_session.flush()
    return stages


async def _make_assessment(
    db_session: AsyncSession, org: Organisation, *, status: OpbohAssessmentStatus
) -> OpbohAssessment:
    version = OpbohFrameworkVersion(
        id=uuid.uuid4(),
        version_label=_unique("v")[:20],
        effective_from=date(2026, 1, 1),
        is_active=True,
        created_by="seed",
        updated_by="seed",
    )
    db_session.add(version)
    await db_session.flush()
    assessment = OpbohAssessment(
        id=uuid.uuid4(),
        tenant_id=org.tenant_id,
        framework_version_id=version.id,
        organisation_id=org.id,
        status=status,
        prepared_by="alice",
        has_critical_failure=False,
        created_by="alice",
        updated_by="alice",
    )
    db_session.add(assessment)
    await db_session.flush()
    return assessment


async def test_create_project_starts_at_lowest_sequence_active_stage(
    db_session: AsyncSession,
) -> None:
    org = await _make_tenant_and_org(db_session)
    stages = await _make_stages(db_session, 3)

    project = await create_project(
        db_session,
        tenant_id=org.tenant_id,
        organisation_id=org.id,
        name="Test Project",
        description=None,
        actor="alice",
    )
    assert project.current_stage_id == stages[0].id


async def test_create_project_with_no_stages_raises(db_session: AsyncSession) -> None:
    org = await _make_tenant_and_org(db_session)
    with pytest.raises(NoStagesConfigured):
        await create_project(
            db_session,
            tenant_id=org.tenant_id,
            organisation_id=org.id,
            name="Test Project",
            description=None,
            actor="alice",
        )


async def test_advance_stage_moves_to_the_next_stage_by_sequence(db_session: AsyncSession) -> None:
    org = await _make_tenant_and_org(db_session)
    stages = await _make_stages(db_session, 3)
    project = await create_project(
        db_session,
        tenant_id=org.tenant_id,
        organisation_id=org.id,
        name="Test Project",
        description=None,
        actor="alice",
    )
    assessment = await _make_assessment(db_session, org, status=OpbohAssessmentStatus.ACCEPTED)

    decision = await advance_stage(
        db_session, project, supporting_assessment=assessment, actor="alice"
    )

    assert decision.from_stage_id == stages[0].id
    assert decision.to_stage_id == stages[1].id
    assert project.current_stage_id == stages[1].id


async def test_advance_stage_rejects_a_draft_assessment(db_session: AsyncSession) -> None:
    org = await _make_tenant_and_org(db_session)
    await _make_stages(db_session, 2)
    project = await create_project(
        db_session,
        tenant_id=org.tenant_id,
        organisation_id=org.id,
        name="Test Project",
        description=None,
        actor="alice",
    )
    assessment = await _make_assessment(db_session, org, status=OpbohAssessmentStatus.DRAFT)

    with pytest.raises(IllegalStageAdvancement, match="draft"):
        await advance_stage(db_session, project, supporting_assessment=assessment, actor="alice")


async def test_advance_stage_rejects_an_assessment_for_a_different_organisation(
    db_session: AsyncSession,
) -> None:
    org = await _make_tenant_and_org(db_session)
    other_org = await _make_tenant_and_org(db_session)
    await _make_stages(db_session, 2)
    project = await create_project(
        db_session,
        tenant_id=org.tenant_id,
        organisation_id=org.id,
        name="Test Project",
        description=None,
        actor="alice",
    )
    assessment = await _make_assessment(
        db_session, other_org, status=OpbohAssessmentStatus.ACCEPTED
    )

    with pytest.raises(IllegalStageAdvancement, match="different organisation"):
        await advance_stage(db_session, project, supporting_assessment=assessment, actor="alice")


async def test_advance_stage_at_the_final_stage_raises(db_session: AsyncSession) -> None:
    org = await _make_tenant_and_org(db_session)
    await _make_stages(db_session, 1)  # only one stage — already at the end
    project = await create_project(
        db_session,
        tenant_id=org.tenant_id,
        organisation_id=org.id,
        name="Test Project",
        description=None,
        actor="alice",
    )
    assessment = await _make_assessment(db_session, org, status=OpbohAssessmentStatus.ACCEPTED)

    with pytest.raises(IllegalStageAdvancement, match="final configured stage"):
        await advance_stage(db_session, project, supporting_assessment=assessment, actor="alice")
