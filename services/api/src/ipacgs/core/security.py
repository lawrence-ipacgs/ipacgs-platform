"""Identity and access — FR-IAM-001…004.

Two distinct concerns live here on purpose:

1. *Authentication* — is this a valid Entra ID token for a real signed-in
   user? (`get_current_user`)
2. *Segregation of duties* — even a fully authenticated, fully authorised
   user must not be allowed to check their own work. (`enforce_maker_checker`)

The second one is the mechanism Section 5 of the architecture document flags
as a real staffing constraint (FW-OPBOH-006, SOD-001/002) — it's enforced
here, in application logic, not by Entra ID itself. Entra ID has no concept
of "this specific record's preparer."
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt
from jose.exceptions import JWTError

from ipacgs.core.config import get_settings

settings = get_settings()
bearer_scheme = HTTPBearer(auto_error=True)

_JWKS_CACHE: dict[str, Any] = {"keys": None, "fetched_at": 0.0}
_JWKS_TTL_SECONDS = 3600


@dataclass(frozen=True)
class CurrentUser:
    """The authenticated principal for this request. `roles` come straight
    off the token's app roles claim — see infra/scripts/create-app-registrations.sh
    for where those roles are defined."""

    object_id: str
    display_name: str
    roles: tuple[str, ...]
    raw_claims: dict[str, Any]


def _authority_urls() -> tuple[str, str]:
    tenant = settings.azure_tenant_id
    jwks_url = f"https://login.microsoftonline.com/{tenant}/discovery/v2.0/keys"
    issuer = f"https://login.microsoftonline.com/{tenant}/v2.0"
    return jwks_url, issuer


async def _get_jwks() -> list[dict[str, Any]]:
    now = time.monotonic()
    if _JWKS_CACHE["keys"] is not None and now - _JWKS_CACHE["fetched_at"] < _JWKS_TTL_SECONDS:
        return _JWKS_CACHE["keys"]

    jwks_url, _ = _authority_urls()
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(jwks_url)
        response.raise_for_status()
    keys = response.json()["keys"]
    _JWKS_CACHE["keys"] = keys
    _JWKS_CACHE["fetched_at"] = now
    return keys


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> CurrentUser:
    """Validate the bearer token against Entra ID and return the principal.

    Not wired into every route yet — Epic 0's job is to make this mechanism
    exist and be correct; individual routes opt in as they're built.
    """
    token = credentials.credentials
    _, issuer = _authority_urls()

    try:
        jwks = await _get_jwks()
        unverified_header = jwt.get_unverified_header(token)
        key = next((k for k in jwks if k["kid"] == unverified_header.get("kid")), None)
        if key is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token signed by an unrecognised key.",
            )
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=settings.entra_api_app_id,
            issuer=issuer,
        )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
        ) from exc

    return CurrentUser(
        object_id=claims["oid"],
        display_name=claims.get("name", claims.get("preferred_username", "unknown")),
        roles=tuple(claims.get("roles", [])),
        raw_claims=claims,
    )


def require_roles(*allowed_roles: str):
    """FastAPI dependency factory — `Depends(require_roles("AssuranceLead"))`.
    RBAC only; does not itself enforce maker-checker (see below)."""

    async def _check(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not set(user.roles) & set(allowed_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of: {', '.join(allowed_roles)}.",
            )
        return user

    return _check


class MakerCheckerViolation(Exception):
    """Raised when a reviewer/approver is the same person as the preparer."""


def enforce_maker_checker(preparer_object_id: str, reviewer: CurrentUser) -> None:
    """SOD-001/002 — a requester shall not be the sole approver of their own
    evidence, gate decision, or exception. Call this at the point a review,
    approval or gate decision is recorded, before it's persisted.

    This is deliberately a plain function, not a FastAPI dependency: which
    two identities are being compared depends on the specific record being
    acted on, which a route-level dependency can't know in advance.
    """
    if preparer_object_id == reviewer.object_id:
        raise MakerCheckerViolation(
            f"User {reviewer.object_id} prepared this record and cannot also "
            "review or approve it — see SOD-001/002."
        )
