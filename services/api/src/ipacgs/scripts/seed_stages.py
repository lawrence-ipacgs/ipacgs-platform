"""Seeds an ILLUSTRATIVE stage sequence — 4 stages, S1 through S4.

Same honesty as `seed_opboh_catalogue.py`: this is not KMI Africa's real,
confirmed stage-gate sequence from the SRS — that source material hasn't
been shared into this repo yet either. What's here is a small, clearly
labeled placeholder that lets `services/stage_engine.py` actually advance
a project through more than one stage, gated on a real accepted
assessment each time — not a claim about what the real lifecycle stages
are called or how many there are.

Run with:
    python -m ipacgs.scripts.seed_stages

Idempotent — checks for an existing stage at each code before inserting.
"""

import asyncio
import uuid
from dataclasses import dataclass

from sqlalchemy import select

from ipacgs.core.db import async_session_factory, engine
from ipacgs.models.project import Stage

SEED_ACTOR = "seed-script"


@dataclass(frozen=True)
class SeedStage:
    code: str
    name: str
    description: str
    sequence: int


# Illustrative only — plausible coverage of a development-capital project's
# lifecycle (opportunity through governance/closeout), matching the stage
# span ("S1-S4") the OPBOH illustrative catalogue's own comments already
# reference, not a transcription of a confirmed source document.
STAGES: tuple[SeedStage, ...] = (
    SeedStage(
        code="S1",
        name="Opportunity & Sponsor Readiness",
        description="Initial screening — sponsor legitimacy, opportunity rationale.",
        sequence=10,
    ),
    SeedStage(
        code="S2",
        name="Site & Structuring",
        description="Site/land screening and initial deal structuring.",
        sequence=20,
    ),
    SeedStage(
        code="S3",
        name="Execution Readiness",
        description="Detailed diligence and readiness to begin implementation.",
        sequence=30,
    ),
    SeedStage(
        code="S4",
        name="Governance & Closeout",
        description="Ongoing governance through project closeout.",
        sequence=40,
    ),
)


async def seed() -> None:
    async with async_session_factory() as session:
        existing = await session.execute(select(Stage.code))
        existing_codes = {row[0] for row in existing.all()}

        created = 0
        for seed_stage in STAGES:
            if seed_stage.code in existing_codes:
                continue
            session.add(
                Stage(
                    id=uuid.uuid4(),
                    code=seed_stage.code,
                    name=seed_stage.name,
                    description=seed_stage.description,
                    sequence=seed_stage.sequence,
                    is_active=True,
                    created_by=SEED_ACTOR,
                    updated_by=SEED_ACTOR,
                )
            )
            created += 1

        if created == 0:
            print("Illustrative stage sequence already seeded.")
            return

        await session.commit()
        print(f"Seeded {created} illustrative stage(s).")


async def main() -> None:
    try:
        await seed()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
