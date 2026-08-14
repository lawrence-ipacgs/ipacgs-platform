"""Epic 5 — Stage Engine service layer.

`advance_stage` is where PRN-001 ("date alone never authorizes
progression") actually gets enforced — mirrors how FW-OPBOH-015's
fatal-flaw block lives in `opboh_workflow.decide`, not in the schema: the
rule is a function precondition, not just a column that happens to exist.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ipacgs.models.opboh import OpbohAssessment, OpbohAssessmentStatus
from ipacgs.models.project import Project, ProjectStatus, Stage, StageGateDecision

_ACCEPTED_STATES = frozenset(
    {OpbohAssessmentStatus.ACCEPTED, OpbohAssessmentStatus.CONDITIONALLY_ACCEPTED}
)


class StageEngineError(Exception):
    """Base class for this module's domain exceptions."""


class NoStagesConfigured(StageEngineError):
    """No active Stage rows exist to assign a new project to — run
    scripts/seed_stages.py (or register real stages) first."""


class IllegalStageAdvancement(StageEngineError):
    """Raised when advance_stage's preconditions aren't met."""


async def create_project(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    organisation_id: uuid.UUID,
    name: str,
    description: str | None,
    actor: str,
) -> Project:
    first_stage_result = await session.execute(
        select(Stage).where(Stage.is_active.is_(True)).order_by(Stage.sequence).limit(1)
    )
    first_stage = first_stage_result.scalars().first()
    if first_stage is None:
        raise NoStagesConfigured("No active stages configured — nothing to start a project at.")

    project = Project(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        organisation_id=organisation_id,
        name=name,
        description=description,
        current_stage_id=first_stage.id,
        status=ProjectStatus.ACTIVE,
        created_by=actor,
        updated_by=actor,
    )
    session.add(project)
    await session.flush()
    return project


async def advance_stage(
    session: AsyncSession,
    project: Project,
    *,
    supporting_assessment: OpbohAssessment,
    actor: str,
    notes: str | None = None,
) -> StageGateDecision:
    if supporting_assessment.status not in _ACCEPTED_STATES:
        raise IllegalStageAdvancement(
            f"Assessment {supporting_assessment.id} is "
            f"{supporting_assessment.status.value} — advancing a stage needs an "
            "accepted (or conditionally accepted) assessment, not a date."
        )
    if supporting_assessment.organisation_id != project.organisation_id:
        raise IllegalStageAdvancement(
            f"Assessment {supporting_assessment.id} is for a different organisation "
            f"than project {project.id} — it can't justify this project's advancement."
        )

    current_stage = await session.get(Stage, project.current_stage_id)
    if current_stage is None:
        raise IllegalStageAdvancement(
            f"Project {project.id}'s current stage {project.current_stage_id} no longer exists."
        )

    next_stage_result = await session.execute(
        select(Stage)
        .where(Stage.is_active.is_(True), Stage.sequence > current_stage.sequence)
        .order_by(Stage.sequence)
        .limit(1)
    )
    next_stage = next_stage_result.scalars().first()
    if next_stage is None:
        raise IllegalStageAdvancement(
            f"Project {project.id} is already at the final configured stage ({current_stage.code})."
        )

    decision = StageGateDecision(
        id=uuid.uuid4(),
        tenant_id=project.tenant_id,
        project_id=project.id,
        from_stage_id=current_stage.id,
        to_stage_id=next_stage.id,
        supporting_assessment_id=supporting_assessment.id,
        decided_by=actor,
        decided_at=datetime.now(UTC),
        notes=notes,
    )
    session.add(decision)

    project.current_stage_id = next_stage.id
    project.updated_by = actor

    await session.flush()
    return decision
