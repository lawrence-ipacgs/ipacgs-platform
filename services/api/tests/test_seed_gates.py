from collections.abc import AsyncGenerator

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ipacgs.models.gate import Gate
from ipacgs.models.project import Stage
from ipacgs.scripts.seed_gates import GATES
from ipacgs.scripts.seed_gates import seed as seed_gates
from ipacgs.scripts.seed_stages import STAGES as SEEDED_STAGES
from ipacgs.scripts.seed_stages import seed as seed_stages

_SEEDED_STAGE_CODES = [s.code for s in SEEDED_STAGES]


@pytest.fixture(autouse=True)
async def _deactivate_seeded_stages_on_teardown(
    db_session: AsyncSession,
) -> AsyncGenerator[None, None]:
    """seed_stages() commits real, low-sequence Stage rows (S1-S4) via its
    own session — this is the first test file that actually calls it.
    Left active, they'd be exactly the kind of leak that broke
    test_stage_engine.py and test_project_routes.py twice already (a
    committed row with a lower sequence than whatever a later test
    generates for itself, winning create_project's "globally lowest
    active stage" query). Deactivating by code afterward is safe — every
    lookup in seed_gates.py/gate_engine.py is code- or exact-id-based,
    never filtered on is_active for the *trigger* stage itself."""
    yield
    await db_session.execute(
        update(Stage).where(Stage.code.in_(_SEEDED_STAGE_CODES)).values(is_active=False)
    )
    await db_session.commit()


async def test_seed_requires_stages_to_exist_first(db_session: AsyncSession) -> None:
    with pytest.raises(RuntimeError, match="seed_stages"):
        await seed_gates()


async def test_seed_creates_the_illustrative_gates(db_session: AsyncSession) -> None:
    await seed_stages()
    await seed_gates()

    for seed_gate in GATES:
        result = await db_session.execute(select(Gate).where(Gate.code == seed_gate.code))
        gate = result.scalars().one()
        assert gate.is_active is True
        assert gate.required_quorum == seed_gate.required_quorum


async def test_seed_is_idempotent(db_session: AsyncSession) -> None:
    await seed_stages()
    await seed_gates()
    await seed_gates()

    result = await db_session.execute(select(Gate).where(Gate.code == GATES[0].code))
    assert len(result.scalars().all()) == 1
