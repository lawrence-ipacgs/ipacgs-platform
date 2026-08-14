"""Seeds ILLUSTRATIVE metadata for the other 29 IPAC 1001-008 frameworks.

Epic 4's real ticket list (AGA-30-001, AGA-30-009) calls for loading all
30 framework *definitions* and marking OPBOH "active" with the other 29
"registered, not yet assessable". This repo doesn't have KMI Africa's real
30-framework list — same situation `seed_opboh_catalogue.py` and
`seed_stages.py` are already honest about for OPBOH's own catalogue and
the stage sequence. What's below is a plausible illustrative spread across
the categories the architecture document's own purpose statement names
("screening, viability, land, governance, capital protection, execution,
stakeholder protection, impact continuity and more") — codes and names
invented for this repo, not a transcription of IPAC 1001-008.

Registered `is_active=False` — "registered, not yet assessable" per
AGA-30-009 — deliberately distinct from OPBOH, which this script leaves
alone (get-or-created by seed_opboh_catalogue.py / migration 0003).

A handful of illustrative FrameworkApplicabilityRule rows are seeded too,
so `GET /projects/{id}/applicable-frameworks` has something real to filter
on rather than every framework applying to every project unconditionally
by default.

Run with:
    python -m ipacgs.scripts.seed_framework_registry

Idempotent — checks for an existing framework at each code before
inserting.
"""

import asyncio
import uuid
from dataclasses import dataclass

from sqlalchemy import select

from ipacgs.core.db import async_session_factory, engine
from ipacgs.models.framework import Framework, FrameworkApplicabilityRule

SEED_ACTOR = "seed-script"


@dataclass(frozen=True)
class SeedFramework:
    code: str
    name: str
    description: str


# Illustrative only — see module docstring. 29 entries, deliberately not
# including OPBOH (already registered elsewhere).
FRAMEWORKS: tuple[SeedFramework, ...] = (
    SeedFramework(
        "SCREEN", "Initial Screening & Eligibility", "Early-stage opportunity screening."
    ),
    SeedFramework(
        "VIABILITY", "Commercial Viability Assessment", "Commercial/financial viability."
    ),
    SeedFramework(
        "LAND", "Land Rights & Tenure Assurance", "Land ownership and tenure verification."
    ),
    SeedFramework(
        "ENVSOC", "Environmental & Social Safeguards", "E&S risk screening and safeguards."
    ),
    SeedFramework(
        "GOVSTRUCT", "Governance Structure Assurance", "Sponsor governance structure review."
    ),
    SeedFramework(
        "FINCAP", "Financial Capacity Assurance", "Sponsor/counterparty financial capacity."
    ),
    SeedFramework(
        "CAPPROT", "Capital Protection Framework", "Capital deployment protection controls."
    ),
    SeedFramework("PROCURE", "Procurement Integrity", "Procurement process integrity controls."),
    SeedFramework("CONTRACT", "Contract Risk Assurance", "Contractual risk review."),
    SeedFramework("EXECREADY", "Execution Readiness", "Readiness to begin implementation."),
    SeedFramework("QUALITY", "Quality Assurance", "Delivery quality controls."),
    SeedFramework("HSE", "Health, Safety & Environment", "HSE compliance during execution."),
    SeedFramework(
        "STAKEHOLDER", "Stakeholder Engagement Assurance", "Stakeholder engagement quality."
    ),
    SeedFramework(
        "GRIEVANCE", "Grievance Mechanism Assurance", "Grievance-handling mechanism review."
    ),
    SeedFramework("LABOUR", "Labour & Working Conditions", "Labour standards compliance."),
    SeedFramework("ANTICORRUPT", "Anti-Corruption & Integrity", "Anti-corruption controls."),
    SeedFramework("AML", "Anti-Money Laundering Screening", "AML control review."),
    SeedFramework(
        "SANCTIONS", "Sanctions & Restricted Party Screening", "Sanctions list screening."
    ),
    SeedFramework("INSURANCE", "Insurance & Risk Transfer Assurance", "Insurance adequacy review."),
    SeedFramework("TECH", "Technical Design Assurance", "Technical design review."),
    SeedFramework("CLIMATE", "Climate Risk & Resilience", "Climate risk exposure assessment."),
    SeedFramework("BIODIV", "Biodiversity & Natural Capital", "Biodiversity impact screening."),
    SeedFramework(
        "COMMDEV", "Community Development Assurance", "Community development commitments."
    ),
    SeedFramework(
        "IMPACT", "Impact Measurement Assurance", "Impact measurement methodology review."
    ),
    SeedFramework(
        "CONTINUITY", "Impact Continuity & Sustainability", "Post-completion impact continuity."
    ),
    SeedFramework("EXITREADY", "Exit Readiness Assurance", "Investor/sponsor exit readiness."),
    SeedFramework("REPORTING", "Reporting Integrity", "Financial/impact reporting integrity."),
    SeedFramework("DATAPRIVACY", "Data Privacy & Protection", "Data privacy compliance."),
    SeedFramework("CYBERSEC", "Cybersecurity Assurance", "Cybersecurity control review."),
)

# A few illustrative applicability rules, so the "applicable frameworks"
# view has something to actually filter on — not exhaustive, not real.
_ILLUSTRATIVE_SECTOR_RULES: tuple[tuple[str, str], ...] = (
    ("LAND", "infrastructure"),
    ("BIODIV", "infrastructure"),
    ("CLIMATE", "energy"),
    ("HSE", "energy"),
)


async def seed() -> None:
    async with async_session_factory() as session:
        existing = await session.execute(select(Framework.code))
        existing_codes = {row[0] for row in existing.all()}

        created_frameworks: dict[str, Framework] = {}
        for seed_fw in FRAMEWORKS:
            if seed_fw.code in existing_codes:
                continue
            framework = Framework(
                id=uuid.uuid4(),
                code=seed_fw.code,
                name=seed_fw.name,
                description=seed_fw.description,
                is_active=False,
                created_by=SEED_ACTOR,
                updated_by=SEED_ACTOR,
            )
            session.add(framework)
            created_frameworks[seed_fw.code] = framework

        if not created_frameworks:
            print("Illustrative framework registry already seeded.")
        else:
            await session.flush()
            print(f"Seeded {len(created_frameworks)} illustrative framework(s).")

        # Rules reference frameworks that may already have existed before
        # this run — look them up rather than assuming they're all in
        # created_frameworks.
        rules_added = 0
        for code, sector in _ILLUSTRATIVE_SECTOR_RULES:
            rule_framework = created_frameworks.get(code)
            if rule_framework is None:
                result = await session.execute(select(Framework).where(Framework.code == code))
                rule_framework = result.scalars().first()
            if rule_framework is None:
                continue

            existing_rule = await session.execute(
                select(FrameworkApplicabilityRule).where(
                    FrameworkApplicabilityRule.framework_id == rule_framework.id,
                    FrameworkApplicabilityRule.sector == sector,
                )
            )
            if existing_rule.scalars().first() is not None:
                continue

            session.add(
                FrameworkApplicabilityRule(
                    id=uuid.uuid4(),
                    framework_id=rule_framework.id,
                    sector=sector,
                    created_by=SEED_ACTOR,
                    updated_by=SEED_ACTOR,
                )
            )
            rules_added += 1

        await session.commit()
        if rules_added:
            print(f"Seeded {rules_added} illustrative applicability rule(s).")


async def main() -> None:
    try:
        await seed()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
