"""Service-level Stage Engine tests. These only `flush()` via `db_session`
(never `commit()`), so nothing here leaks across tests today — same
caveat as test_framework_registry.py, and codes/sequences are still
randomized rather than quietly relying on that staying true forever."""

import uuid
from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ipacgs.models.opboh import (
    FindingSeverity,
    FindingStatus,
    OpbohAssessment,
    OpbohAssessmentStatus,
    OpbohDomain,
    OpbohFinding,
    OpbohFrameworkVersion,
    OpbohQuestion,
    OpbohResponse,
    OpbohResponseValue,
)
from ipacgs.models.organisation import Organisation
from ipacgs.models.project import Project, Stage
from ipacgs.models.stage_checklist import (
    ChecklistResponseValue,
    StageChecklistItem,
    StageDecisionOutcome,
)
from ipacgs.models.tenant import Tenant
from ipacgs.services.stage_engine import (
    IllegalStageAdvancement,
    NoStagesConfigured,
    RagStatus,
    advance_stage,
    assign_stage,
    compute_project_rag,
    create_project,
    list_open_findings_for_project,
    record_checklist_response,
    record_stage_decision,
    reopen_stage,
)


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


async def _make_tenant_and_org(db_session: AsyncSession) -> Organisation:
    tenant = Tenant(id=uuid.uuid4(), name="Test Tenant", slug=_unique("t"), created_by="seed")
    db_session.add(tenant)
    await db_session.flush()
    org = Organisation(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        legal_name="Test Sponsor Ltd",
        created_by="seed",
        updated_by="seed",
    )
    db_session.add(org)
    await db_session.flush()
    return org


async def _make_stages(db_session: AsyncSession, count: int) -> list[Stage]:
    """A widely-separated random base per call, so two tests' stages can
    never numerically interleave — Stage.sequence is global, unscoped
    ordering, unlike a simple unique code."""
    base = uuid.uuid4().int % 1_000_000 * 100
    stages = [
        Stage(
            id=uuid.uuid4(),
            code=_unique("stg"),
            name=f"Stage {i}",
            sequence=base + i * 10,
            is_active=True,
            created_by="seed",
            updated_by="seed",
        )
        for i in range(count)
    ]
    db_session.add_all(stages)
    await db_session.flush()
    return stages


async def _make_checklist_items(
    db_session: AsyncSession, stage: Stage, criteria: list[str]
) -> list[StageChecklistItem]:
    items = [
        StageChecklistItem(
            id=uuid.uuid4(),
            stage_id=stage.id,
            sequence=(i + 1) * 10,
            criterion=criterion,
            is_active=True,
            created_by="seed",
            updated_by="seed",
        )
        for i, criterion in enumerate(criteria)
    ]
    db_session.add_all(items)
    await db_session.flush()
    return items


async def _make_assessment(
    db_session: AsyncSession,
    org: Organisation,
    *,
    status: OpbohAssessmentStatus,
    project: Project | None = None,
) -> OpbohAssessment:
    version = OpbohFrameworkVersion(
        id=uuid.uuid4(),
        version_label=_unique("v")[:20],
        effective_from=date(2026, 1, 1),
        is_active=True,
        created_by="seed",
        updated_by="seed",
    )
    db_session.add(version)
    await db_session.flush()
    assessment = OpbohAssessment(
        id=uuid.uuid4(),
        tenant_id=org.tenant_id,
        framework_version_id=version.id,
        organisation_id=org.id,
        project_id=project.id if project else None,
        status=status,
        prepared_by="alice",
        has_critical_failure=False,
        created_by="alice",
        updated_by="alice",
    )
    db_session.add(assessment)
    await db_session.flush()
    return assessment


async def test_create_project_starts_at_lowest_sequence_active_stage(
    db_session: AsyncSession,
) -> None:
    org = await _make_tenant_and_org(db_session)
    stages = await _make_stages(db_session, 3)

    project = await create_project(
        db_session,
        tenant_id=org.tenant_id,
        organisation_id=org.id,
        name="Test Project",
        description=None,
        actor="alice",
    )
    assert project.current_stage_id == stages[0].id


async def test_create_project_with_no_stages_raises(db_session: AsyncSession) -> None:
    org = await _make_tenant_and_org(db_session)
    with pytest.raises(NoStagesConfigured):
        await create_project(
            db_session,
            tenant_id=org.tenant_id,
            organisation_id=org.id,
            name="Test Project",
            description=None,
            actor="alice",
        )


async def test_advance_stage_moves_to_the_next_stage_by_sequence(db_session: AsyncSession) -> None:
    org = await _make_tenant_and_org(db_session)
    stages = await _make_stages(db_session, 3)
    project = await create_project(
        db_session,
        tenant_id=org.tenant_id,
        organisation_id=org.id,
        name="Test Project",
        description=None,
        actor="alice",
    )
    assessment = await _make_assessment(db_session, org, status=OpbohAssessmentStatus.ACCEPTED)

    decision = await advance_stage(
        db_session, project, supporting_assessment=assessment, actor="alice"
    )

    assert decision.from_stage_id == stages[0].id
    assert decision.to_stage_id == stages[1].id
    assert project.current_stage_id == stages[1].id


async def test_advance_stage_rejects_a_draft_assessment(db_session: AsyncSession) -> None:
    org = await _make_tenant_and_org(db_session)
    await _make_stages(db_session, 2)
    project = await create_project(
        db_session,
        tenant_id=org.tenant_id,
        organisation_id=org.id,
        name="Test Project",
        description=None,
        actor="alice",
    )
    assessment = await _make_assessment(db_session, org, status=OpbohAssessmentStatus.DRAFT)

    with pytest.raises(IllegalStageAdvancement, match="draft"):
        await advance_stage(db_session, project, supporting_assessment=assessment, actor="alice")


async def test_advance_stage_rejects_an_assessment_for_a_different_organisation(
    db_session: AsyncSession,
) -> None:
    org = await _make_tenant_and_org(db_session)
    other_org = await _make_tenant_and_org(db_session)
    await _make_stages(db_session, 2)
    project = await create_project(
        db_session,
        tenant_id=org.tenant_id,
        organisation_id=org.id,
        name="Test Project",
        description=None,
        actor="alice",
    )
    assessment = await _make_assessment(
        db_session, other_org, status=OpbohAssessmentStatus.ACCEPTED
    )

    with pytest.raises(IllegalStageAdvancement, match="different organisation"):
        await advance_stage(db_session, project, supporting_assessment=assessment, actor="alice")


async def test_advance_stage_at_the_final_stage_raises(db_session: AsyncSession) -> None:
    org = await _make_tenant_and_org(db_session)
    await _make_stages(db_session, 1)  # only one stage — already at the end
    project = await create_project(
        db_session,
        tenant_id=org.tenant_id,
        organisation_id=org.id,
        name="Test Project",
        description=None,
        actor="alice",
    )
    assessment = await _make_assessment(db_session, org, status=OpbohAssessmentStatus.ACCEPTED)

    with pytest.raises(IllegalStageAdvancement, match="final configured stage"):
        await advance_stage(db_session, project, supporting_assessment=assessment, actor="alice")


# ---------------------------------------------------------------------------
# Stage Checklist Engine — real per-stage entry/exit criteria
# ---------------------------------------------------------------------------


async def test_advance_stage_without_a_checklist_still_needs_an_opboh_assessment(
    db_session: AsyncSession,
) -> None:
    """Regression: a stage with nothing in stage_checklist_items configured
    for it (every stage _make_stages produces, same as before this engine
    existed) falls back to the original OPBOH-assessment path unchanged —
    not "None was passed" silently succeeding."""
    org = await _make_tenant_and_org(db_session)
    await _make_stages(db_session, 2)
    project = await create_project(
        db_session,
        tenant_id=org.tenant_id,
        organisation_id=org.id,
        name="Test Project",
        description=None,
        actor="alice",
    )

    with pytest.raises(IllegalStageAdvancement, match="no checklist configured"):
        await advance_stage(db_session, project, actor="alice")


async def test_advance_stage_with_a_checklist_configured_ignores_an_opboh_assessment(
    db_session: AsyncSession,
) -> None:
    """The other direction: once a stage has its own checklist, an
    accepted OPBOH assessment alone isn't enough — no StageDecision
    recorded yet means no advance, regardless of what's passed in."""
    org = await _make_tenant_and_org(db_session)
    stages = await _make_stages(db_session, 2)
    await _make_checklist_items(db_session, stages[0], ["Criterion A", "Criterion B"])
    project = await create_project(
        db_session,
        tenant_id=org.tenant_id,
        organisation_id=org.id,
        name="Test Project",
        description=None,
        actor="alice",
    )
    assessment = await _make_assessment(db_session, org, status=OpbohAssessmentStatus.ACCEPTED)

    with pytest.raises(IllegalStageAdvancement, match="its own checklist configured"):
        await advance_stage(db_session, project, supporting_assessment=assessment, actor="alice")


async def test_record_stage_decision_rejects_unanswered_items(db_session: AsyncSession) -> None:
    org = await _make_tenant_and_org(db_session)
    stages = await _make_stages(db_session, 2)
    items = await _make_checklist_items(db_session, stages[0], ["Criterion A", "Criterion B"])
    project = await create_project(
        db_session,
        tenant_id=org.tenant_id,
        organisation_id=org.id,
        name="Test Project",
        description=None,
        actor="alice",
    )
    await record_checklist_response(
        db_session,
        project,
        items[0],
        response_value=ChecklistResponseValue.YES,
        comment=None,
        actor="alice",
    )

    with pytest.raises(IllegalStageAdvancement, match="1 checklist item"):
        await record_stage_decision(
            db_session,
            project,
            outcome=StageDecisionOutcome.PROCEED,
            conditions=None,
            actor="dave",
        )


async def test_record_checklist_response_rejects_an_item_from_a_different_stage(
    db_session: AsyncSession,
) -> None:
    org = await _make_tenant_and_org(db_session)
    stages = await _make_stages(db_session, 2)
    other_stage_items = await _make_checklist_items(db_session, stages[1], ["Criterion X"])
    project = await create_project(
        db_session,
        tenant_id=org.tenant_id,
        organisation_id=org.id,
        name="Test Project",
        description=None,
        actor="alice",
    )

    with pytest.raises(IllegalStageAdvancement, match="different stage"):
        await record_checklist_response(
            db_session,
            project,
            other_stage_items[0],
            response_value=ChecklistResponseValue.YES,
            comment=None,
            actor="alice",
        )


async def test_a_decline_decision_still_blocks_advancement(db_session: AsyncSession) -> None:
    """Answering every item doesn't itself unlock the stage — the recorded
    outcome has to actually be an advancing one. DECLINE is a real, named
    way to not proceed, not just an incomplete PROCEED."""
    org = await _make_tenant_and_org(db_session)
    stages = await _make_stages(db_session, 2)
    items = await _make_checklist_items(db_session, stages[0], ["Criterion A"])
    project = await create_project(
        db_session,
        tenant_id=org.tenant_id,
        organisation_id=org.id,
        name="Test Project",
        description=None,
        actor="alice",
    )
    await record_checklist_response(
        db_session,
        project,
        items[0],
        response_value=ChecklistResponseValue.NO,
        comment="Not met.",
        actor="alice",
    )
    await record_stage_decision(
        db_session, project, outcome=StageDecisionOutcome.DECLINE, conditions=None, actor="dave"
    )

    with pytest.raises(IllegalStageAdvancement, match="its own checklist configured"):
        await advance_stage(db_session, project, actor="alice")


async def test_advance_stage_succeeds_via_a_proceed_decision_with_no_assessment(
    db_session: AsyncSession,
) -> None:
    """The real replacement path end to end: answer every item, record a
    PROCEED decision, advance with no OPBOH assessment at all."""
    org = await _make_tenant_and_org(db_session)
    stages = await _make_stages(db_session, 2)
    items = await _make_checklist_items(db_session, stages[0], ["Criterion A", "Criterion B"])
    project = await create_project(
        db_session,
        tenant_id=org.tenant_id,
        organisation_id=org.id,
        name="Test Project",
        description=None,
        actor="alice",
    )
    for item in items:
        await record_checklist_response(
            db_session,
            project,
            item,
            response_value=ChecklistResponseValue.YES,
            comment=None,
            actor="alice",
        )
    await record_stage_decision(
        db_session,
        project,
        outcome=StageDecisionOutcome.PROCEED_WITH_CONDITIONS,
        conditions="Confirm outstanding item next stage.",
        actor="dave",
    )

    decision = await advance_stage(db_session, project, actor="alice")

    assert decision.from_stage_id == stages[0].id
    assert decision.to_stage_id == stages[1].id
    assert decision.supporting_assessment_id is None
    assert project.current_stage_id == stages[1].id


# ---------------------------------------------------------------------------
# reopen_stage — Epic 5 gap-closing
# ---------------------------------------------------------------------------


async def test_reopen_stage_moves_to_an_earlier_stage(db_session: AsyncSession) -> None:
    org = await _make_tenant_and_org(db_session)
    stages = await _make_stages(db_session, 3)
    project = await create_project(
        db_session,
        tenant_id=org.tenant_id,
        organisation_id=org.id,
        name="Test Project",
        description=None,
        actor="alice",
    )
    assessment = await _make_assessment(db_session, org, status=OpbohAssessmentStatus.ACCEPTED)
    await advance_stage(db_session, project, supporting_assessment=assessment, actor="alice")
    assert project.current_stage_id == stages[1].id

    decision = await reopen_stage(
        db_session,
        project,
        target_stage_id=stages[0].id,
        actor="bob",
        reason="Evidence withdrawn — sponsor registration lapsed.",
    )

    assert decision.kind.value == "reopen"
    assert decision.from_stage_id == stages[1].id
    assert decision.to_stage_id == stages[0].id
    assert decision.supporting_assessment_id is None
    assert project.current_stage_id == stages[0].id


async def test_reopen_stage_requires_a_reason(db_session: AsyncSession) -> None:
    org = await _make_tenant_and_org(db_session)
    stages = await _make_stages(db_session, 2)
    project = await create_project(
        db_session,
        tenant_id=org.tenant_id,
        organisation_id=org.id,
        name="Test Project",
        description=None,
        actor="alice",
    )
    assessment = await _make_assessment(db_session, org, status=OpbohAssessmentStatus.ACCEPTED)
    await advance_stage(db_session, project, supporting_assessment=assessment, actor="alice")

    with pytest.raises(IllegalStageAdvancement, match="reason"):
        await reopen_stage(
            db_session, project, target_stage_id=stages[0].id, actor="bob", reason="   "
        )


async def test_reopen_stage_rejects_a_later_or_equal_stage(db_session: AsyncSession) -> None:
    org = await _make_tenant_and_org(db_session)
    stages = await _make_stages(db_session, 3)
    project = await create_project(
        db_session,
        tenant_id=org.tenant_id,
        organisation_id=org.id,
        name="Test Project",
        description=None,
        actor="alice",
    )

    with pytest.raises(IllegalStageAdvancement, match="earlier"):
        await reopen_stage(
            db_session, project, target_stage_id=stages[2].id, actor="bob", reason="Mistake."
        )
    with pytest.raises(IllegalStageAdvancement, match="earlier"):
        await reopen_stage(
            db_session, project, target_stage_id=stages[0].id, actor="bob", reason="Mistake."
        )


# ---------------------------------------------------------------------------
# assign_stage — Epic 5 gap-closing
# ---------------------------------------------------------------------------


async def test_assign_stage_sets_owner_and_due_date(db_session: AsyncSession) -> None:
    org = await _make_tenant_and_org(db_session)
    await _make_stages(db_session, 1)
    project = await create_project(
        db_session,
        tenant_id=org.tenant_id,
        organisation_id=org.id,
        name="Test Project",
        description=None,
        actor="alice",
    )

    updated = await assign_stage(
        db_session, project, assigned_to="carol", due_date=date(2026, 12, 1), actor="alice"
    )

    assert updated.assigned_to == "carol"
    assert updated.stage_due_date == date(2026, 12, 1)


async def test_advancing_resets_the_stage_assignment(db_session: AsyncSession) -> None:
    org = await _make_tenant_and_org(db_session)
    await _make_stages(db_session, 2)
    project = await create_project(
        db_session,
        tenant_id=org.tenant_id,
        organisation_id=org.id,
        name="Test Project",
        description=None,
        actor="alice",
    )
    await assign_stage(
        db_session, project, assigned_to="carol", due_date=date(2026, 12, 1), actor="alice"
    )
    assessment = await _make_assessment(db_session, org, status=OpbohAssessmentStatus.ACCEPTED)

    await advance_stage(db_session, project, supporting_assessment=assessment, actor="alice")

    assert project.assigned_to is None
    assert project.stage_due_date is None


# ---------------------------------------------------------------------------
# compute_project_rag — Epic 5 gap-closing
# ---------------------------------------------------------------------------


async def test_rag_is_grey_with_no_linked_assessment(db_session: AsyncSession) -> None:
    org = await _make_tenant_and_org(db_session)
    await _make_stages(db_session, 1)
    project = await create_project(
        db_session,
        tenant_id=org.tenant_id,
        organisation_id=org.id,
        name="Test Project",
        description=None,
        actor="alice",
    )

    assert await compute_project_rag(db_session, project) == RagStatus.GREY


async def test_rag_is_red_for_a_vacuously_clean_but_empty_assessment(
    db_session: AsyncSession,
) -> None:
    """No domains at all — vacuously clean in opboh_scoring terms (nothing
    configured means nothing could fail, so
    AssessmentResult.is_clean is True — see
    test_opboh_scoring.py::test_empty_assessment_scores_zero_but_is_vacuously_clean).
    But under the real Assurance Score formula, zero domains scored also
    means assurance_score is 0.0/100, and RagStatus now mirrors
    AssessmentResult.rag exactly (compute_project_rag's docstring) rather
    than re-deriving its own is_clean-based rule the way it used to. Zero
    domains scored is zero assurance established, not a clean bill of
    health, so Red is the right answer here, not Green — this replaces a
    stale Green expectation left over from before real scoring landed
    (29b9e65), which changed this exact rule without this exact test
    having been run first (no Postgres in that commit's own local check,
    per its own message — see git history)."""
    org = await _make_tenant_and_org(db_session)
    await _make_stages(db_session, 1)
    project = await create_project(
        db_session,
        tenant_id=org.tenant_id,
        organisation_id=org.id,
        name="Test Project",
        description=None,
        actor="alice",
    )
    await _make_assessment(db_session, org, status=OpbohAssessmentStatus.ACCEPTED, project=project)

    assert await compute_project_rag(db_session, project) == RagStatus.RED


async def test_rag_is_green_for_an_assessment_with_a_real_answered_domain(
    db_session: AsyncSession,
) -> None:
    """The real Green case the old test above never actually exercised —
    an answered domain, above its own threshold, no critical failures."""
    org = await _make_tenant_and_org(db_session)
    await _make_stages(db_session, 1)
    project = await create_project(
        db_session,
        tenant_id=org.tenant_id,
        organisation_id=org.id,
        name="Test Project",
        description=None,
        actor="alice",
    )
    assessment = await _make_assessment(
        db_session, org, status=OpbohAssessmentStatus.ACCEPTED, project=project
    )
    domain = OpbohDomain(
        id=uuid.uuid4(),
        framework_version_id=assessment.framework_version_id,
        code="sponsor",
        name="Sponsor Readiness",
        weight=1.0,
        min_score_threshold=3.0,
    )
    db_session.add(domain)
    await db_session.flush()
    question = OpbohQuestion(
        id=uuid.uuid4(),
        domain_id=domain.id,
        control_objective="Sponsor has clear legal existence",
        question_text="Is the sponsor a validly registered legal entity?",
        is_critical_control=False,
        pass_threshold=3.0,
    )
    db_session.add(question)
    await db_session.flush()
    db_session.add(
        OpbohResponse(
            id=uuid.uuid4(),
            assessment_id=assessment.id,
            question_id=question.id,
            response_value=OpbohResponseValue.YES,
            score=5,
            evidence_sufficiency_factor=1.0,
            created_by="alice",
            updated_by="alice",
        )
    )
    await db_session.flush()

    assert await compute_project_rag(db_session, project) == RagStatus.GREEN


async def test_rag_is_red_when_a_critical_control_has_failed(db_session: AsyncSession) -> None:
    org = await _make_tenant_and_org(db_session)
    await _make_stages(db_session, 1)
    project = await create_project(
        db_session,
        tenant_id=org.tenant_id,
        organisation_id=org.id,
        name="Test Project",
        description=None,
        actor="alice",
    )
    assessment = await _make_assessment(
        db_session, org, status=OpbohAssessmentStatus.CONDITIONALLY_ACCEPTED, project=project
    )
    domain = OpbohDomain(
        id=uuid.uuid4(),
        framework_version_id=assessment.framework_version_id,
        code="sponsor",
        name="Sponsor Readiness",
        weight=1.0,
        min_score_threshold=3.0,
    )
    db_session.add(domain)
    await db_session.flush()
    db_session.add(
        OpbohQuestion(
            id=uuid.uuid4(),
            domain_id=domain.id,
            control_objective="Sponsor has clear legal existence",
            question_text="Is the sponsor a validly registered legal entity?",
            is_critical_control=True,
            pass_threshold=5.0,
        )
    )
    await db_session.flush()

    assert await compute_project_rag(db_session, project) == RagStatus.RED


# ---------------------------------------------------------------------------
# list_open_findings_for_project — Epic 5 gap-closing
# ---------------------------------------------------------------------------


async def test_list_open_findings_excludes_closed_ones(db_session: AsyncSession) -> None:
    org = await _make_tenant_and_org(db_session)
    await _make_stages(db_session, 1)
    project = await create_project(
        db_session,
        tenant_id=org.tenant_id,
        organisation_id=org.id,
        name="Test Project",
        description=None,
        actor="alice",
    )
    assessment = await _make_assessment(
        db_session, org, status=OpbohAssessmentStatus.CONDITIONALLY_ACCEPTED, project=project
    )
    db_session.add_all(
        [
            OpbohFinding(
                id=uuid.uuid4(),
                tenant_id=org.tenant_id,
                assessment_id=assessment.id,
                severity=FindingSeverity.HIGH,
                description="Open finding",
                status=FindingStatus.OPEN,
                created_by="alice",
                updated_by="alice",
            ),
            OpbohFinding(
                id=uuid.uuid4(),
                tenant_id=org.tenant_id,
                assessment_id=assessment.id,
                severity=FindingSeverity.LOW,
                description="In-progress finding",
                status=FindingStatus.IN_PROGRESS,
                created_by="alice",
                updated_by="alice",
            ),
            OpbohFinding(
                id=uuid.uuid4(),
                tenant_id=org.tenant_id,
                assessment_id=assessment.id,
                severity=FindingSeverity.MEDIUM,
                description="Closed finding",
                status=FindingStatus.CLOSED,
                created_by="alice",
                updated_by="alice",
            ),
        ]
    )
    await db_session.flush()

    findings = await list_open_findings_for_project(db_session, project)

    assert {f.description for f in findings} == {"Open finding", "In-progress finding"}
