from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ipacgs.models.framework import Framework, FrameworkApplicabilityRule
from ipacgs.scripts.seed_framework_registry import FRAMEWORKS, seed


async def test_seed_creates_the_illustrative_frameworks_as_inactive(
    db_session: AsyncSession,
) -> None:
    await seed()

    for seed_fw in FRAMEWORKS:
        result = await db_session.execute(select(Framework).where(Framework.code == seed_fw.code))
        framework = result.scalars().one()
        assert framework.is_active is False


async def test_seed_creates_at_least_one_applicability_rule(db_session: AsyncSession) -> None:
    await seed()

    count = await db_session.scalar(select(func.count()).select_from(FrameworkApplicabilityRule))
    assert count is not None and count > 0


async def test_seed_is_idempotent(db_session: AsyncSession) -> None:
    await seed()
    await seed()

    count = await db_session.scalar(
        select(func.count()).select_from(Framework).where(Framework.code == FRAMEWORKS[0].code)
    )
    assert count == 1
