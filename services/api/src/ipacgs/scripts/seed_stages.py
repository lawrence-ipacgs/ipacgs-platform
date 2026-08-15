"""Seeds the REAL Phase 1 (Intake & Screening) stage sequence — 7 stages,
sourced from UACOC's "Project Intake Full Process Map" document
(`docs/Project Intake Full Process Map.pdf`, shared 2026-08-15). Unlike
every other seed script in this repo so far, this one is not an
illustrative placeholder: these are UACOC's actual stage names, in their
actual documented order, with descriptions drawn directly from each
stage's own process-map page. The old illustrative 4-stage placeholder
(codes S1-S4: "Opportunity & Sponsor Readiness" etc.) is gone — nothing
in the codebase referenced those names outside this file and
`seed_gates.py` (updated alongside this).

Two honest gaps this does NOT close:

1. That document's own page 1 overview describes a real 5-phase, 22-step
   lifecycle: Intake & Screening (this file, steps 1-7) -> Assessment &
   Preparation -> Investor Engagement & Structuring -> Delivery &
   Handover -> Realisation & Closure. Only Phase 1 is detailed anywhere
   in what's been shared — steps 8-22 have no source material yet, so
   this seed stops at stage 7 ("Project Onboarding"). A project that
   reaches it has nowhere further to advance until KMI/UACOC shares the
   rest.
2. `services/stage_engine.py`'s `advance_stage()` still requires an
   *accepted OPBOH assessment* to move between any two stages — a
   generic precondition built (Epic 5) before this document existed.
   That's a real mismatch for these seven stages specifically: their own
   documented advancement logic is administrative approval at each step
   (see each page's own numbered "Approval"/"Quality Review" sub-steps
   and Entry/Exit Criteria panels), not an OPBOH-style compliance
   assessment. The one place OPBOH plausibly *does* belong is Phase 2's
   very first step, "Diagnostic assessment" — the step immediately after
   this document ends, which is a promising signal — but the current
   code enforces that precondition from stage 1, too early. Not fixed
   here: doing it properly needs either per-stage configurable
   advancement rules or explicit confirmation from KMI/UACOC on what
   actually gates each of these seven steps, and both are bigger than a
   seed-data swap. See `stage_engine.py`'s module docstring for the same
   note at the enforcement site.

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


# Real — UACOC's Phase 1 (Intake & Screening), steps 1-7 of the 22-step
# lifecycle. Descriptions are drawn from each stage's own process-map
# purpose statement, lightly trimmed for length, not paraphrased into
# something the source document didn't say.
STAGES: tuple[SeedStage, ...] = (
    SeedStage(
        code="INTK-SUBMIT",
        name="Project Submission",
        description=(
            "Captures the project opportunity in a consistent format, establishes an "
            "official record, identifies the submitting party, and determines whether "
            "the submission is sufficiently complete to proceed to registration and "
            "screening."
        ),
        sequence=10,
    ),
    SeedStage(
        code="INTK-REGISTER",
        name="Project Registration",
        description=(
            "Creates the official project identity and record, classifies the project, "
            "assigns governance attributes, and activates the next lifecycle stage."
        ),
        sequence=20,
    ),
    SeedStage(
        code="INTK-SPONSOR-VER",
        name="Sponsor and Ownership Verification",
        description=(
            "Confirms the legal identity, authority, ownership structure, beneficial "
            "ownership, project rights, governance standing and delivery capacity of "
            "the project sponsor and all relevant project parties."
        ),
        sequence=30,
    ),
    SeedStage(
        code="INTK-INTEGRITY",
        name="Integrity Screening",
        description=(
            "Evaluates the ethical, legal, regulatory and reputational standing of the "
            "sponsor, beneficial owners, directors, related parties and other connected "
            "persons or entities to identify unacceptable risks."
        ),
        sequence=40,
    ),
    SeedStage(
        code="INTK-MIN-INFO",
        name="Minimum-Information Review",
        description=(
            "Evaluates whether a registered and integrity-cleared project contains the "
            "essential information required to enter Classification, Prioritisation and "
            "Detailed Assessment."
        ),
        sequence=50,
    ),
    SeedStage(
        code="INTK-CLASSIFY",
        name="Classification and Prioritisation",
        description=(
            "Categorises the project, ranks its strategic importance, and assigns the "
            "appropriate processing pathway and priority level."
        ),
        sequence=60,
    ),
    SeedStage(
        code="INTK-ONBOARD",
        name="Project Onboarding",
        description=(
            "Ensures a structured, transparent and well-governed onboarding of the "
            "project into the institutional lifecycle by confirming understanding, "
            "establishing governance, and preparing for diagnostic assessment and "
            "next-stage activities."
        ),
        sequence=70,
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
            print("Phase 1 (Intake & Screening) stage sequence already seeded.")
            return

        await session.commit()
        print(f"Seeded {created} stage(s) of UACOC's real Intake & Screening sequence.")


async def main() -> None:
    try:
        await seed()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
