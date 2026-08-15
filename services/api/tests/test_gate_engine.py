"""Service-level Gate Engine tests. Only flush()es via db_session (never
commit()) — same non-leaking pattern as test_stage_engine.py and
test_framework_registry.py.

Every project's current_stage_id is set directly after creation rather
than relying on create_project's "globally lowest active stage" picker —
sidesteps that ambiguity entirely instead of fighting it, since these
tests need a project sitting at one *specific* stage (the gate's trigger
stage), not whichever stage happens to sort lowest this run.
"""

import uuid
from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ipacgs.models.gate import Gate, GateCertificate, GateDecisionStatus, GateVoteOutcome
from ipacgs.models.opboh import OpbohAssessment, OpbohAssessmentStatus, OpbohFrameworkVersion
from ipacgs.models.organisation import Organisation
from ipacgs.models.project import Project, ProjectStatus, Stage
from ipacgs.models.tenant import Tenant
from ipacgs.services.gate_engine import (
    IllegalGateDecision,
    assemble_readiness_pack,
    cast_vote,
    gate_blocking_advancement,
    open_gate_decision,
    suspend_gate_decision,
)
from ipacgs.services.stage_engine import IllegalStageAdvancement, advance_stage


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


async def _make_two_stages(db_session: AsyncSession) -> tuple[Stage, Stage]:
    base = uuid.uuid4().int % 1_000_000 * 100
    stage_a = Stage(
        id=uuid.uuid4(),
        code=_unique("stg-a"),
        name="Stage A",
        sequence=base,
        is_active=True,
        created_by="seed",
        updated_by="seed",
    )
    stage_b = Stage(
        id=uuid.uuid4(),
        code=_unique("stg-b"),
        name="Stage B",
        sequence=base + 10,
        is_active=True,
        created_by="seed",
        updated_by="seed",
    )
    db_session.add_all([stage_a, stage_b])
    await db_session.flush()
    return stage_a, stage_b


async def _make_project_at(db_session: AsyncSession, org: Organisation, stage: Stage) -> Project:
    project = Project(
        id=uuid.uuid4(),
        tenant_id=org.tenant_id,
        organisation_id=org.id,
        name="Test Project",
        current_stage_id=stage.id,
        status=ProjectStatus.ACTIVE,
        created_by="alice",
        updated_by="alice",
    )
    db_session.add(project)
    await db_session.flush()
    return project


async def _make_gate(
    db_session: AsyncSession, trigger_stage: Stage, *, required_quorum: int = 1
) -> Gate:
    gate = Gate(
        id=uuid.uuid4(),
        code=_unique("gate"),
        name="Test Gate",
        sequence=uuid.uuid4().int % 1_000_000,
        trigger_stage_id=trigger_stage.id,
        required_quorum=required_quorum,
        is_active=True,
        created_by="seed",
        updated_by="seed",
    )
    db_session.add(gate)
    await db_session.flush()
    return gate


async def _make_assessment(
    db_session: AsyncSession,
    org: Organisation,
    project: Project,
    *,
    status: OpbohAssessmentStatus,
    prepared_by: str = "alice",
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
        project_id=project.id,
        status=status,
        prepared_by=prepared_by,
        has_critical_failure=False,
        created_by=prepared_by,
        updated_by=prepared_by,
    )
    db_session.add(assessment)
    await db_session.flush()
    return assessment


# ---------------------------------------------------------------------------
# open_gate_decision
# ---------------------------------------------------------------------------


async def test_open_gate_decision_succeeds_at_the_trigger_stage(db_session: AsyncSession) -> None:
    org = await _make_tenant_and_org(db_session)
    stage_a, _stage_b = await _make_two_stages(db_session)
    project = await _make_project_at(db_session, org, stage_a)
    gate = await _make_gate(db_session, stage_a)

    decision = await open_gate_decision(db_session, project, gate, actor="alice")

    assert decision.status == GateDecisionStatus.PENDING
    assert decision.opened_by == "alice"


async def test_open_gate_decision_rejects_a_project_not_at_the_trigger_stage(
    db_session: AsyncSession,
) -> None:
    org = await _make_tenant_and_org(db_session)
    stage_a, stage_b = await _make_two_stages(db_session)
    project = await _make_project_at(db_session, org, stage_b)
    gate = await _make_gate(db_session, stage_a)

    with pytest.raises(IllegalGateDecision, match="trigger stage"):
        await open_gate_decision(db_session, project, gate, actor="alice")


async def test_open_gate_decision_rejects_a_second_open_decision(db_session: AsyncSession) -> None:
    org = await _make_tenant_and_org(db_session)
    stage_a, _stage_b = await _make_two_stages(db_session)
    project = await _make_project_at(db_session, org, stage_a)
    gate = await _make_gate(db_session, stage_a)
    await open_gate_decision(db_session, project, gate, actor="alice")

    with pytest.raises(IllegalGateDecision, match="already has an open decision"):
        await open_gate_decision(db_session, project, gate, actor="alice")


# ---------------------------------------------------------------------------
# cast_vote
# ---------------------------------------------------------------------------


async def test_a_single_proceed_vote_finalizes_a_quorum_one_gate(
    db_session: AsyncSession,
) -> None:
    org = await _make_tenant_and_org(db_session)
    stage_a, _stage_b = await _make_two_stages(db_session)
    project = await _make_project_at(db_session, org, stage_a)
    gate = await _make_gate(db_session, stage_a, required_quorum=1)
    decision = await open_gate_decision(db_session, project, gate, actor="alice")

    await cast_vote(db_session, decision, project, voter="bob", outcome=GateVoteOutcome.PROCEED)

    assert decision.status == GateDecisionStatus.PROCEED
    assert decision.decided_at is not None


async def test_quorum_two_needs_two_distinct_proceed_votes(db_session: AsyncSession) -> None:
    org = await _make_tenant_and_org(db_session)
    stage_a, _stage_b = await _make_two_stages(db_session)
    project = await _make_project_at(db_session, org, stage_a)
    gate = await _make_gate(db_session, stage_a, required_quorum=2)
    decision = await open_gate_decision(db_session, project, gate, actor="alice")

    await cast_vote(db_session, decision, project, voter="bob", outcome=GateVoteOutcome.PROCEED)
    assert decision.status == GateDecisionStatus.PENDING

    await cast_vote(db_session, decision, project, voter="carol", outcome=GateVoteOutcome.PROCEED)
    assert decision.status == GateDecisionStatus.PROCEED


async def test_a_single_hold_vote_finalizes_immediately_regardless_of_quorum(
    db_session: AsyncSession,
) -> None:
    org = await _make_tenant_and_org(db_session)
    stage_a, _stage_b = await _make_two_stages(db_session)
    project = await _make_project_at(db_session, org, stage_a)
    gate = await _make_gate(db_session, stage_a, required_quorum=5)
    decision = await open_gate_decision(db_session, project, gate, actor="alice")

    await cast_vote(db_session, decision, project, voter="bob", outcome=GateVoteOutcome.HOLD)

    assert decision.status == GateDecisionStatus.HOLD


async def test_the_same_voter_cannot_vote_twice(db_session: AsyncSession) -> None:
    org = await _make_tenant_and_org(db_session)
    stage_a, _stage_b = await _make_two_stages(db_session)
    project = await _make_project_at(db_session, org, stage_a)
    gate = await _make_gate(db_session, stage_a, required_quorum=5)
    decision = await open_gate_decision(db_session, project, gate, actor="alice")
    await cast_vote(db_session, decision, project, voter="bob", outcome=GateVoteOutcome.PROCEED)

    with pytest.raises(IllegalGateDecision, match="already voted"):
        await cast_vote(db_session, decision, project, voter="bob", outcome=GateVoteOutcome.PROCEED)


async def test_the_assessment_preparer_cannot_also_vote(db_session: AsyncSession) -> None:
    org = await _make_tenant_and_org(db_session)
    stage_a, _stage_b = await _make_two_stages(db_session)
    project = await _make_project_at(db_session, org, stage_a)
    gate = await _make_gate(db_session, stage_a)
    await _make_assessment(
        db_session, org, project, status=OpbohAssessmentStatus.ACCEPTED, prepared_by="dave"
    )
    decision = await open_gate_decision(db_session, project, gate, actor="alice")

    with pytest.raises(IllegalGateDecision, match="prepared the assessment"):
        await cast_vote(
            db_session, decision, project, voter="dave", outcome=GateVoteOutcome.PROCEED
        )


async def test_voting_on_an_already_decided_gate_is_rejected(db_session: AsyncSession) -> None:
    org = await _make_tenant_and_org(db_session)
    stage_a, _stage_b = await _make_two_stages(db_session)
    project = await _make_project_at(db_session, org, stage_a)
    gate = await _make_gate(db_session, stage_a, required_quorum=1)
    decision = await open_gate_decision(db_session, project, gate, actor="alice")
    await cast_vote(db_session, decision, project, voter="bob", outcome=GateVoteOutcome.PROCEED)

    with pytest.raises(IllegalGateDecision, match="no further votes"):
        await cast_vote(
            db_session, decision, project, voter="carol", outcome=GateVoteOutcome.PROCEED
        )


async def test_a_proceed_decision_issues_a_certificate_with_a_real_hash(
    db_session: AsyncSession,
) -> None:
    org = await _make_tenant_and_org(db_session)
    stage_a, _stage_b = await _make_two_stages(db_session)
    project = await _make_project_at(db_session, org, stage_a)
    gate = await _make_gate(db_session, stage_a, required_quorum=1)
    decision = await open_gate_decision(db_session, project, gate, actor="alice")

    await cast_vote(db_session, decision, project, voter="bob", outcome=GateVoteOutcome.PROCEED)

    # Queried directly rather than via decision.certificate — that
    # relationship is lazy by default, which async SQLAlchemy can't
    # resolve on plain attribute access outside an explicit load.
    result = await db_session.execute(
        select(GateCertificate).where(GateCertificate.gate_decision_id == decision.id)
    )
    certificate = result.scalars().one()
    assert len(certificate.content_hash) == 64
    int(certificate.content_hash, 16)  # raises if it isn't real hex


# ---------------------------------------------------------------------------
# suspend_gate_decision
# ---------------------------------------------------------------------------


async def test_suspend_requires_a_proceed_decision(db_session: AsyncSession) -> None:
    org = await _make_tenant_and_org(db_session)
    stage_a, _stage_b = await _make_two_stages(db_session)
    project = await _make_project_at(db_session, org, stage_a)
    gate = await _make_gate(db_session, stage_a)
    decision = await open_gate_decision(db_session, project, gate, actor="alice")

    with pytest.raises(IllegalGateDecision, match="nothing to suspend"):
        await suspend_gate_decision(db_session, decision, actor="alice", reason="test")


async def test_suspend_requires_a_reason(db_session: AsyncSession) -> None:
    org = await _make_tenant_and_org(db_session)
    stage_a, _stage_b = await _make_two_stages(db_session)
    project = await _make_project_at(db_session, org, stage_a)
    gate = await _make_gate(db_session, stage_a, required_quorum=1)
    decision = await open_gate_decision(db_session, project, gate, actor="alice")
    await cast_vote(db_session, decision, project, voter="bob", outcome=GateVoteOutcome.PROCEED)

    with pytest.raises(IllegalGateDecision, match="requires a reason"):
        await suspend_gate_decision(db_session, decision, actor="alice", reason="   ")


async def test_suspend_moves_a_proceed_decision_to_suspended(db_session: AsyncSession) -> None:
    org = await _make_tenant_and_org(db_session)
    stage_a, _stage_b = await _make_two_stages(db_session)
    project = await _make_project_at(db_session, org, stage_a)
    gate = await _make_gate(db_session, stage_a, required_quorum=1)
    decision = await open_gate_decision(db_session, project, gate, actor="alice")
    await cast_vote(db_session, decision, project, voter="bob", outcome=GateVoteOutcome.PROCEED)

    await suspend_gate_decision(db_session, decision, actor="alice", reason="Evidence withdrawn.")

    assert decision.status == GateDecisionStatus.SUSPENDED
    assert decision.suspension_reason == "Evidence withdrawn."


# ---------------------------------------------------------------------------
# assemble_readiness_pack
# ---------------------------------------------------------------------------


async def test_readiness_pack_reflects_current_rag_and_findings(db_session: AsyncSession) -> None:
    org = await _make_tenant_and_org(db_session)
    stage_a, _stage_b = await _make_two_stages(db_session)
    project = await _make_project_at(db_session, org, stage_a)
    gate = await _make_gate(db_session, stage_a)

    pack = await assemble_readiness_pack(db_session, project, gate)

    assert pack.gate_code == gate.code
    assert pack.rag_status.value == "grey"  # no assessment linked yet
    assert pack.open_finding_count == 0


# ---------------------------------------------------------------------------
# Non-bypassable — the actual integration with stage_engine.advance_stage
# ---------------------------------------------------------------------------


async def test_advance_stage_is_blocked_by_an_unresolved_gate(db_session: AsyncSession) -> None:
    org = await _make_tenant_and_org(db_session)
    stage_a, stage_b = await _make_two_stages(db_session)
    project = await _make_project_at(db_session, org, stage_a)
    await _make_gate(db_session, stage_a)  # pending forever — nobody's voted
    assessment = await _make_assessment(
        db_session, org, project, status=OpbohAssessmentStatus.ACCEPTED
    )

    with pytest.raises(IllegalStageAdvancement, match="must reach a PROCEED decision"):
        await advance_stage(db_session, project, supporting_assessment=assessment, actor="alice")

    assert project.current_stage_id == stage_a.id  # unchanged


async def test_advance_stage_succeeds_once_the_gate_has_proceeded(
    db_session: AsyncSession,
) -> None:
    org = await _make_tenant_and_org(db_session)
    stage_a, stage_b = await _make_two_stages(db_session)
    project = await _make_project_at(db_session, org, stage_a)
    gate = await _make_gate(db_session, stage_a, required_quorum=1)
    decision = await open_gate_decision(db_session, project, gate, actor="alice")
    await cast_vote(db_session, decision, project, voter="bob", outcome=GateVoteOutcome.PROCEED)
    assessment = await _make_assessment(
        db_session, org, project, status=OpbohAssessmentStatus.ACCEPTED
    )

    await advance_stage(db_session, project, supporting_assessment=assessment, actor="alice")

    assert project.current_stage_id == stage_b.id


async def test_advance_stage_is_unaffected_when_no_gate_is_configured(
    db_session: AsyncSession,
) -> None:
    org = await _make_tenant_and_org(db_session)
    stage_a, stage_b = await _make_two_stages(db_session)
    project = await _make_project_at(db_session, org, stage_a)
    assessment = await _make_assessment(
        db_session, org, project, status=OpbohAssessmentStatus.ACCEPTED
    )

    await advance_stage(db_session, project, supporting_assessment=assessment, actor="alice")

    assert project.current_stage_id == stage_b.id


async def test_gate_blocking_advancement_reports_the_blocking_gate(
    db_session: AsyncSession,
) -> None:
    org = await _make_tenant_and_org(db_session)
    stage_a, _stage_b = await _make_two_stages(db_session)
    project = await _make_project_at(db_session, org, stage_a)
    gate = await _make_gate(db_session, stage_a)

    blocking = await gate_blocking_advancement(db_session, project, project.current_stage_id)

    assert blocking is not None
    assert blocking.id == gate.id
