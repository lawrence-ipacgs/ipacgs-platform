from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ipacgs.models.framework import Framework
from ipacgs.models.opboh import OpbohDomain, OpbohFrameworkVersion, OpbohQuestion
from ipacgs.scripts.seed_opboh_catalogue import ILLUSTRATIVE_VERSION_LABEL
from ipacgs.scripts.seed_opboh_catalogue import seed as seed_illustrative
from ipacgs.scripts.seed_opboh_real_catalogue import CATALOGUE, REAL_VERSION_LABEL
from ipacgs.scripts.seed_opboh_real_catalogue import seed as seed_real


async def test_seed_creates_the_expected_shape_and_deactivates_the_illustrative_catalogue(
    db_session: AsyncSession,
) -> None:
    """One test, not two: `seed_real()` commits for real (its own session,
    separate from `db_session` — same reason `test_opboh_routes.py`'s
    `catalogue` fixture documents) and is idempotent on `REAL_VERSION_LABEL`
    existing at all, so it only *ever* does real work once per test session
    — a second test calling it a second time to re-check the
    illustrative-deactivation branch would just hit the early return and
    trivially pass without exercising anything. This test earns the right
    to be the one exercising that branch by explicitly setting up its own
    precondition (an active illustrative catalogue) first, rather than
    assuming suite order left one in place.
    """
    await seed_illustrative()
    await db_session.execute(
        update(OpbohFrameworkVersion)
        .where(OpbohFrameworkVersion.version_label == ILLUSTRATIVE_VERSION_LABEL)
        .values(is_active=True)
    )
    await db_session.commit()

    await seed_real()

    version_result = await db_session.execute(
        select(OpbohFrameworkVersion).where(
            OpbohFrameworkVersion.version_label == REAL_VERSION_LABEL
        )
    )
    version = version_result.scalars().one()
    assert version.is_active is True

    # Epic 4 — registered under the Framework Registry's OPBOH entry, same
    # as the illustrative catalogue, not floating unlinked.
    assert version.framework_id is not None
    framework = await db_session.get(Framework, version.framework_id)
    assert framework is not None
    assert framework.code == "OPBOH"

    domain_count = await db_session.scalar(
        select(func.count())
        .select_from(OpbohDomain)
        .where(OpbohDomain.framework_version_id == version.id)
    )
    assert domain_count == len(CATALOGUE) == 37

    expected_questions = sum(len(d.questions) for d in CATALOGUE)
    question_count = await db_session.scalar(
        select(func.count())
        .select_from(OpbohQuestion)
        .join(OpbohDomain, OpbohQuestion.domain_id == OpbohDomain.id)
        .where(OpbohDomain.framework_version_id == version.id)
    )
    assert question_count == expected_questions == 222

    # One critical control per domain (the first focus field) — a
    # documented placeholder (see this script's module docstring), not a
    # KMI-confirmed criticality determination, but enough to keep
    # FW-OPBOH-015's fatal-flaw mechanism actually exercised.
    critical_count = await db_session.scalar(
        select(func.count())
        .select_from(OpbohQuestion)
        .join(OpbohDomain, OpbohQuestion.domain_id == OpbohDomain.id)
        .where(
            OpbohDomain.framework_version_id == version.id,
            OpbohQuestion.is_critical_control.is_(True),
        )
    )
    assert critical_count == 37

    # The illustrative catalogue seeded above is deactivated, not deleted —
    # existing assessments still reference it by ID (see this script's
    # module docstring) — and it's the only thing that changed status:
    # exactly one active OpbohFrameworkVersion afterward. Only meaningful
    # to assert here, in the one test that controls both catalogues' state
    # from a known starting point.
    illustrative_result = await db_session.execute(
        select(OpbohFrameworkVersion).where(
            OpbohFrameworkVersion.version_label == ILLUSTRATIVE_VERSION_LABEL
        )
    )
    illustrative = illustrative_result.scalars().one()
    assert illustrative.is_active is False

    active_count = await db_session.scalar(
        select(func.count())
        .select_from(OpbohFrameworkVersion)
        .where(OpbohFrameworkVersion.is_active.is_(True))
    )
    assert active_count == 1


async def test_seed_is_idempotent(db_session: AsyncSession) -> None:
    await seed_real()
    await seed_real()  # should be a no-op the second time, not a duplicate or an error

    count = await db_session.scalar(
        select(func.count())
        .select_from(OpbohFrameworkVersion)
        .where(OpbohFrameworkVersion.version_label == REAL_VERSION_LABEL)
    )
    assert count == 1
