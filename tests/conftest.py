import pytest
import pytest_asyncio
from httpx import AsyncClient

from services.common.base import BaseService, ServiceSettings


class MockService(BaseService):
    """A mock service for testing the base class."""

    def run(self):
        pass  # Not needed for testing


@pytest.fixture
def mock_settings() -> ServiceSettings:
    """Returns a mock ServiceSettings instance for testing."""
    return ServiceSettings(port=8001)  # Use a different port for testing


@pytest.fixture
def mock_service(mock_settings: ServiceSettings) -> MockService:
    """Returns a mock service instance for testing."""
    return MockService(service_name="MockService", settings=mock_settings)


@pytest_asyncio.fixture
async def test_client(mock_service: MockService):
    """Returns an httpx test client for the mock service."""
    async with AsyncClient(app=mock_service.app, base_url="http://test") as client:
        yield client
