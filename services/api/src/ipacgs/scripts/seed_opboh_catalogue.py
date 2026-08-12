"""Seeds an ILLUSTRATIVE OPBOH catalogue — 4 domains, 8 questions.

This is not KMI Africa's real OPBOH content. The actual catalogue (the
spec deck's "827 explicit module fields, 3,700 source questions") lives in
source PDFs that haven't been shared into this repo yet. What's here is a
small, clearly-labeled placeholder — enough to exercise the scoring engine
and API for real (a critical control that can actually fail, a domain
threshold that actually gates), not a claim about what OPBOH really asks.

Run with:
    python -m ipacgs.scripts.seed_opboh_catalogue

Idempotent — checks for an existing catalogue at ILLUSTRATIVE_VERSION_LABEL
before inserting, so re-running doesn't create duplicates. When the real
catalogue is ready to import, that import should mark its own framework
version `is_active = True` and this illustrative one `is_active = False`
(see `create_assessment`'s "no active version" check in
`api/routes/opboh.py` — only one version should be active for new
assessments at a time) rather than deleting this one outright; existing
assessments still reference it by ID.
"""

import asyncio
import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select

from ipacgs.core.db import async_session_factory, engine
from ipacgs.models.opboh import OpbohDomain, OpbohFrameworkVersion, OpbohQuestion

ILLUSTRATIVE_VERSION_LABEL = "illus-0.1"
SEED_ACTOR = "seed-script"


@dataclass(frozen=True)
class SeedQuestion:
    control_objective: str
    question_text: str
    is_critical_control: bool
    pass_threshold: float


@dataclass(frozen=True)
class SeedDomain:
    code: str
    name: str
    weight: float
    min_score_threshold: float
    questions: tuple[SeedQuestion, ...]


# Four domains matching OPBOH's real stage applicability (S1-S4, per the
# SRS) — opportunity/sponsor through governance — not a guess at the real
# domain list, just plausible coverage for those four stages so the
# scoring engine has something real to score.
CATALOGUE: tuple[SeedDomain, ...] = (
    SeedDomain(
        code="sponsor-readiness",
        name="Sponsor & Opportunity Readiness",
        weight=1.0,
        min_score_threshold=0.6,
        questions=(
            SeedQuestion(
                control_objective="Sponsor has clear legal existence",
                question_text="Is the sponsor a validly registered, existing legal entity?",
                is_critical_control=True,
                pass_threshold=1.0,
            ),
            SeedQuestion(
                control_objective="Sponsor has documented mandate and authority",
                question_text=(
                    "Does the sponsor have clear, documented mandate/authority to bring "
                    "this opportunity forward?"
                ),
                is_critical_control=True,
                pass_threshold=1.0,
            ),
            SeedQuestion(
                control_objective="Opportunity has a documented strategic rationale",
                question_text=(
                    "Does the opportunity have a documented strategic rationale and "
                    "beneficiary value proposition?"
                ),
                is_critical_control=False,
                pass_threshold=0.5,
            ),
        ),
    ),
    SeedDomain(
        code="site-screening",
        name="Site & Land Screening",
        weight=1.0,
        min_score_threshold=0.6,
        questions=(
            SeedQuestion(
                control_objective="Site ownership or right-of-use is unambiguous",
                question_text="Is site ownership or right-of-use documented and unambiguous?",
                is_critical_control=True,
                pass_threshold=1.0,
            ),
            SeedQuestion(
                control_objective="Obvious site constraints have been screened",
                question_text="Have obvious environmental or access constraints been screened?",
                is_critical_control=False,
                pass_threshold=0.5,
            ),
        ),
    ),
    SeedDomain(
        code="governance",
        name="Governance & Control Environment",
        weight=1.0,
        min_score_threshold=0.6,
        questions=(
            SeedQuestion(
                control_objective="A governance structure with defined decision authority exists",
                question_text=(
                    "Is there a documented governance structure (board/steering committee) "
                    "with defined decision authority?"
                ),
                is_critical_control=True,
                pass_threshold=1.0,
            ),
            SeedQuestion(
                control_objective="Basic financial controls are documented",
                question_text=(
                    "Are basic financial controls (segregation of duties, approval limits) "
                    "documented?"
                ),
                is_critical_control=False,
                pass_threshold=0.5,
            ),
        ),
    ),
    SeedDomain(
        code="integrity-screening",
        name="Conflict & Integrity Screening",
        weight=1.0,
        min_score_threshold=0.6,
        questions=(
            SeedQuestion(
                control_objective="No unresolved conflict-of-interest or sanctions flags",
                question_text=(
                    "Has a conflict-of-interest and sanctions screen been completed with "
                    "no unresolved red flags?"
                ),
                is_critical_control=True,
                pass_threshold=1.0,
            ),
        ),
    ),
)


async def seed() -> None:
    async with async_session_factory() as session:
        existing = await session.execute(
            select(OpbohFrameworkVersion).where(
                OpbohFrameworkVersion.version_label == ILLUSTRATIVE_VERSION_LABEL
            )
        )
        if existing.scalars().first() is not None:
            print(f"Illustrative catalogue {ILLUSTRATIVE_VERSION_LABEL!r} already seeded.")
            return

        version = OpbohFrameworkVersion(
            id=uuid.uuid4(),
            version_label=ILLUSTRATIVE_VERSION_LABEL,
            effective_from=date.today(),
            is_active=True,
            created_by=SEED_ACTOR,
            updated_by=SEED_ACTOR,
        )
        session.add(version)
        await session.flush()

        question_count = 0
        for sequence, seed_domain in enumerate(CATALOGUE):
            domain = OpbohDomain(
                id=uuid.uuid4(),
                framework_version_id=version.id,
                code=seed_domain.code,
                name=seed_domain.name,
                sequence=sequence,
                weight=seed_domain.weight,
                min_score_threshold=seed_domain.min_score_threshold,
            )
            session.add(domain)
            await session.flush()

            for q_sequence, seed_question in enumerate(seed_domain.questions):
                session.add(
                    OpbohQuestion(
                        id=uuid.uuid4(),
                        domain_id=domain.id,
                        control_objective=seed_question.control_objective,
                        question_text=seed_question.question_text,
                        sequence=q_sequence,
                        is_critical_control=seed_question.is_critical_control,
                        pass_threshold=seed_question.pass_threshold,
                        evidence_required=True,
                    )
                )
                question_count += 1

        await session.commit()
        print(
            f"Seeded illustrative OPBOH catalogue {ILLUSTRATIVE_VERSION_LABEL!r}: "
            f"{len(CATALOGUE)} domains, {question_count} questions."
        )


async def main() -> None:
    try:
        await seed()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
