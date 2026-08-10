"""ASGI entry point. `uvicorn ipacgs.main:app`."""

import logging

from fastapi import FastAPI

from ipacgs.api.routes import health
from ipacgs.core.config import get_settings

settings = get_settings()
logging.basicConfig(level=settings.log_level)

app = FastAPI(
    title="IPAC Governance Systems API",
    description="Milestone 1.1 — Platform Foundation. See the architecture "
    "document's Section 4 (Epic 0) for what this service does and doesn't do yet.",
    version="0.1.0",
)

app.include_router(health.router)
