"""Service-level notifications tests. Only flush()es via db_session
(never commit()) — same non-leaking pattern as test_stage_engine.py and
test_gate_engine.py."""

import uuid
from datetime import date, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from ipacgs.models.notification import NotificationKind
from ipacgs.models.opboh import (
    OpbohAssessment,
    OpbohAssessmentStatus,
    OpbohDomain,
    OpbohFrameworkVersion,
    OpbohQuestion,
)
from ipacgs.models.organisation import Organisation
from ipacgs.models.project import Project, ProjectStatus, Stage
from ipacgs.models.tenant import Tenant
from ipacgs.services.notifications import (
    list_for_recipient,
    mark_read,
    notify,
    scan_overdue_projects,
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


async def _make_stage(db_session: AsyncSession) -> Stage:
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
    return stage


async def _make_project(
    db_session: AsyncSession,
    org: Organisation,
    stage: Stage,
    *,
    assigned_to: str | None = None,
    stage_due_date: date | None = None,
) -> Project:
    project = Project(
        id=uuid.uuid4(),
        tenant_id=org.tenant_id,
        organisation_id=org.id,
        name="Test Project",
        current_stage_id=stage.id,
        status=ProjectStatus.ACTIVE,
        assigned_to=assigned_to,
        stage_due_date=stage_due_date,
        created_by="seed",
        updated_by="seed",
    )
    db_session.add(project)
    await db_session.flush()
    return project


async def test_notify_creates_an_unread_notification(db_session: AsyncSession) -> None:
    org = await _make_tenant_and_org(db_session)
    entity_id = uuid.uuid4()

    note = await notify(
        db_session,
        tenant_id=org.tenant_id,
        recipient="alice",
        kind=NotificationKind.ASSIGNMENT,
        entity_type="project",
        entity_id=entity_id,
        message="Test message.",
    )

    assert note.is_read is False
    assert note.read_at is None
    assert note.entity_id == entity_id


async def test_list_for_recipient_filters_by_recipient(db_session: AsyncSession) -> None:
    org = await _make_tenant_and_org(db_session)
    # Unique recipients, not literal "alice"/"bob": db_session tests never
    # commit here (only flush — rolled back at teardown), but other test
    # files' HTTP-level tests do commit real Notification rows against the
    # same session-scoped schema, and Notification has no is_active flag to
    # deactivate on the way out like Stage/Gate/OpbohFrameworkVersion do.
    alice, bob = _unique("alice"), _unique("bob")
    await notify(
        db_session,
        tenant_id=org.tenant_id,
        recipient=alice,
        kind=NotificationKind.ASSIGNMENT,
        entity_type="project",
        entity_id=uuid.uuid4(),
        message="For alice.",
    )
    await notify(
        db_session,
        tenant_id=org.tenant_id,
        recipient=bob,
        kind=NotificationKind.ASSIGNMENT,
        entity_type="project",
        entity_id=uuid.uuid4(),
        message="For bob.",
    )

    alice_notes = await list_for_recipient(db_session, alice)
    assert len(alice_notes) == 1
    assert alice_notes[0].message == "For alice."


async def test_list_for_recipient_unread_only(db_session: AsyncSession) -> None:
    org = await _make_tenant_and_org(db_session)
    alice = _unique("alice")
    note = await notify(
        db_session,
        tenant_id=org.tenant_id,
        recipient=alice,
        kind=NotificationKind.ASSIGNMENT,
        entity_type="project",
        entity_id=uuid.uuid4(),
        message="Read this.",
    )
    await mark_read(db_session, note)

    all_notes = await list_for_recipient(db_session, alice)
    unread_notes = await list_for_recipient(db_session, alice, unread_only=True)

    assert len(all_notes) == 1
    assert len(unread_notes) == 0


async def test_mark_read_sets_read_at(db_session: AsyncSession) -> None:
    org = await _make_tenant_and_org(db_session)
    note = await notify(
        db_session,
        tenant_id=org.tenant_id,
        recipient=_unique("alice"),
        kind=NotificationKind.ASSIGNMENT,
        entity_type="project",
        entity_id=uuid.uuid4(),
        message="Test.",
    )

    updated = await mark_read(db_session, note)

    assert updated.is_read is True
    assert updated.read_at is not None


async def test_scan_overdue_creates_a_due_date_notification(db_session: AsyncSession) -> None:
    org = await _make_tenant_and_org(db_session)
    stage = await _make_stage(db_session)
    yesterday = date.today() - timedelta(days=1)
    await _make_project(db_session, org, stage, assigned_to="carol", stage_due_date=yesterday)

    created = await scan_overdue_projects(db_session)

    kinds = {n.kind for n in created}
    assert NotificationKind.DUE_DATE in kinds
    assert all(n.recipient == "carol" for n in created)


async def test_scan_overdue_skips_projects_with_no_assignee(db_session: AsyncSession) -> None:
    org = await _make_tenant_and_org(db_session)
    stage = await _make_stage(db_session)
    yesterday = date.today() - timedelta(days=1)
    await _make_project(db_session, org, stage, assigned_to=None, stage_due_date=yesterday)

    created = await scan_overdue_projects(db_session)

    assert created == []


async def test_scan_overdue_skips_projects_not_yet_due(db_session: AsyncSession) -> None:
    org = await _make_tenant_and_org(db_session)
    stage = await _make_stage(db_session)
    tomorrow = date.today() + timedelta(days=1)
    await _make_project(db_session, org, stage, assigned_to="carol", stage_due_date=tomorrow)

    created = await scan_overdue_projects(db_session)

    assert created == []


async def test_scan_overdue_is_idempotent(db_session: AsyncSession) -> None:
    org = await _make_tenant_and_org(db_session)
    stage = await _make_stage(db_session)
    yesterday = date.today() - timedelta(days=1)
    await _make_project(db_session, org, stage, assigned_to="carol", stage_due_date=yesterday)

    first_scan = await scan_overdue_projects(db_session)
    second_scan = await scan_overdue_projects(db_session)

    assert len(first_scan) > 0
    assert second_scan == []


async def test_scan_overdue_escalates_a_critical_failure(db_session: AsyncSession) -> None:
    org = await _make_tenant_and_org(db_session)
    stage = await _make_stage(db_session)
    yesterday = date.today() - timedelta(days=1)
    project = await _make_project(
        db_session, org, stage, assigned_to="carol", stage_due_date=yesterday
    )

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
        status=OpbohAssessmentStatus.CONDITIONALLY_ACCEPTED,
        prepared_by="alice",
        has_critical_failure=True,
        created_by="alice",
        updated_by="alice",
    )
    db_session.add(assessment)
    await db_session.flush()

    domain = OpbohDomain(
        id=uuid.uuid4(),
        framework_version_id=version.id,
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

    created = await scan_overdue_projects(db_session)

    kinds = {n.kind for n in created}
    assert NotificationKind.DUE_DATE in kinds
    assert NotificationKind.ESCALATION in kinds
