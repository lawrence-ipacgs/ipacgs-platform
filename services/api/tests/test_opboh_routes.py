"""End-to-end: the OPBOH lifecycle over real HTTP, through the actual
FastAPI routes — the first test in this repo that exercises the whole
stack together (routes, services, scoring, SOD) rather than one layer at
a time.

`get_current_user` needs a real Entra ID token in production; here it's
swapped for a FastAPI dependency override returning a fixed identity, which
is the standard way to test authenticated routes without one. `_as()`
below is the toggle a test uses to submit a request "as" a different actor,
which is exactly what makes the SOD tests possible over HTTP.
"""

import uuid
from collections.abc import AsyncGenerator
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from ipacgs.core.security import CurrentUser, get_current_user
from ipacgs.main import app
from ipacgs.models.opboh import OpbohDomain, OpbohFrameworkVersion, OpbohQuestion
from ipacgs.models.organisation import Organisation
from ipacgs.models.project import Project, ProjectStatus, Stage
from ipacgs.models.tenant import Tenant


def _as(object_id: str) -> None:
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        object_id=object_id, display_name=object_id, roles=(), raw_claims={}
    )


@pytest.fixture(autouse=True)
async def _clear_overrides() -> AsyncGenerator[None, None]:
    yield
    app.dependency_overrides.clear()


@pytest.fixture
async def organisation(db_session: AsyncSession) -> Organisation:
    tenant = Tenant(
        id=uuid.uuid4(), name="Test Tenant", slug=f"t-{uuid.uuid4()}", created_by="seed"
    )
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
async def catalogue(
    db_session: AsyncSession,
) -> tuple[OpbohFrameworkVersion, OpbohQuestion, OpbohQuestion]:
    """One active framework version, one domain, two questions — one
    critical, one not. Just enough to exercise the scoring engine's
    critical-failure path end to end."""
    version = OpbohFrameworkVersion(
        id=uuid.uuid4(),
        # version_label is String(20) — a real version label is short
        # ("1.1", "2.0-beta"); a full UUID as the "make it unique per test"
        # suffix blew straight through that, which is exactly what CI's
        # Postgres caught and this sandbox's DB-less checks couldn't.
        version_label=f"t-{uuid.uuid4().hex[:8]}",
        effective_from=date(2026, 1, 1),
        is_active=True,
        created_by="seed",
        updated_by="seed",
    )
    db_session.add(version)
    await db_session.flush()

    domain = OpbohDomain(
        id=uuid.uuid4(),
        framework_version_id=version.id,
        code="sponsor",
        name="Sponsor Readiness",
        weight=1.0,
        min_score_threshold=0.6,
    )
    db_session.add(domain)
    await db_session.flush()

    critical_q = OpbohQuestion(
        id=uuid.uuid4(),
        domain_id=domain.id,
        control_objective="Sponsor has clear legal existence",
        question_text="Is the sponsor a validly registered legal entity?",
        is_critical_control=True,
        pass_threshold=1.0,
    )
    ordinary_q = OpbohQuestion(
        id=uuid.uuid4(),
        domain_id=domain.id,
        control_objective="Sponsor has a stated track record",
        question_text="Does the sponsor have a track record on similar projects?",
        is_critical_control=False,
        pass_threshold=0.5,
    )
    db_session.add_all([critical_q, ordinary_q])
    await db_session.commit()
    return version, critical_q, ordinary_q


async def test_full_lifecycle_clean_accept(
    client: AsyncClient,
    organisation: Organisation,
    catalogue: tuple[OpbohFrameworkVersion, OpbohQuestion, OpbohQuestion],
) -> None:
    _version, critical_q, ordinary_q = catalogue

    _as("alice")
    create_resp = await client.post(
        "/opboh/assessments", json={"organisation_id": str(organisation.id)}
    )
    assert create_resp.status_code == 201, create_resp.text
    assessment_id = create_resp.json()["id"]
    assert create_resp.json()["status"] == "draft"
    assert create_resp.json()["prepared_by"] == "alice"

    for q in (critical_q, ordinary_q):
        answer_resp = await client.post(
            f"/opboh/assessments/{assessment_id}/responses",
            json={"question_id": str(q.id), "score": 1.0, "evidence_sufficient": True},
        )
        assert answer_resp.status_code == 200, answer_resp.text

    submit_resp = await client.post(f"/opboh/assessments/{assessment_id}/submit")
    assert submit_resp.status_code == 200
    assert submit_resp.json()["status"] == "submitted"

    _as("bob")
    begin_resp = await client.post(f"/opboh/assessments/{assessment_id}/begin-assessment")
    assert begin_resp.status_code == 200
    assert begin_resp.json()["assessed_by"] == "bob"

    _as("carol")
    review_resp = await client.post(f"/opboh/assessments/{assessment_id}/independently-review")
    assert review_resp.status_code == 200
    assert review_resp.json()["reviewed_by"] == "carol"

    score_resp = await client.get(f"/opboh/assessments/{assessment_id}/score")
    assert score_resp.status_code == 200
    score_body = score_resp.json()
    assert score_body["overall_score"] == 1.0
    assert score_body["has_critical_failure"] is False
    assert score_body["is_clean"] is True

    _as("dave")
    decide_resp = await client.post(
        f"/opboh/assessments/{assessment_id}/decide", json={"decision": "accepted"}
    )
    assert decide_resp.status_code == 200, decide_resp.text
    assert decide_resp.json()["status"] == "accepted"
    assert decide_resp.json()["approved_by"] == "dave"


async def test_critical_failure_blocks_accept_over_http(
    client: AsyncClient,
    organisation: Organisation,
    catalogue: tuple[OpbohFrameworkVersion, OpbohQuestion, OpbohQuestion],
) -> None:
    _version, critical_q, ordinary_q = catalogue

    _as("alice")
    create_resp = await client.post(
        "/opboh/assessments", json={"organisation_id": str(organisation.id)}
    )
    assessment_id = create_resp.json()["id"]

    # The critical control fails; the ordinary one is fine — the point is
    # that a decent-looking ordinary answer does not rescue this.
    await client.post(
        f"/opboh/assessments/{assessment_id}/responses",
        json={"question_id": str(critical_q.id), "score": 0.0, "evidence_sufficient": True},
    )
    await client.post(
        f"/opboh/assessments/{assessment_id}/responses",
        json={"question_id": str(ordinary_q.id), "score": 1.0, "evidence_sufficient": True},
    )
    await client.post(f"/opboh/assessments/{assessment_id}/submit")

    _as("bob")
    await client.post(f"/opboh/assessments/{assessment_id}/begin-assessment")
    _as("carol")
    await client.post(f"/opboh/assessments/{assessment_id}/independently-review")

    _as("dave")
    reject_accept = await client.post(
        f"/opboh/assessments/{assessment_id}/decide", json={"decision": "accepted"}
    )
    assert reject_accept.status_code == 409  # FW-OPBOH-015, over the wire this time

    conditional = await client.post(
        f"/opboh/assessments/{assessment_id}/decide",
        json={
            "decision": "conditionally_accepted",
            "decision_summary": "Pending updated registration.",
        },
    )
    assert conditional.status_code == 200
    assert conditional.json()["status"] == "conditionally_accepted"
    assert conditional.json()["has_critical_failure"] is True


async def test_same_person_cannot_assess_their_own_preparation_over_http(
    client: AsyncClient,
    organisation: Organisation,
    catalogue: tuple[OpbohFrameworkVersion, OpbohQuestion, OpbohQuestion],
) -> None:
    _as("alice")
    create_resp = await client.post(
        "/opboh/assessments", json={"organisation_id": str(organisation.id)}
    )
    assessment_id = create_resp.json()["id"]
    await client.post(f"/opboh/assessments/{assessment_id}/submit")

    begin_resp = await client.post(f"/opboh/assessments/{assessment_id}/begin-assessment")
    assert begin_resp.status_code == 403
    assert "SOD-001/002" in begin_resp.json()["detail"]


async def test_creating_an_assessment_for_an_unknown_organisation_is_404(
    client: AsyncClient,
) -> None:
    _as("alice")
    resp = await client.post("/opboh/assessments", json={"organisation_id": str(uuid.uuid4())})
    assert resp.status_code == 404


async def _make_project(db_session: AsyncSession, organisation: Organisation) -> Project:
    stage = Stage(
        id=uuid.uuid4(),
        code=f"stg-{uuid.uuid4().hex[:8]}",
        name="Stage",
        sequence=uuid.uuid4().int % 1_000_000,
        is_active=True,
        created_by="seed",
        updated_by="seed",
    )
    db_session.add(stage)
    await db_session.flush()
    project = Project(
        id=uuid.uuid4(),
        tenant_id=organisation.tenant_id,
        organisation_id=organisation.id,
        name="Test Project",
        current_stage_id=stage.id,
        status=ProjectStatus.ACTIVE,
        created_by="seed",
        updated_by="seed",
    )
    db_session.add(project)
    await db_session.commit()
    return project


async def test_creating_an_assessment_links_the_given_project(
    client: AsyncClient, organisation: Organisation, db_session: AsyncSession
) -> None:
    project = await _make_project(db_session, organisation)

    _as("alice")
    resp = await client.post(
        "/opboh/assessments",
        json={"organisation_id": str(organisation.id), "project_id": str(project.id)},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["project_id"] == str(project.id)


async def test_creating_an_assessment_for_a_project_in_a_different_organisation_is_409(
    client: AsyncClient, organisation: Organisation, db_session: AsyncSession
) -> None:
    other_org = Organisation(
        id=uuid.uuid4(),
        tenant_id=organisation.tenant_id,
        legal_name="Other Org Ltd",
        created_by="seed",
        updated_by="seed",
    )
    db_session.add(other_org)
    await db_session.commit()
    project = await _make_project(db_session, other_org)

    _as("alice")
    resp = await client.post(
        "/opboh/assessments",
        json={"organisation_id": str(organisation.id), "project_id": str(project.id)},
    )
    assert resp.status_code == 409
