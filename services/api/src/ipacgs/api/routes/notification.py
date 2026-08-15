"""Notification routes — Epic 7.

`GET /me/notifications` is FR-RPT-001's "personal work queue": scoped to
the authenticated caller's own identity, not a filterable recipient
parameter — without RBAC there's no way to tell whether the caller is
*allowed* to see someone else's queue, so the route just never offers
that choice.

`POST /notifications/scan-overdue` exists because there's no scheduler
in this platform to run it automatically (see services/notifications.py's
module docstring) — until one exists, this has to be triggered by
something external on a schedule.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ipacgs.api.schemas.notification import NotificationOut
from ipacgs.core.db import get_db
from ipacgs.core.security import CurrentUser, get_current_user
from ipacgs.models.notification import Notification
from ipacgs.services import notifications

router = APIRouter(tags=["notifications"])


@router.get("/me/notifications", response_model=list[NotificationOut])
async def my_notifications(
    unread_only: bool = False,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> list[Notification]:
    return await notifications.list_for_recipient(db, user.object_id, unread_only=unread_only)


@router.post("/notifications/{notification_id}/read", response_model=NotificationOut)
async def mark_notification_read(
    notification_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> Notification:
    notification = await db.get(Notification, notification_id)
    if notification is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No notification {notification_id}.")

    notification = await notifications.mark_read(db, notification)
    await db.commit()
    await db.refresh(notification)
    return notification


@router.post("/notifications/scan-overdue", response_model=list[NotificationOut])
async def scan_overdue(db: AsyncSession = Depends(get_db)) -> list[Notification]:
    created = await notifications.scan_overdue_projects(db)
    await db.commit()
    return created
