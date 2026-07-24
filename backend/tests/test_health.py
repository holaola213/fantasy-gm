import pytest
from httpx import ASGITransport, AsyncClient

from app.health.router import get_database_health_check
from app.main import app


@pytest.mark.asyncio
async def test_health_returns_ok_when_database_check_succeeds() -> None:
    async def successful_check() -> None:
        return None

    app.dependency_overrides[get_database_health_check] = lambda: successful_check

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "connected"}


@pytest.mark.asyncio
async def test_health_returns_safe_503_when_database_check_fails() -> None:
    async def failing_check() -> None:
        raise RuntimeError("postgresql+asyncpg://user:secret@db:5432/fantasy_gm")

    app.dependency_overrides[get_database_health_check] = lambda: failing_check

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {"detail": "database unavailable"}
