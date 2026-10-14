"""Dedicated repository for order_inventory_transactions table."""

from typing import Any, Dict, List, Optional
import psycopg
from src.orchestrator.entities.inventory_transaction import OrderInventoryTransaction
from src.orchestrator.repositories.base import BaseRepository


class InventoryTransactionRepository(BaseRepository):
    """Data access repository for order_inventory_transactions."""

    def __init__(self, conn: Optional[psycopg.Connection] = None):
        super().__init__(conn)

    @staticmethod
    def _from_row(row: Dict[str, Any]) -> OrderInventoryTransaction:
        """Converts database row dictionary to OrderInventoryTransaction entity."""
        return OrderInventoryTransaction.model_validate(dict(row))

    def record_transaction(self, tx: OrderInventoryTransaction) -> OrderInventoryTransaction:
        """Inserts an immutable inventory ledger transaction (deduction or rollback)."""
        query = """
            INSERT INTO order_inventory_transactions (
                order_id, product_id, sku, transaction_type,
                quantity, external_reference_id, status, reason
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s, %s
            )
            RETURNING *;
        """
        params = (
            tx.order_id,
            tx.product_id,
            tx.sku,
            tx.transaction_type,
            tx.quantity,
            tx.external_reference_id,
            tx.status,
            tx.reason,
        )

        with self.get_connection() as conn:
            row = conn.execute(query, params).fetchone()
            return self._from_row(row)

    def find_by_order_id(self, order_id: str) -> List[OrderInventoryTransaction]:
        """Retrieves all inventory ledger entries for an order in chronological order."""
        query = """
            SELECT * FROM order_inventory_transactions
            WHERE order_id = %s
            ORDER BY tx_number ASC;
        """
        with self.get_connection() as conn:
            rows = conn.execute(query, (order_id,)).fetchall()
            return [self._from_row(row) for row in rows]

    def get_total_deducted(self, order_id: str, sku: str) -> int:
        """
        Computes the net quantity deducted for an order and SKU,
        accounting for deductions and rollback releases.
        """
        query = """
            SELECT 
                COALESCE(SUM(CASE WHEN transaction_type = 'DEDUCTION' AND status = 'SUCCESS' THEN quantity ELSE 0 END), 0) -
                COALESCE(SUM(CASE WHEN transaction_type = 'ROLLBACK_RELEASE' AND status = 'SUCCESS' THEN quantity ELSE 0 END), 0) AS net_deducted
            FROM order_inventory_transactions
            WHERE order_id = %s AND sku = %s;
        """
        with self.get_connection() as conn:
            row = conn.execute(query, (order_id, sku)).fetchone()
            return int(row["net_deducted"]) if row else 0
