"""Test fixtures. Expects DATABASE_URL to point at a real (test) Postgres —
CI provides one as a service container; locally, point it at a throwaway
local Postgres, or run `docker run -p 5432:5432 -e POSTGRES_PASSWORD=test postgres:16`.

Deliberately not using SQLite-in-memory here: this schema uses Postgres-only
types (UUID, JSONB, native enums) that SQLite can't represent, and a test
suite that passes against a database the app doesn't actually run on isn't
worth much.
"""

import asyncio
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from ipacgs.core.db import async_session_factory, engine
from ipacgs.main import app
from ipacgs.models import Base


@pytest.fixture(scope="session", autouse=True)
def _event_loop_policy():
    # pytest-asyncio in auto mode needs a session-scoped loop for the
    # session-scoped schema fixture below.
    policy = asyncio.get_event_loop_policy()
    yield policy


@pytest.fixture(scope="session")
async def _schema() -> AsyncGenerator[None, None]:
    """NOT autouse — only tests that actually request `db_session` or
    `client` pay the cost of a real Postgres connection. Pure-logic tests
    like test_security.py's maker-checker tests must be able to run with no
    database reachable at all; a suite where every test secretly requires
    infrastructure it doesn't use isn't one people run locally before pushing."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db_session(_schema: None) -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session


@pytest.fixture
async def client(_schema: None) -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
