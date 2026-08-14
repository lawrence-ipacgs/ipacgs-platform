"""ASGI entry point. `uvicorn ipacgs.main:app`."""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from ipacgs.api.routes import evidence, framework, health, opboh
from ipacgs.core.config import get_settings
from ipacgs.core.security import MakerCheckerViolation
from ipacgs.services.evidence import IllegalEvidenceTransition
from ipacgs.services.framework_registry import DuplicateFrameworkCode
from ipacgs.services.opboh_workflow import IllegalTransition

settings = get_settings()
logging.basicConfig(level=settings.log_level)

app = FastAPI(
    title="IPAC Governance Systems API",
    description="Milestone 1.1 — Platform Foundation, Epic 3 (OPBOH) and Epic 4 (Framework "
    "Registry). See the architecture document's Section 4 for what this service does and "
    "doesn't do yet.",
    version="0.3.0",
)

app.include_router(health.router)
app.include_router(opboh.router)
app.include_router(evidence.router)
app.include_router(framework.router)


# Domain exceptions get their own status codes here, once, rather than
# every route re-wrapping a try/except around the same two cases. The
# distinction matters: a MakerCheckerViolation means "you specifically
# can't do this" (403) — the action would be legal for someone else. An
# IllegalTransition/IllegalEvidenceTransition means "this can't happen from
# here at all" (409) — a conflict with the resource's current state,
# regardless of who's asking.
@app.exception_handler(MakerCheckerViolation)
async def maker_checker_handler(_: Request, exc: MakerCheckerViolation) -> JSONResponse:
    return JSONResponse(status_code=403, content={"detail": str(exc)})


@app.exception_handler(IllegalTransition)
async def illegal_transition_handler(_: Request, exc: IllegalTransition) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(IllegalEvidenceTransition)
async def illegal_evidence_transition_handler(
    _: Request, exc: IllegalEvidenceTransition
) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(DuplicateFrameworkCode)
async def duplicate_framework_code_handler(_: Request, exc: DuplicateFrameworkCode) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})
