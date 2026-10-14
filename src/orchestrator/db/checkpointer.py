"""LangGraph PostgreSQL Checkpointer initialization."""

from contextlib import contextmanager
from typing import Any, Generator
from src.orchestrator.config import settings
from src.orchestrator.core.logging import logger

try:
    from langgraph.checkpoint.postgres import PostgresSaver
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    POSTGRES_CHECKPOINTER_AVAILABLE = True
except ImportError:
    POSTGRES_CHECKPOINTER_AVAILABLE = False
    logger.warning("langgraph-checkpoint-postgres not found. In-memory checkpointer will be used as fallback.")

from langgraph.checkpoint.memory import MemorySaver


@contextmanager
def get_checkpointer() -> Generator[Any, None, None]:
    """
    Yields an active LangGraph PostgresSaver checkpointer.
    Falls back to MemorySaver if postgres checkpointer library is unavailable or in mock mode.
    """
    if POSTGRES_CHECKPOINTER_AVAILABLE:
        try:
            logger.debug("Connecting PostgresSaver to database...")
            # Note: with PostgresSaver.from_conn_string, connection is managed via context manager
            with PostgresSaver.from_conn_string(settings.DATABASE_URL) as checkpointer:
                # In Flyway managed setup, DDL is pre-applied.
                # checkpointer.setup() can be called safely or skipped if Flyway manages all DDL.
                yield checkpointer
        except Exception as e:
            logger.error(f"Error connecting to Postgres checkpointer: {e}. Falling back to MemorySaver.")
            yield MemorySaver()
    else:
        yield MemorySaver()


def get_memory_checkpointer() -> MemorySaver:
    """Returns an in-memory checkpointer for testing and development."""
    return MemorySaver()
