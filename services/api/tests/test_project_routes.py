"""HTTP-level Stage Engine tests. Route handlers actually `commit()`
(unlike test_stage_engine.py's service-level tests, which only `flush()`
via `db_session`), so committed rows outlive the test that made them
within the same test *session* — see test_framework_routes.py's docstring
for the CI failure that first surfaced this. Sharper here: `Stage.sequence`
is global, unscoped ordering, so two tests' stages could numerically
interleave and let one test's project silently "advance" into a
different test's stage — not just collide on a unique column. Every
stage sequence below gets its own widely-separated random base for
exactly that reason, not just a random code."""

import uuid
from collections.abc import AsyncGenerator
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from ipacgs.core.security import CurrentUser, get_current_user
from ipacgs.main import app
from ipacgs.models.framework import Framework
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
        # This is what actually broke test_stage_engine.py: spacing this
        # fixture's own sequence range apart from other tests protects
        # advance_stage's *relative* "next stage after X" query, but
        # create_project's "the globally lowest active stage" has no
        # reference point to space against — a committed row from any
        # earlier test with a lower sequence wins regardless. Committing
        # is unavoidable here (route handlers use a separate session than
        # this fixture's db_session, so the client can't see this data
        # otherwise) — deactivating on the way out is what keeps it from
        # outliving this test in a schema that's only ever torn down once,
        # at the end of the whole session (see conftest.py's `_schema`).
        stage_a.is_active = False
        stage_b.is_active = False
        await db_session.commit()


async def _accepted_assessment(db_session: AsyncSession, org: Organisation) -> OpbohAssessment:
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
        status=OpbohAssessmentStatus.ACCEPTED,
        prepared_by="alice",
        has_critical_failure=False,
        created_by="alice",
        updated_by="alice",
    )
    db_session.add(assessment)
    await db_session.commit()
    return assessment


async def test_create_and_fetch_a_project(
    client: AsyncClient, organisation: Organisation, two_stages: tuple[Stage, Stage]
) -> None:
    stage_a, _stage_b = two_stages
    _as("alice")
    create_resp = await client.post(
        "/projects", json={"organisation_id": str(organisation.id), "name": "Test Project"}
    )
    assert create_resp.status_code == 201, create_resp.text
    body = create_resp.json()
    assert body["current_stage_id"] == str(stage_a.id)
    assert body["status"] == "active"

    get_resp = await client.get(f"/projects/{body['id']}")
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "Test Project"


async def test_creating_a_project_for_an_unknown_organisation_is_404(client: AsyncClient) -> None:
    _as("alice")
    resp = await client.post(
        "/projects", json={"organisation_id": str(uuid.uuid4()), "name": "Test Project"}
    )
    assert resp.status_code == 404


async def test_advance_stage_moves_the_project_and_records_the_decision(
    client: AsyncClient,
    organisation: Organisation,
    two_stages: tuple[Stage, Stage],
    db_session: AsyncSession,
) -> None:
    stage_a, stage_b = two_stages
    assessment = await _accepted_assessment(db_session, organisation)

    _as("alice")
    create_resp = await client.post(
        "/projects", json={"organisation_id": str(organisation.id), "name": "Test Project"}
    )
    project_id = create_resp.json()["id"]

    advance_resp = await client.post(
        f"/projects/{project_id}/advance-stage",
        json={"supporting_assessment_id": str(assessment.id), "notes": "Sponsor confirmed."},
    )
    assert advance_resp.status_code == 200, advance_resp.text
    decision = advance_resp.json()
    assert decision["from_stage_id"] == str(stage_a.id)
    assert decision["to_stage_id"] == str(stage_b.id)
    assert decision["decided_by"] == "alice"

    project_resp = await client.get(f"/projects/{project_id}")
    assert project_resp.json()["current_stage_id"] == str(stage_b.id)

    history_resp = await client.get(f"/projects/{project_id}/stage-history")
    assert history_resp.status_code == 200
    assert len(history_resp.json()) == 1
    assert history_resp.json()[0]["supporting_assessment_id"] == str(assessment.id)


async def test_advance_stage_rejects_an_unaccepted_assessment(
    client: AsyncClient,
    organisation: Organisation,
    two_stages: tuple[Stage, Stage],
    db_session: AsyncSession,
) -> None:
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
    draft_assessment = OpbohAssessment(
        id=uuid.uuid4(),
        tenant_id=organisation.tenant_id,
        framework_version_id=version.id,
        organisation_id=organisation.id,
        status=OpbohAssessmentStatus.DRAFT,
        prepared_by="alice",
        has_critical_failure=False,
        created_by="alice",
        updated_by="alice",
    )
    db_session.add(draft_assessment)
    await db_session.commit()

    _as("alice")
    create_resp = await client.post(
        "/projects", json={"organisation_id": str(organisation.id), "name": "Test Project"}
    )
    project_id = create_resp.json()["id"]

    advance_resp = await client.post(
        f"/projects/{project_id}/advance-stage",
        json={"supporting_assessment_id": str(draft_assessment.id)},
    )
    assert advance_resp.status_code == 409


async def test_advance_stage_for_an_unknown_assessment_is_404(
    client: AsyncClient, organisation: Organisation, two_stages: tuple[Stage, Stage]
) -> None:
    _as("alice")
    create_resp = await client.post(
        "/projects", json={"organisation_id": str(organisation.id), "name": "Test Project"}
    )
    project_id = create_resp.json()["id"]

    resp = await client.post(
        f"/projects/{project_id}/advance-stage",
        json={"supporting_assessment_id": str(uuid.uuid4())},
    )
    assert resp.status_code == 404


async def test_advance_stage_for_an_unknown_project_is_404(client: AsyncClient) -> None:
    _as("alice")
    resp = await client.post(
        f"/projects/{uuid.uuid4()}/advance-stage",
        json={"supporting_assessment_id": str(uuid.uuid4())},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# reopen-stage, assign, rag, open-findings, applicable-frameworks —
# Epic 4/5 gap-closing
# ---------------------------------------------------------------------------


async def test_reopen_stage_moves_back_and_clears_the_assignment(
    client: AsyncClient,
    organisation: Organisation,
    two_stages: tuple[Stage, Stage],
    db_session: AsyncSession,
) -> None:
    stage_a, stage_b = two_stages
    assessment = await _accepted_assessment(db_session, organisation)

    _as("alice")
    create_resp = await client.post(
        "/projects", json={"organisation_id": str(organisation.id), "name": "Test Project"}
    )
    project_id = create_resp.json()["id"]
    await client.post(
        f"/projects/{project_id}/advance-stage",
        json={"supporting_assessment_id": str(assessment.id)},
    )
    await client.post(
        f"/projects/{project_id}/assign", json={"assigned_to": "carol", "due_date": "2026-12-01"}
    )

    reopen_resp = await client.post(
        f"/projects/{project_id}/reopen-stage",
        json={"target_stage_id": str(stage_a.id), "reason": "Registration lapsed."},
    )
    assert reopen_resp.status_code == 200, reopen_resp.text
    decision = reopen_resp.json()
    assert decision["kind"] == "reopen"
    assert decision["from_stage_id"] == str(stage_b.id)
    assert decision["to_stage_id"] == str(stage_a.id)
    assert decision["supporting_assessment_id"] is None

    project_resp = await client.get(f"/projects/{project_id}")
    body = project_resp.json()
    assert body["current_stage_id"] == str(stage_a.id)
    assert body["assigned_to"] is None
    assert body["stage_due_date"] is None


async def test_reopen_stage_without_a_reason_is_rejected(
    client: AsyncClient, organisation: Organisation, two_stages: tuple[Stage, Stage]
) -> None:
    stage_a, _stage_b = two_stages
    _as("alice")
    create_resp = await client.post(
        "/projects", json={"organisation_id": str(organisation.id), "name": "Test Project"}
    )
    project_id = create_resp.json()["id"]

    resp = await client.post(
        f"/projects/{project_id}/reopen-stage",
        json={"target_stage_id": str(stage_a.id), "reason": "   "},
    )
    assert resp.status_code == 409


async def test_assign_stage_sets_owner_and_due_date(
    client: AsyncClient, organisation: Organisation, two_stages: tuple[Stage, Stage]
) -> None:
    _as("alice")
    create_resp = await client.post(
        "/projects", json={"organisation_id": str(organisation.id), "name": "Test Project"}
    )
    project_id = create_resp.json()["id"]

    resp = await client.post(
        f"/projects/{project_id}/assign", json={"assigned_to": "dave", "due_date": "2026-09-15"}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["assigned_to"] == "dave"
    assert resp.json()["stage_due_date"] == "2026-09-15"


async def test_rag_endpoint_is_grey_before_any_assessment(
    client: AsyncClient, organisation: Organisation, two_stages: tuple[Stage, Stage]
) -> None:
    _as("alice")
    create_resp = await client.post(
        "/projects", json={"organisation_id": str(organisation.id), "name": "Test Project"}
    )
    project_id = create_resp.json()["id"]

    resp = await client.get(f"/projects/{project_id}/rag")
    assert resp.status_code == 200
    assert resp.json()["status"] == "grey"


async def test_open_findings_endpoint_returns_empty_list_with_no_findings(
    client: AsyncClient, organisation: Organisation, two_stages: tuple[Stage, Stage]
) -> None:
    _as("alice")
    create_resp = await client.post(
        "/projects", json={"organisation_id": str(organisation.id), "name": "Test Project"}
    )
    project_id = create_resp.json()["id"]

    resp = await client.get(f"/projects/{project_id}/open-findings")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_applicable_frameworks_includes_a_rule_free_active_framework(
    client: AsyncClient,
    organisation: Organisation,
    two_stages: tuple[Stage, Stage],
    db_session: AsyncSession,
) -> None:
    """Framework.code is globally unique and this test commits one for
    real (same reason two_stages does) — randomized, same lesson as
    everywhere else in this file."""
    framework = Framework(
        id=uuid.uuid4(),
        code=_unique("fw"),
        name="Test Framework",
        is_active=True,
        created_by="seed",
        updated_by="seed",
    )
    db_session.add(framework)
    await db_session.commit()

    _as("alice")
    create_resp = await client.post(
        "/projects",
        json={
            "organisation_id": str(organisation.id),
            "name": "Test Project",
            "sector": "infrastructure",
        },
    )
    project_id = create_resp.json()["id"]

    resp = await client.get(f"/projects/{project_id}/applicable-frameworks")
    assert resp.status_code == 200
    assert str(framework.id) in {f["id"] for f in resp.json()}
