import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(test_client: AsyncClient):
    """Test that the health check endpoint returns a 200 OK response."""
    response = await test_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "MockService"}
