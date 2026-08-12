from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ipacgs.models.opboh import OpbohDomain, OpbohFrameworkVersion, OpbohQuestion
from ipacgs.scripts.seed_opboh_catalogue import CATALOGUE, ILLUSTRATIVE_VERSION_LABEL, seed


async def test_seed_creates_the_expected_catalogue_shape(db_session: AsyncSession) -> None:
    await seed()

    version_result = await db_session.execute(
        select(OpbohFrameworkVersion).where(
            OpbohFrameworkVersion.version_label == ILLUSTRATIVE_VERSION_LABEL
        )
    )
    version = version_result.scalars().one()
    assert version.is_active is True

    domain_count = await db_session.scalar(
        select(func.count())
        .select_from(OpbohDomain)
        .where(OpbohDomain.framework_version_id == version.id)
    )
    assert domain_count == len(CATALOGUE)

    expected_questions = sum(len(d.questions) for d in CATALOGUE)
    question_count = await db_session.scalar(
        select(func.count())
        .select_from(OpbohQuestion)
        .join(OpbohDomain, OpbohQuestion.domain_id == OpbohDomain.id)
        .where(OpbohDomain.framework_version_id == version.id)
    )
    assert question_count == expected_questions

    # Every domain the SRS's fatal-flaw mechanism actually depends on has
    # at least one critical control — an illustrative catalogue with none
    # would silently fail to exercise FW-OPBOH-015 at all.
    critical_count = await db_session.scalar(
        select(func.count())
        .select_from(OpbohQuestion)
        .join(OpbohDomain, OpbohQuestion.domain_id == OpbohDomain.id)
        .where(
            OpbohDomain.framework_version_id == version.id,
            OpbohQuestion.is_critical_control.is_(True),
        )
    )
    assert critical_count is not None and critical_count > 0


async def test_seed_is_idempotent(db_session: AsyncSession) -> None:
    await seed()
    await seed()  # should be a no-op the second time, not a duplicate or an error

    count = await db_session.scalar(
        select(func.count())
        .select_from(OpbohFrameworkVersion)
        .where(OpbohFrameworkVersion.version_label == ILLUSTRATIVE_VERSION_LABEL)
    )
    assert count == 1
