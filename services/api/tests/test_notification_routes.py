"""HTTP-level notification + tracker-view tests. GET /projects is
unscoped across every test's committed projects (same convention as
GET /frameworks, GET /gates) — assertions check membership, not exact
counts or list contents, same defensive pattern already established for
those routes."""

import uuid
from collections.abc import AsyncGenerator
from datetime import date, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from ipacgs.core.security import CurrentUser, get_current_user
from ipacgs.main import app
from ipacgs.models.notification import NotificationKind
from ipacgs.models.opboh import (
    FindingSeverity,
    FindingStatus,
    OpbohAssessment,
    OpbohAssessmentStatus,
    OpbohFinding,
    OpbohFrameworkVersion,
)
from ipacgs.models.organisation import Organisation
from ipacgs.models.project import Project, ProjectStatus, Stage
from ipacgs.models.tenant import Tenant
from ipacgs.services.notifications import notify


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
async def one_stage(db_session: AsyncSession) -> AsyncGenerator[Stage, None]:
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
    await db_session.commit()
    try:
        yield stage
    finally:
        stage.is_active = False
        await db_session.commit()


async def test_my_notifications_only_returns_my_own(
    client: AsyncClient, organisation: Organisation, db_session: AsyncSession
) -> None:
    await notify(
        db_session,
        tenant_id=organisation.tenant_id,
        recipient="alice",
        kind=NotificationKind.ASSIGNMENT,
        entity_type="project",
        entity_id=uuid.uuid4(),
        message="For alice only.",
    )
    await db_session.commit()

    _as("alice")
    resp = await client.get("/me/notifications")
    assert resp.status_code == 200
    assert all(n["recipient"] == "alice" for n in resp.json())
    assert any(n["message"] == "For alice only." for n in resp.json())

    _as("bob")
    bob_resp = await client.get("/me/notifications")
    assert bob_resp.status_code == 200
    assert not any(n["message"] == "For alice only." for n in bob_resp.json())


async def test_mark_notification_read(
    client: AsyncClient, organisation: Organisation, db_session: AsyncSession
) -> None:
    note = await notify(
        db_session,
        tenant_id=organisation.tenant_id,
        recipient="alice",
        kind=NotificationKind.ASSIGNMENT,
        entity_type="project",
        entity_id=uuid.uuid4(),
        message="Mark me read.",
    )
    await db_session.commit()

    resp = await client.post(f"/notifications/{note.id}/read")
    assert resp.status_code == 200, resp.text
    assert resp.json()["is_read"] is True
    assert resp.json()["read_at"] is not None


async def test_mark_unknown_notification_read_is_404(client: AsyncClient) -> None:
    resp = await client.post(f"/notifications/{uuid.uuid4()}/read")
    assert resp.status_code == 404


async def test_scan_overdue_route_creates_notifications(
    client: AsyncClient, organisation: Organisation, one_stage: Stage, db_session: AsyncSession
) -> None:
    yesterday = date.today() - timedelta(days=1)
    project = Project(
        id=uuid.uuid4(),
        tenant_id=organisation.tenant_id,
        organisation_id=organisation.id,
        name="Overdue Project",
        current_stage_id=one_stage.id,
        status=ProjectStatus.ACTIVE,
        assigned_to="dave",
        stage_due_date=yesterday,
        created_by="seed",
        updated_by="seed",
    )
    db_session.add(project)
    await db_session.commit()

    resp = await client.post("/notifications/scan-overdue")
    assert resp.status_code == 200, resp.text
    assert any(n["recipient"] == "dave" for n in resp.json())


async def test_assigning_a_stage_sends_a_notification(
    client: AsyncClient, organisation: Organisation, one_stage: Stage
) -> None:
    _as("alice")
    create_resp = await client.post(
        "/projects", json={"organisation_id": str(organisation.id), "name": "Test Project"}
    )
    project_id = create_resp.json()["id"]

    assign_resp = await client.post(
        f"/projects/{project_id}/assign", json={"assigned_to": "erin", "due_date": "2026-12-01"}
    )
    assert assign_resp.status_code == 200, assign_resp.text

    _as("erin")
    notes_resp = await client.get("/me/notifications")
    assert any(
        n["kind"] == "assignment" and n["entity_id"] == project_id for n in notes_resp.json()
    )


async def test_assigning_a_finding_sends_a_notification(
    client: AsyncClient, organisation: Organisation, db_session: AsyncSession
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
    assessment = OpbohAssessment(
        id=uuid.uuid4(),
        tenant_id=organisation.tenant_id,
        framework_version_id=version.id,
        organisation_id=organisation.id,
        status=OpbohAssessmentStatus.SUBMITTED,
        prepared_by="alice",
        has_critical_failure=False,
        created_by="alice",
        updated_by="alice",
    )
    db_session.add(assessment)
    await db_session.flush()
    finding = OpbohFinding(
        id=uuid.uuid4(),
        tenant_id=organisation.tenant_id,
        assessment_id=assessment.id,
        severity=FindingSeverity.MEDIUM,
        description="Needs follow-up.",
        status=FindingStatus.OPEN,
        created_by="alice",
        updated_by="alice",
    )
    db_session.add(finding)
    await db_session.commit()

    _as("alice")
    resp = await client.post(
        f"/opboh/findings/{finding.id}/assign",
        json={"owner": "frank", "due_date": "2026-11-01"},
    )
    assert resp.status_code == 200, resp.text

    _as("frank")
    notes_resp = await client.get("/me/notifications")
    assert any(
        n["kind"] == "assignment" and n["entity_id"] == str(finding.id) for n in notes_resp.json()
    )

    version.is_active = False
    await db_session.commit()


async def test_project_tracker_view_includes_my_project(
    client: AsyncClient, organisation: Organisation, one_stage: Stage
) -> None:
    _as("alice")
    create_resp = await client.post(
        "/projects", json={"organisation_id": str(organisation.id), "name": "Tracked Project"}
    )
    project_id = create_resp.json()["id"]

    resp = await client.get("/projects")
    assert resp.status_code == 200
    by_id = {p["id"]: p for p in resp.json()}
    assert project_id in by_id
    summary = by_id[project_id]
    assert summary["name"] == "Tracked Project"
    assert summary["current_stage_code"] == one_stage.code
    assert summary["rag_status"] == "grey"
    assert summary["blocking_gate_code"] is None
