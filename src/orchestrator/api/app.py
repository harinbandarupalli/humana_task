"""FastAPI Application entrypoint with lifecycle management."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.orchestrator.api.routes.health import router as health_router
from src.orchestrator.api.routes.workflows import router as workflows_router
from src.orchestrator.config import settings
from src.orchestrator.core.logging import logger
from src.orchestrator.db.session import close_connection_pool, get_connection_pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manages application startup and shutdown lifecycle hooks."""
    logger.info("Initializing LangGraph Orchestrator services...")
    try:
        get_connection_pool()
        logger.info("Database pool established successfully.")
    except Exception as e:
        logger.warning(f"Could not connect to database on startup: {e}. Check PostgreSQL configuration.")

    yield

    logger.info("Shutting down LangGraph Orchestrator services...")
    close_connection_pool()


def create_app() -> FastAPI:
    """Builds and configures the FastAPI application."""
    app = FastAPI(
        title=settings.APP_NAME,
        version="0.1.0",
        description="LangGraph Orchestrator with PostgreSQL state persistence and Flyway migrations.",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(workflows_router)

    return app


app = create_app()
