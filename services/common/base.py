from abc import ABC
from fastapi import FastAPI
from pydantic_settings import BaseSettings, SettingsConfigDict


class ServiceSettings(BaseSettings):
    """Common settings for all services."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )
    host: str = "127.0.0.1"
    port: int


class BaseService(ABC):
    """An abstract base class for all microservices."""

    def __init__(self, service_name: str, settings: ServiceSettings):
        self.service_name = service_name
        self.settings = settings
        self.app = FastAPI(
            title=self.service_name,
            description=f"{self.service_name} for the YTArchive project.",
            version="0.1.0",
        )
        self._configure_routes()

    def _configure_routes(self):
        """Configure the API routes for the service."""

        @self.app.get("/health", tags=["Monitoring"])
        async def health_check():
            """Health check endpoint to verify service is running."""
            return {"status": "ok", "service": self.service_name}

    def run(self):
        """Run the service using uvicorn."""
        import uvicorn

        config = uvicorn.Config(
            self.app, host=self.settings.host, port=self.settings.port, log_level="info"
        )
        server = uvicorn.Server(config)

        # TODO: Add graceful shutdown logic here

        server.run()
