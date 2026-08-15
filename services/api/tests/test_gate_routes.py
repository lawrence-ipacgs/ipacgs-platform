"""HTTP-level Gate Engine tests. Route handlers commit for real — same
leak-awareness as test_project_routes.py and test_opboh_routes.py.

Gates don't need the same "widely-separated sequence" defense Stage did:
every gate lookup in this codebase is an exact match on trigger_stage_id
(a specific, randomly-generated Stage UUID), never an ambient "lowest/
likely" scan — see models/gate.py's module docstring. What Gate tests do
still need is a project sitting at a *known* stage: rather than fighting
create_project's own "globally lowest active stage" picker, every test
here reads back whichever stage the project actually started at (
guaranteed to be `stage_a`, by the same widely-separated + deactivated-
on-teardown two_stages fixture test_project_routes.py already
established) and attaches the gate to that.
"""

import uuid
from collections.abc import AsyncGenerator
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from ipacgs.core.security import CurrentUser, get_current_user
from ipacgs.main import app
from ipacgs.models.gate import Gate
from ipacgs.models.opboh import OpbohAssessment, OpbohAssessmentStatus, OpbohFrameworkVersion
from ipacgs.models.organisation import Organisation
from ipacgs.models.project import Stage
from ipacgs.models.tenant import Tenant


def _as(object_id: str) -> None:
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        object_id=object_id, display_name=object_id, roles=(), raw_claims={}
    )


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


@pytest.fixture(autouse=True)
async def _clear_overrides() -> AsyncGenerator[None, None]:
    yield
    app.dependency_overrides.clear()


@pytest.fixture
async def organisation(db_session: AsyncSession) -> Organisation:
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
    await db_session.commit()
    return org


@pytest.fixture
async def two_stages(db_session: AsyncSession) -> AsyncGenerator[tuple[Stage, Stage], None]:
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
    await db_session.commit()
    try:
        yield stage_a, stage_b
    finally:
        stage_a.is_active = False
        stage_b.is_active = False
        await db_session.commit()


async def _create_project(client: AsyncClient, organisation: Organisation) -> str:
    resp = await client.post(
        "/projects", json={"organisation_id": str(organisation.id), "name": "Test Project"}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]  # type: ignore[no-any-return]


async def _create_gate(
    client: AsyncClient, db_session: AsyncSession, trigger_stage: Stage, *, required_quorum: int = 1
) -> str:
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
    await db_session.commit()
    return str(gate.id)


async def _accepted_assessment(db_session: AsyncSession, org: Organisation, project_id: str) -> str:
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
        project_id=uuid.UUID(project_id),
        status=OpbohAssessmentStatus.ACCEPTED,
        prepared_by="alice",
        has_critical_failure=False,
        created_by="alice",
        updated_by="alice",
    )
    db_session.add(assessment)
    await db_session.commit()
    return str(assessment.id)


async def test_open_vote_and_fetch_a_gate_decision(
    client: AsyncClient,
    organisation: Organisation,
    two_stages: tuple[Stage, Stage],
    db_session: AsyncSession,
) -> None:
    stage_a, _stage_b = two_stages
    gate_id = await _create_gate(client, db_session, stage_a, required_quorum=1)
    _as("alice")
    project_id = await _create_project(client, organisation)

    open_resp = await client.post(f"/projects/{project_id}/gates/{gate_id}/open")
    assert open_resp.status_code == 201, open_resp.text
    decision_id = open_resp.json()["id"]
    assert open_resp.json()["status"] == "pending"

    vote_resp = await client.post(
        f"/gate-decisions/{decision_id}/vote", json={"outcome": "proceed"}
    )
    assert vote_resp.status_code == 200, vote_resp.text
    body = vote_resp.json()
    assert body["status"] == "proceed"
    assert len(body["votes"]) == 1
    assert body["certificate"] is not None
    assert len(body["certificate"]["content_hash"]) == 64

    get_resp = await client.get(f"/gate-decisions/{decision_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["status"] == "proceed"


async def test_a_hold_vote_finalizes_to_hold(
    client: AsyncClient,
    organisation: Organisation,
    two_stages: tuple[Stage, Stage],
    db_session: AsyncSession,
) -> None:
    stage_a, _stage_b = two_stages
    gate_id = await _create_gate(client, db_session, stage_a, required_quorum=3)
    _as("alice")
    project_id = await _create_project(client, organisation)
    open_resp = await client.post(f"/projects/{project_id}/gates/{gate_id}/open")
    decision_id = open_resp.json()["id"]

    vote_resp = await client.post(f"/gate-decisions/{decision_id}/vote", json={"outcome": "hold"})
    assert vote_resp.status_code == 200
    assert vote_resp.json()["status"] == "hold"
    assert vote_resp.json()["certificate"] is None


async def test_suspend_a_proceeded_decision(
    client: AsyncClient,
    organisation: Organisation,
    two_stages: tuple[Stage, Stage],
    db_session: AsyncSession,
) -> None:
    stage_a, _stage_b = two_stages
    gate_id = await _create_gate(client, db_session, stage_a, required_quorum=1)
    _as("alice")
    project_id = await _create_project(client, organisation)
    open_resp = await client.post(f"/projects/{project_id}/gates/{gate_id}/open")
    decision_id = open_resp.json()["id"]
    await client.post(f"/gate-decisions/{decision_id}/vote", json={"outcome": "proceed"})

    suspend_resp = await client.post(
        f"/gate-decisions/{decision_id}/suspend", json={"reason": "Fraud indicator raised."}
    )
    assert suspend_resp.status_code == 200, suspend_resp.text
    assert suspend_resp.json()["status"] == "suspended"
    assert suspend_resp.json()["suspension_reason"] == "Fraud indicator raised."


async def test_readiness_pack_route(
    client: AsyncClient,
    organisation: Organisation,
    two_stages: tuple[Stage, Stage],
    db_session: AsyncSession,
) -> None:
    stage_a, _stage_b = two_stages
    gate_id = await _create_gate(client, db_session, stage_a)
    _as("alice")
    project_id = await _create_project(client, organisation)

    resp = await client.get(f"/projects/{project_id}/gates/{gate_id}/readiness-pack")
    assert resp.status_code == 200
    assert resp.json()["rag_status"] == "grey"
    assert resp.json()["open_finding_count"] == 0


async def test_blocking_gate_route_reports_the_unresolved_gate(
    client: AsyncClient,
    organisation: Organisation,
    two_stages: tuple[Stage, Stage],
    db_session: AsyncSession,
) -> None:
    stage_a, _stage_b = two_stages
    gate_id = await _create_gate(client, db_session, stage_a)
    _as("alice")
    project_id = await _create_project(client, organisation)

    resp = await client.get(f"/projects/{project_id}/blocking-gate")
    assert resp.status_code == 200
    assert resp.json()["id"] == gate_id


async def test_blocking_gate_route_is_null_with_no_gate_configured(
    client: AsyncClient, organisation: Organisation, two_stages: tuple[Stage, Stage]
) -> None:
    _as("alice")
    project_id = await _create_project(client, organisation)

    resp = await client.get(f"/projects/{project_id}/blocking-gate")
    assert resp.status_code == 200
    assert resp.json() is None


async def test_advance_stage_over_http_is_blocked_by_an_unresolved_gate(
    client: AsyncClient,
    organisation: Organisation,
    two_stages: tuple[Stage, Stage],
    db_session: AsyncSession,
) -> None:
    stage_a, _stage_b = two_stages
    await _create_gate(client, db_session, stage_a)  # nobody's voted on it
    _as("alice")
    project_id = await _create_project(client, organisation)
    assessment_id = await _accepted_assessment(db_session, organisation, project_id)

    resp = await client.post(
        f"/projects/{project_id}/advance-stage",
        json={"supporting_assessment_id": assessment_id},
    )
    assert resp.status_code == 409
    assert "PROCEED" in resp.json()["detail"]


async def test_advance_stage_over_http_succeeds_once_the_gate_has_proceeded(
    client: AsyncClient,
    organisation: Organisation,
    two_stages: tuple[Stage, Stage],
    db_session: AsyncSession,
) -> None:
    stage_a, stage_b = two_stages
    gate_id = await _create_gate(client, db_session, stage_a, required_quorum=1)
    _as("alice")
    project_id = await _create_project(client, organisation)
    open_resp = await client.post(f"/projects/{project_id}/gates/{gate_id}/open")
    decision_id = open_resp.json()["id"]
    await client.post(f"/gate-decisions/{decision_id}/vote", json={"outcome": "proceed"})
    assessment_id = await _accepted_assessment(db_session, organisation, project_id)

    resp = await client.post(
        f"/projects/{project_id}/advance-stage",
        json={"supporting_assessment_id": assessment_id},
    )
    assert resp.status_code == 200, resp.text

    project_resp = await client.get(f"/projects/{project_id}")
    assert project_resp.json()["current_stage_id"] == str(stage_b.id)


async def test_opening_a_gate_decision_for_an_unknown_gate_is_404(
    client: AsyncClient, organisation: Organisation
) -> None:
    _as("alice")
    project_id = await _create_project(client, organisation)

    resp = await client.post(f"/projects/{project_id}/gates/{uuid.uuid4()}/open")
    assert resp.status_code == 404


async def test_opening_a_gate_decision_for_an_unknown_project_is_404(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    stage = Stage(
        id=uuid.uuid4(),
        code=_unique("stg"),
        name="Stage",
        sequence=uuid.uuid4().int % 1_000_000,
        is_active=True,
        created_by="seed",
        updated_by="seed",
    )
    db_session.add(stage)
    await db_session.flush()
    gate = Gate(
        id=uuid.uuid4(),
        code=_unique("gate"),
        name="Test Gate",
        sequence=1,
        trigger_stage_id=stage.id,
        required_quorum=1,
        is_active=True,
        created_by="seed",
        updated_by="seed",
    )
    db_session.add(gate)
    await db_session.commit()

    _as("alice")
    resp = await client.post(f"/projects/{uuid.uuid4()}/gates/{gate.id}/open")
    assert resp.status_code == 404

    stage.is_active = False
    await db_session.commit()
