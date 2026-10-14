"""CLI and Local Runner Entrypoint."""

import uvicorn
from src.orchestrator.config import settings
from src.orchestrator.core.logging import logger


def main():
    """Runs the FastAPI application using uvicorn."""
    logger.info(f"Starting server on {settings.APP_HOST}:{settings.APP_PORT}...")
    uvicorn.run(
        "src.orchestrator.api.app:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=True if settings.ENVIRONMENT == "development" else False,
    )


if __name__ == "__main__":
    main()
