"""Liveness/readiness — no auth required, deliberately. Container Apps'
ingress probes this; it must never depend on a valid Entra ID token."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ipacgs.core.db import get_db

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def liveness() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
async def readiness(db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    """Confirms the API can actually reach Postgres, not just that the
    process is running — the distinction that matters to a load balancer
    deciding whether to route traffic here."""
    await db.execute(text("SELECT 1"))
    return {"status": "ready"}
