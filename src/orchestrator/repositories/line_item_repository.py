"""Dedicated repository for order_line_items table."""

import json
from typing import Any, Dict, List, Optional
import psycopg
from src.orchestrator.entities.line_item import OrderLineItem
from src.orchestrator.repositories.base import BaseRepository
from src.orchestrator.repositories.exceptions import EntityNotFoundError


class LineItemRepository(BaseRepository):
    """Data access repository for order_line_items."""

    def __init__(self, conn: Optional[psycopg.Connection] = None):
        super().__init__(conn)

    @staticmethod
    def _from_row(row: Dict[str, Any]) -> OrderLineItem:
        """Converts database row dictionary to OrderLineItem entity."""
        return OrderLineItem.model_validate(dict(row))

    def bulk_upsert(self, items: List[OrderLineItem]) -> None:
        """
        Inserts or updates line items for an order.
        Handles conflict on (order_id, item_id) uniquely.
        """
        if not items:
            return

        query = """
            INSERT INTO order_line_items (
                order_id, item_id, product_id, sku, product_name,
                quantity_ordered, quantity_available, quantity_deducted, quantity_shipped,
                unit_price, is_discontinued, stock_status, deduction_status, shipping_status, item_metadata
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (order_id, item_id) DO UPDATE
            SET quantity_available = EXCLUDED.quantity_available,
                quantity_deducted = EXCLUDED.quantity_deducted,
                quantity_shipped = EXCLUDED.quantity_shipped,
                is_discontinued = EXCLUDED.is_discontinued,
                stock_status = EXCLUDED.stock_status,
                deduction_status = EXCLUDED.deduction_status,
                shipping_status = EXCLUDED.shipping_status,
                item_metadata = EXCLUDED.item_metadata,
                updated_at = CURRENT_TIMESTAMP;
        """

        with self.get_connection() as conn:
            for item in items:
                conn.execute(
                    query,
                    (
                        item.order_id,
                        item.item_id,
                        item.product_id,
                        item.sku,
                        item.product_name,
                        item.quantity_ordered,
                        item.quantity_available,
                        item.quantity_deducted,
                        item.quantity_shipped,
                        item.unit_price,
                        item.is_discontinued,
                        item.stock_status,
                        item.deduction_status,
                        item.shipping_status,
                        json.dumps(item.item_metadata),
                    ),
                )

    def find_by_order_id(self, order_id: str) -> List[OrderLineItem]:
        """Fetches all line items associated with an order."""
        query = """
            SELECT * FROM order_line_items
            WHERE order_id = %s
            ORDER BY line_number ASC;
        """
        with self.get_connection() as conn:
            rows = conn.execute(query, (order_id,)).fetchall()
            return [self._from_row(row) for row in rows]

    def find_by_order_and_sku(self, order_id: str, sku: str) -> Optional[OrderLineItem]:
        """Finds a specific line item by order_id and SKU."""
        query = "SELECT * FROM order_line_items WHERE order_id = %s AND sku = %s;"
        with self.get_connection() as conn:
            row = conn.execute(query, (order_id, sku)).fetchone()
            return self._from_row(row) if row else None

    def update_inventory_assessment(
        self,
        order_id: str,
        item_id: str,
        quantity_available: int,
        is_discontinued: bool,
        stock_status: str,
    ) -> None:
        """Updates inventory check results for a single line item."""
        query = """
            UPDATE order_line_items
            SET quantity_available = %s,
                is_discontinued = %s,
                stock_status = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE order_id = %s AND item_id = %s;
        """
        with self.get_connection() as conn:
            res = conn.execute(query, (quantity_available, is_discontinued, stock_status, order_id, item_id))
            if res.rowcount == 0:
                raise EntityNotFoundError(f"Line item '{item_id}' for order '{order_id}' not found.")

    def update_deduction_status(
        self,
        order_id: str,
        item_id: str,
        quantity_deducted: int,
        deduction_status: str,
    ) -> None:
        """Updates deduction result for a single line item."""
        query = """
            UPDATE order_line_items
            SET quantity_deducted = %s,
                deduction_status = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE order_id = %s AND item_id = %s;
        """
        with self.get_connection() as conn:
            res = conn.execute(query, (quantity_deducted, deduction_status, order_id, item_id))
            if res.rowcount == 0:
                raise EntityNotFoundError(f"Line item '{item_id}' for order '{order_id}' not found.")

    def update_shipping_status(
        self,
        order_id: str,
        item_id: str,
        quantity_shipped: int,
        shipping_status: str,
    ) -> None:
        """Updates shipping outcome for a line item."""
        query = """
            UPDATE order_line_items
            SET quantity_shipped = %s,
                shipping_status = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE order_id = %s AND item_id = %s;
        """
        with self.get_connection() as conn:
            res = conn.execute(query, (quantity_shipped, shipping_status, order_id, item_id))
            if res.rowcount == 0:
                raise EntityNotFoundError(f"Line item '{item_id}' for order '{order_id}' not found.")

    def get_out_of_stock_items(self, order_id: str) -> List[OrderLineItem]:
        """Retrieves items that are OUT_OF_STOCK or DISCONTINUED."""
        query = """
            SELECT * FROM order_line_items
            WHERE order_id = %s
              AND stock_status IN ('OUT_OF_STOCK', 'PARTIAL_STOCK', 'DISCONTINUED');
        """
        with self.get_connection() as conn:
            rows = conn.execute(query, (order_id,)).fetchall()
            return [self._from_row(row) for row in rows]

    def get_eligible_items(self, order_id: str) -> List[OrderLineItem]:
        """Retrieves items that are in stock and ready for deduction and shipping."""
        query = """
            SELECT * FROM order_line_items
            WHERE order_id = %s
              AND stock_status = 'IN_STOCK'
              AND is_discontinued = FALSE;
        """
        with self.get_connection() as conn:
            rows = conn.execute(query, (order_id,)).fetchall()
            return [self._from_row(row) for row in rows]
