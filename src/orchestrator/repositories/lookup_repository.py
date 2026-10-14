"""Repository for static reference and code lookups."""

from typing import Dict, List, Optional
import psycopg
from src.orchestrator.entities.lookup import LookupCode
from src.orchestrator.repositories.base import BaseRepository

VALID_LOOKUP_TABLES = {
    "order_status_lookup",
    "payment_status_lookup",
    "workflow_stage_lookup",
    "stock_status_lookup",
    "deduction_status_lookup",
    "notification_status_lookup",
    "notification_type_lookup",
    "fulfillment_type_lookup",
}


class LookupRepository(BaseRepository):
    """Provides cached access and validation for reference code tables."""

    def __init__(self, conn: Optional[psycopg.Connection] = None):
        super().__init__(conn)
        self._cache: Dict[str, List[LookupCode]] = {}

    def get_all(self, table_name: str, use_cache: bool = True) -> List[LookupCode]:
        """Retrieves all active lookup entries for a specified lookup table."""
        if table_name not in VALID_LOOKUP_TABLES:
            raise ValueError(f"Invalid lookup table name: '{table_name}'. Must be one of {VALID_LOOKUP_TABLES}")

        if use_cache and table_name in self._cache:
            return self._cache[table_name]

        query = f"""
            SELECT code, display_name, description, is_active, sort_order, created_at
            FROM {table_name}
            WHERE is_active = TRUE
            ORDER BY sort_order ASC;
        """

        with self.get_connection() as conn:
            rows = conn.execute(query).fetchall()
            results = [LookupCode.model_validate(dict(row)) for row in rows]
            if use_cache:
                self._cache[table_name] = results
            return results

    def is_valid_code(self, table_name: str, code: str) -> bool:
        """Checks if a given code is active and exists in the specified lookup table."""
        items = self.get_all(table_name)
        return any(item.code == code for item in items)
