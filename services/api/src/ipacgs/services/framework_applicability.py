"""Epic 4 gap-closing — a minimal applicability engine, not the full
sector/jurisdiction/risk/stage rules engine FR-AGA-001…002 actually
specifies. See models/framework.py's FrameworkApplicabilityRule
docstring for the exact scope cut (sector only, opt-out-by-default)."""

import uuid
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ipacgs.models.framework import Framework, FrameworkApplicabilityRule
from ipacgs.models.project import Project


async def applicable_frameworks_for_project(
    session: AsyncSession, project: Project
) -> list[Framework]:
    """Every active framework with no rules recorded against it is
    applicable by default (this is how OPBOH behaves today — no rule
    gates it). A framework with rules is applicable only if at least one
    of its rules matches this project's sector, or is itself sector-agnostic
    (sector is null)."""
    frameworks_result = await session.execute(
        select(Framework).where(Framework.is_active.is_(True))
    )
    frameworks = list(frameworks_result.scalars().all())

    rules_result = await session.execute(select(FrameworkApplicabilityRule))
    rules_by_framework: dict[uuid.UUID, list[FrameworkApplicabilityRule]] = defaultdict(list)
    for rule in rules_result.scalars().all():
        rules_by_framework[rule.framework_id].append(rule)

    applicable = []
    for framework in frameworks:
        rules = rules_by_framework.get(framework.id, [])
        if not rules:
            applicable.append(framework)
            continue
        if any(rule.sector is None or rule.sector == project.sector for rule in rules):
            applicable.append(framework)
    return applicable
