"""HTTP-level Framework Registry tests — mirrors test_opboh_routes.py's
`_as()` dependency-override pattern for exercising authenticated routes
without a real Entra ID token.

Every `code` used below is randomized per test, not a fixed literal like
"ESG" — `Framework.code` is unique, and unlike the service-level tests in
test_framework_registry.py (which only `flush()` via `db_session` and get
rolled back for free), routes actually `commit()`. That commit outlives
the test that made it: `_schema` creates the schema once per test
*session*, not once per test, so a fixed code collides with whatever
earlier test in the same run already registered it — CI caught exactly
this the first time this file used "ESG" everywhere. Same defense
test_opboh_routes.py's `catalogue` fixture already uses for
`version_label`, for the same reason.
"""

import uuid
from collections.abc import AsyncGenerator

import pytest
from httpx import AsyncClient

from ipacgs.core.security import CurrentUser, get_current_user
from ipacgs.main import app


def _as(object_id: str) -> None:
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        object_id=object_id, display_name=object_id, roles=(), raw_claims={}
    )


def _unique_code(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


@pytest.fixture(autouse=True)
async def _clear_overrides() -> AsyncGenerator[None, None]:
    yield
    app.dependency_overrides.clear()


async def test_register_list_and_fetch_a_framework(client: AsyncClient) -> None:
    code = _unique_code("esg")
    _as("alice")
    create_resp = await client.post(
        "/frameworks", json={"code": code, "name": "Environmental & Social Governance"}
    )
    assert create_resp.status_code == 201, create_resp.text
    framework_id = create_resp.json()["id"]
    assert create_resp.json()["is_active"] is True

    list_resp = await client.get("/frameworks")
    assert list_resp.status_code == 200
    assert any(f["id"] == framework_id for f in list_resp.json())

    get_resp = await client.get(f"/frameworks/{framework_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["code"] == code


async def test_registering_a_duplicate_code_is_409(client: AsyncClient) -> None:
    code = _unique_code("esg")
    _as("alice")
    first_resp = await client.post("/frameworks", json={"code": code, "name": "First"})
    assert first_resp.status_code == 201, first_resp.text

    dup_resp = await client.post("/frameworks", json={"code": code, "name": "Second"})
    assert dup_resp.status_code == 409


async def test_fetching_an_unknown_framework_is_404(client: AsyncClient) -> None:
    _as("alice")
    resp = await client.get("/frameworks/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


async def test_version_lifecycle_create_then_activate(client: AsyncClient) -> None:
    _as("alice")
    framework_resp = await client.post(
        "/frameworks",
        json={"code": _unique_code("esg"), "name": "Environmental & Social Governance"},
    )
    assert framework_resp.status_code == 201, framework_resp.text
    framework_id = framework_resp.json()["id"]

    v1_resp = await client.post(
        f"/frameworks/{framework_id}/versions",
        json={"version_label": "1.0", "effective_from": "2026-01-01"},
    )
    assert v1_resp.status_code == 201, v1_resp.text
    assert v1_resp.json()["is_active"] is False
    v1_id = v1_resp.json()["id"]

    v2_resp = await client.post(
        f"/frameworks/{framework_id}/versions",
        json={"version_label": "2.0", "effective_from": "2026-06-01"},
    )
    v2_id = v2_resp.json()["id"]

    activate_v1 = await client.post(f"/frameworks/{framework_id}/versions/{v1_id}/activate")
    assert activate_v1.status_code == 200
    assert activate_v1.json()["is_active"] is True

    versions_resp = await client.get(f"/frameworks/{framework_id}/versions")
    by_id = {v["id"]: v for v in versions_resp.json()}
    assert by_id[v1_id]["is_active"] is True
    assert by_id[v2_id]["is_active"] is False

    activate_v2 = await client.post(f"/frameworks/{framework_id}/versions/{v2_id}/activate")
    assert activate_v2.status_code == 200

    versions_after = await client.get(f"/frameworks/{framework_id}/versions")
    by_id_after = {v["id"]: v for v in versions_after.json()}
    assert by_id_after[v1_id]["is_active"] is False
    assert by_id_after[v2_id]["is_active"] is True


async def test_creating_a_version_for_an_unknown_framework_is_404(client: AsyncClient) -> None:
    _as("alice")
    resp = await client.post(
        "/frameworks/00000000-0000-0000-0000-000000000000/versions",
        json={"version_label": "1.0", "effective_from": "2026-01-01"},
    )
    assert resp.status_code == 404


async def test_activating_a_version_under_the_wrong_framework_is_404(client: AsyncClient) -> None:
    """A version genuinely exists, just not under the framework_id in the
    URL — must 404, not silently activate it anyway."""
    _as("alice")
    esg_resp = await client.post("/frameworks", json={"code": _unique_code("esg"), "name": "ESG"})
    fin_resp = await client.post(
        "/frameworks", json={"code": _unique_code("fin-gov"), "name": "Financial Gov"}
    )
    assert esg_resp.status_code == 201, esg_resp.text
    assert fin_resp.status_code == 201, fin_resp.text
    esg_id = esg_resp.json()["id"]
    fin_id = fin_resp.json()["id"]

    version_resp = await client.post(
        f"/frameworks/{esg_id}/versions",
        json={"version_label": "1.0", "effective_from": "2026-01-01"},
    )
    version_id = version_resp.json()["id"]

    wrong_activate = await client.post(f"/frameworks/{fin_id}/versions/{version_id}/activate")
    assert wrong_activate.status_code == 404
