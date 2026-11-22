import pytest
from httpx import ASGITransport, AsyncClient

from medication_reminder.main import create_app
from medication_reminder.shared.config import Settings


@pytest.mark.asyncio
async def test_health_returns_service_status() -> None:
    app = create_app(
        Settings(
            app_name="Test Reminder",
            environment="test",
        )
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "Test Reminder",
        "environment": "test",
    }
