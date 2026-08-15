"""Epic 7 — notifications service layer.

`notify` is the single entry point for creating a notification, same
"one place, not scattered across callers" pattern core/audit.py's
record_audit_event already established — nothing should construct a
Notification row directly.

`scan_overdue_projects` is a real gap worth stating plainly: WF-ESC-001…002
wants overdue critical items escalated, but this platform has no
scheduler (no Azure Container Apps Job, no timer trigger) to run that
scan on its own yet. It has to be called explicitly — via this module's
own function directly, or the `POST /notifications/scan-overdue` route —
until that infrastructure exists. Calling it twice for the same overdue
project is safe (idempotent: skips projects that already have an unread
notification of the relevant kind) but it will never run *by itself*.
"""

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ipacgs.models.notification import Notification, NotificationKind
from ipacgs.models.project import Project
from ipacgs.services.stage_engine import RagStatus, compute_project_rag


async def notify(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    recipient: str,
    kind: NotificationKind,
    entity_type: str,
    entity_id: uuid.UUID,
    message: str,
) -> Notification:
    notification = Notification(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        recipient=recipient,
        kind=kind,
        entity_type=entity_type,
        entity_id=entity_id,
        message=message,
    )
    session.add(notification)
    await session.flush()
    return notification


async def list_for_recipient(
    session: AsyncSession, recipient: str, *, unread_only: bool = False
) -> list[Notification]:
    stmt = select(Notification).where(Notification.recipient == recipient)
    if unread_only:
        stmt = stmt.where(Notification.is_read.is_(False))
    stmt = stmt.order_by(Notification.created_at.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def mark_read(session: AsyncSession, notification: Notification) -> Notification:
    notification.is_read = True
    notification.read_at = datetime.now(UTC)
    await session.flush()
    return notification


async def scan_overdue_projects(session: AsyncSession) -> list[Notification]:
    today = date.today()
    result = await session.execute(
        select(Project).where(
            Project.stage_due_date.is_not(None),
            Project.stage_due_date < today,
            Project.assigned_to.is_not(None),
        )
    )
    overdue_projects = result.scalars().all()

    created: list[Notification] = []
    for project in overdue_projects:
        assert project.assigned_to is not None  # filtered above
        due_date_note = await _notify_once(
            session,
            project=project,
            kind=NotificationKind.DUE_DATE,
            message=f"Project {project.name!r} is overdue on its current stage "
            f"(was due {project.stage_due_date}).",
        )
        if due_date_note is not None:
            created.append(due_date_note)

        # WF-ESC-001…002 — "overdue *critical* items" specifically, not
        # every overdue item: RED means the project's latest linked
        # assessment has an unresolved critical-control failure.
        rag = await compute_project_rag(session, project)
        if rag == RagStatus.RED:
            escalation_note = await _notify_once(
                session,
                project=project,
                kind=NotificationKind.ESCALATION,
                message=f"Project {project.name!r} is overdue AND has a critical-control "
                "failure — needs attention beyond the assigned owner.",
            )
            if escalation_note is not None:
                created.append(escalation_note)

    return created


async def _notify_once(
    session: AsyncSession, *, project: Project, kind: NotificationKind, message: str
) -> Notification | None:
    """Skips creating a duplicate if an unread notification of this kind
    already exists for this project — otherwise every scan would spam a
    fresh notification for the same still-overdue project."""
    assert project.assigned_to is not None
    existing = await session.execute(
        select(Notification).where(
            Notification.entity_type == "project",
            Notification.entity_id == project.id,
            Notification.kind == kind,
            Notification.is_read.is_(False),
        )
    )
    if existing.scalars().first() is not None:
        return None

    return await notify(
        session,
        tenant_id=project.tenant_id,
        recipient=project.assigned_to,
        kind=kind,
        entity_type="project",
        entity_id=project.id,
        message=message,
    )
