"""Seeds each of UACOC's seven real `INTK-*` intake stages
(`scripts/seed_stages.py`) with its own real exit-criteria checklist.

Sourced verbatim (lightly trimmed for length, not paraphrased into something
the source document didn't say — same discipline `seed_stages.py` already
holds itself to) from each stage's own "Exit Criteria" panel in
`docs/Project Intake Full Process Map.pdf`. Every stage in that document has
one of these panels; what's below is a straight transcription of it, stage by
stage, in the order the panel lists them.

Once these items exist for a stage, `services/stage_engine.py`'s
`advance_stage` gates leaving that stage on them (a recorded
PROCEED/PROCEED_WITH_CONDITIONS `StageDecision`, itself only recordable once
every active item here has an answer) instead of on an OPBOH assessment — see
that module's docstring for the full mechanism.

Run with:
    python -m ipacgs.scripts.seed_stage_checklists

Idempotent — checks for an existing item at each (stage, sequence) before
inserting, same pattern as `seed_stages.py`.
"""

import asyncio
import uuid
from dataclasses import dataclass

from sqlalchemy import select

from ipacgs.core.db import async_session_factory, engine
from ipacgs.models.project import Stage
from ipacgs.models.stage_checklist import StageChecklistItem

SEED_ACTOR = "seed-script"


@dataclass(frozen=True)
class SeedItem:
    stage_code: str
    sequence: int
    criterion: str


ITEMS: tuple[SeedItem, ...] = (
    # INTK-SUBMIT — Project Submission
    SeedItem("INTK-SUBMIT", 10, "Submission record created"),
    SeedItem("INTK-SUBMIT", 20, "All mandatory information captured"),
    SeedItem("INTK-SUBMIT", 30, "Quality check passed"),
    SeedItem("INTK-SUBMIT", 40, "Ready for registration and screening"),
    # INTK-REGISTER — Project Registration
    SeedItem("INTK-REGISTER", 10, "Project entered into official register"),
    SeedItem("INTK-REGISTER", 20, "Unique registration number assigned"),
    SeedItem("INTK-REGISTER", 30, "Official identity established"),
    SeedItem("INTK-REGISTER", 40, "Project classified"),
    SeedItem("INTK-REGISTER", 50, "Lifecycle stage and status assigned"),
    SeedItem("INTK-REGISTER", 60, "Responsible unit and project officer appointed"),
    SeedItem("INTK-REGISTER", 70, "Initial risks and outstanding information recorded"),
    SeedItem("INTK-REGISTER", 80, "Project file created"),
    # INTK-SPONSOR-VER — Sponsor and Ownership Verification
    SeedItem("INTK-SPONSOR-VER", 10, "Identity and authority verified"),
    SeedItem("INTK-SPONSOR-VER", 20, "Ownership and rights confirmed"),
    SeedItem("INTK-SPONSOR-VER", 30, "Compliance and capacity assessed"),
    SeedItem("INTK-SPONSOR-VER", 40, "All supporting documents validated"),
    SeedItem("INTK-SPONSOR-VER", 50, "Quality standards met"),
    SeedItem("INTK-SPONSOR-VER", 60, "Status updated to Verified — Ready for Screening"),
    # INTK-INTEGRITY — Integrity Screening
    SeedItem("INTK-INTEGRITY", 10, "Integrity risk assessed and decision reached"),
    SeedItem("INTK-INTEGRITY", 20, "No unacceptable risk outstanding"),
    SeedItem("INTK-INTEGRITY", 30, "Outcome recorded in the integrity register and project system"),
    SeedItem("INTK-INTEGRITY", 40, "Sponsor notified of the screening outcome"),
    SeedItem("INTK-INTEGRITY", 50, "Lifecycle status updated"),
    SeedItem("INTK-INTEGRITY", 60, "Ready for the next stage"),
    # INTK-MIN-INFO — Minimum-Information Review
    SeedItem("INTK-MIN-INFO", 10, "Review completed and documented"),
    SeedItem("INTK-MIN-INFO", 20, "Information sufficiency decision made"),
    SeedItem("INTK-MIN-INFO", 30, "Information gaps addressed or recorded"),
    SeedItem("INTK-MIN-INFO", 40, "Readiness rating assigned"),
    SeedItem("INTK-MIN-INFO", 50, "Review findings approved"),
    SeedItem("INTK-MIN-INFO", 60, "Audit trail maintained"),
    # INTK-CLASSIFY — Classification and Prioritisation
    SeedItem("INTK-CLASSIFY", 10, "Project classified across all required dimensions"),
    SeedItem("INTK-CLASSIFY", 20, "Priority level assigned and approved"),
    SeedItem("INTK-CLASSIFY", 30, "Processing pathway determined"),
    SeedItem("INTK-CLASSIFY", 40, "Classification record completed"),
    SeedItem("INTK-CLASSIFY", 50, "Project forwarded to the next process stage"),
    # INTK-ONBOARD — Project Onboarding
    SeedItem("INTK-ONBOARD", 10, "Formal onboarding session attended"),
    SeedItem("INTK-ONBOARD", 20, "Project identity, priority and pathway confirmed"),
    SeedItem("INTK-ONBOARD", 30, "Institutional mandate and lifecycle explained"),
    SeedItem("INTK-ONBOARD", 40, "Governance arrangements established"),
    SeedItem("INTK-ONBOARD", 50, "Roles and authority documented"),
    SeedItem("INTK-ONBOARD", 60, "Communication protocols agreed"),
    SeedItem("INTK-ONBOARD", 70, "Confidentiality and data protection confirmed"),
    SeedItem("INTK-ONBOARD", 80, "Digital access activated"),
    SeedItem("INTK-ONBOARD", 90, "Reporting requirements established"),
    SeedItem("INTK-ONBOARD", 100, "Conditions reviewed, resolved or established"),
    SeedItem("INTK-ONBOARD", 110, "Diagnostic scope agreed"),
    SeedItem("INTK-ONBOARD", 120, "Work programme approved"),
    SeedItem("INTK-ONBOARD", 130, "Sponsor acknowledgement signed"),
    SeedItem("INTK-ONBOARD", 140, "Onboarding report approved"),
    SeedItem("INTK-ONBOARD", 150, "Project authorised to proceed (conditionally or fully)"),
)


async def seed() -> None:
    async with async_session_factory() as session:
        stages_result = await session.execute(
            select(Stage).where(Stage.code.in_({i.stage_code for i in ITEMS}))
        )
        stages_by_code = {s.code: s for s in stages_result.scalars().all()}
        missing_codes = {i.stage_code for i in ITEMS} - stages_by_code.keys()
        if missing_codes:
            raise RuntimeError(
                f"Stage code(s) {sorted(missing_codes)} not found — run "
                "scripts/seed_stages.py first."
            )

        existing_result = await session.execute(
            select(StageChecklistItem.stage_id, StageChecklistItem.sequence)
        )
        existing_keys = {(row[0], row[1]) for row in existing_result.all()}

        created = 0
        for item in ITEMS:
            stage = stages_by_code[item.stage_code]
            if (stage.id, item.sequence) in existing_keys:
                continue
            session.add(
                StageChecklistItem(
                    id=uuid.uuid4(),
                    stage_id=stage.id,
                    sequence=item.sequence,
                    criterion=item.criterion,
                    is_active=True,
                    created_by=SEED_ACTOR,
                    updated_by=SEED_ACTOR,
                )
            )
            created += 1

        if created == 0:
            print("Stage checklists already seeded.")
            return

        await session.commit()
        print(f"Seeded {created} checklist item(s) across {len(stages_by_code)} stage(s).")


async def main() -> None:
    try:
        await seed()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
