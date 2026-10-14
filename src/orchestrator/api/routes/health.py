"""Healthcheck API endpoint."""

from fastapi import APIRouter
from src.orchestrator.db.session import get_db_connection

router = APIRouter(tags=["Health"])


@router.get("/health")
def healthcheck():
    """Verifies service readiness and PostgreSQL database connectivity."""
    db_status = "connected"
    try:
        with get_db_connection() as conn:
            conn.execute("SELECT 1;")
    except Exception as e:
        db_status = f"disconnected ({e})"

    return {
        "status": "ok",
        "database": db_status,
        "service": "langgraph-orchestrator",
    }
