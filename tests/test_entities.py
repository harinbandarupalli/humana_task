"""Unit tests for domain entities using standard library unittest."""

import unittest
from datetime import datetime
from decimal import Decimal

try:
    from src.orchestrator.entities import (
        LookupCode,
        NodeExecutionCheckpoint,
        OrderInventoryTransaction,
        OrderLineItem,
        OrderNotification,
        OrderOrchestrationRun,
    )
    ENTITIES_AVAILABLE = True
except ImportError:
    ENTITIES_AVAILABLE = False


class TestDomainEntities(unittest.TestCase):
    """Tests for Pydantic domain entities."""

    def test_order_orchestration_run_entity(self):
        """Validates instantiation and serialization of OrderOrchestrationRun."""
        if not ENTITIES_AVAILABLE:
            self.skipTest("Dependencies not installed in global environment")

        now = datetime.utcnow()
        run = OrderOrchestrationRun(
            order_id="ORD-99881",
            thread_id="ORD-99881",
            user_id="USR-4421",
            customer_email="alice@example.com",
            customer_phone="+15551234567",
            order_placed_at=now,
            order_type="STANDARD",
            payment_status="SUCCESS",
            current_stage="INGESTION",
            status="RUNNING",
            total_amount=Decimal("149.99"),
            shipping_address={"city": "Austin", "state": "TX"},
        )

        self.assertEqual(run.order_id, "ORD-99881")
        self.assertEqual(run.user_id, "USR-4421")
        self.assertEqual(run.customer_email, "alice@example.com")
        self.assertEqual(run.customer_phone, "+15551234567")
        self.assertEqual(run.total_amount, Decimal("149.99"))
        data = run.to_dict()
        self.assertEqual(data["order_id"], "ORD-99881")

    def test_order_line_item_entity(self):
        """Validates instantiation of OrderLineItem."""
        if not ENTITIES_AVAILABLE:
            self.skipTest("Dependencies not installed in global environment")

        item = OrderLineItem(
            order_id="ORD-99881",
            item_id="ITEM-1",
            product_id="PROD-100",
            sku="SKU-100-RED",
            product_name="Red Sneakers",
            quantity_ordered=2,
            unit_price=Decimal("49.99"),
        )

        self.assertEqual(item.order_id, "ORD-99881")
        self.assertEqual(item.sku, "SKU-100-RED")
        self.assertEqual(item.quantity_ordered, 2)
        self.assertEqual(item.stock_status, "PENDING_CHECK")

    def test_node_execution_checkpoint_entity(self):
        """Validates instantiation of NodeExecutionCheckpoint."""
        if not ENTITIES_AVAILABLE:
            self.skipTest("Dependencies not installed in global environment")

        checkpoint = NodeExecutionCheckpoint(
            order_id="ORD-99881",
            node_name="order_ingest",
            stage_version=1,
            execution_status="COMPLETED",
            duration_ms=45,
            llm_generated_comment="Order successfully validated.",
        )

        self.assertEqual(checkpoint.order_id, "ORD-99881")
        self.assertEqual(checkpoint.duration_ms, 45)
        self.assertEqual(checkpoint.llm_generated_comment, "Order successfully validated.")

    def test_order_notification_entity(self):
        """Validates instantiation of OrderNotification."""
        if not ENTITIES_AVAILABLE:
            self.skipTest("Dependencies not installed in global environment")

        notification = OrderNotification(
            order_id="ORD-99881",
            node_name="notification_review",
            idempotency_key="ORD-99881:OUT_OF_STOCK_ALERT:SKU-100-RED",
            recipient_email="alice@example.com",
            notification_type="OUT_OF_STOCK_ALERT",
            subject="Item Out of Stock",
            body_text="Your item is currently backordered.",
        )

        self.assertEqual(notification.idempotency_key, "ORD-99881:OUT_OF_STOCK_ALERT:SKU-100-RED")
        self.assertEqual(notification.status, "PENDING")

    def test_inventory_transaction_entity(self):
        """Validates instantiation of OrderInventoryTransaction."""
        if not ENTITIES_AVAILABLE:
            self.skipTest("Dependencies not installed in global environment")

        tx = OrderInventoryTransaction(
            order_id="ORD-99881",
            product_id="PROD-100",
            sku="SKU-100-RED",
            transaction_type="DEDUCTION",
            quantity=2,
            status="SUCCESS",
            external_reference_id="INV-TX-9901",
        )

        self.assertEqual(tx.order_id, "ORD-99881")
        self.assertEqual(tx.quantity, 2)
        self.assertEqual(tx.transaction_type, "DEDUCTION")


if __name__ == "__main__":
    unittest.main()
