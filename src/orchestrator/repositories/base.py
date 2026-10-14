"""Base repository with connection lifecycle management."""

from contextlib import contextmanager
from typing import Generator, Optional
import psycopg
from src.orchestrator.db.session import get_db_connection


class BaseRepository:
    """Base repository providing transparent connection pool access and transaction propagation."""

    def __init__(self, conn: Optional[psycopg.Connection] = None):
        self._external_conn = conn

    @contextmanager
    def get_connection(self) -> Generator[psycopg.Connection, None, None]:
        """
        Yields active database connection.
        Reuses external connection if injected, otherwise checks out a connection from the pool.
        """
        if self._external_conn is not None:
            yield self._external_conn
        else:
            with get_db_connection() as conn:
                yield conn
