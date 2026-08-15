"""Seeds an ILLUSTRATIVE Gate 0 / Gate 1 — same honesty as every other
seed script in this repo: not KMI Africa's real gate definitions (the
SRS describes Gate 0-10), just enough of a placeholder to exercise the
mechanism — quorum, voting, non-bypassable Hold, certificates — for real.

Requires scripts/seed_stages.py to have already run: these gates are
defined to trigger at two of the real Intake & Screening stages from
that sequence ("INTK-SUBMIT" and "INTK-INTEGRITY"), looked up by code.
Run this after seed_stages, not before. Re-pointed from the old
illustrative "S1"/"S2" codes now that seed_stages.py seeds UACOC's real
Phase 1 stage names — the gates themselves are still illustrative; UACOC's
own process-map document doesn't describe a gate/quorum-vote mechanism at
all, so there's no real trigger point to source these from yet either.

Run with:
    python -m ipacgs.scripts.seed_gates

Idempotent — checks for an existing gate at each code before inserting.
"""

import asyncio
import uuid
from dataclasses import dataclass

from sqlalchemy import select

from ipacgs.core.db import async_session_factory, engine
from ipacgs.models.gate import Gate
from ipacgs.models.project import Stage

SEED_ACTOR = "seed-script"


@dataclass(frozen=True)
class SeedGate:
    code: str
    name: str
    description: str
    sequence: int
    trigger_stage_code: str
    required_quorum: int


GATES: tuple[SeedGate, ...] = (
    SeedGate(
        code="GATE-0",
        name="Opportunity Screening Gate",
        description="Illustrative — sign-off before leaving INTK-SUBMIT (Project Submission).",
        sequence=10,
        trigger_stage_code="INTK-SUBMIT",
        required_quorum=1,
    ),
    SeedGate(
        code="GATE-1",
        name="Structuring Gate",
        description="Illustrative — sign-off before leaving INTK-INTEGRITY "
        "(Integrity Screening), two-person quorum.",
        sequence=20,
        trigger_stage_code="INTK-INTEGRITY",
        required_quorum=2,
    ),
)


async def seed() -> None:
    async with async_session_factory() as session:
        existing = await session.execute(select(Gate.code))
        existing_codes = {row[0] for row in existing.all()}

        created = 0
        for seed_gate in GATES:
            if seed_gate.code in existing_codes:
                continue

            stage_result = await session.execute(
                select(Stage).where(Stage.code == seed_gate.trigger_stage_code)
            )
            trigger_stage = stage_result.scalars().first()
            if trigger_stage is None:
                raise RuntimeError(
                    f"No stage {seed_gate.trigger_stage_code!r} found — run "
                    "`python -m ipacgs.scripts.seed_stages` before this script."
                )

            session.add(
                Gate(
                    id=uuid.uuid4(),
                    code=seed_gate.code,
                    name=seed_gate.name,
                    description=seed_gate.description,
                    sequence=seed_gate.sequence,
                    trigger_stage_id=trigger_stage.id,
                    required_quorum=seed_gate.required_quorum,
                    is_active=True,
                    created_by=SEED_ACTOR,
                    updated_by=SEED_ACTOR,
                )
            )
            created += 1

        if created == 0:
            print("Illustrative gates already seeded.")
            return

        await session.commit()
        print(f"Seeded {created} illustrative gate(s).")


async def main() -> None:
    try:
        await seed()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
