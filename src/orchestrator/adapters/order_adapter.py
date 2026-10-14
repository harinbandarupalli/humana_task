"""External API adapter for ORDER API and ORDER_DETAILS API."""

from datetime import datetime, timezone
from typing import Any, Dict, List
from src.orchestrator.adapters.base import BaseApiAdapter
from src.orchestrator.config.settings import settings
from src.orchestrator.core.logging import logger


class OrderApiAdapter(BaseApiAdapter):
    """Adapter for fetching order header and line item details."""

    def __init__(self, base_url: str = settings.ORDER_API_URL):
        super().__init__(base_url)

    def fetch_order(self, order_id: str) -> Dict[str, Any]:
        """Fetches top-level order details from ORDER API."""
        if self.use_mock:
            logger.info(f"[Mock OrderApi] Returning mock order header for {order_id}")
            # Determine mock type based on order_id suffix for flexible testing
            is_pre_order = order_id.endswith("-PRE")
            is_unpaid = order_id.endswith("-UNPAID")
            is_invalid_address = "INVALID" in order_id or "BAD_ADDR" in order_id

            return {
                "order_id": order_id,
                "user_id": f"USR-{order_id.replace('ORD-', '')[:4]}",
                "customer_email": "customer@example.com",
                "customer_phone": "+1-555-019-2834",
                "order_placed_at": datetime.now(timezone.utc).isoformat(),
                "order_type": "PRE_ORDER" if is_pre_order else "STANDARD",
                "payment_status": "FAILED" if is_unpaid else "SUCCESS",
                "order_status": "PENDING_TO_SHIP",
                "currency": "USD",
                "total_amount": 299.98,
                "shipping_address": {
                    "street_1": "INVALID Nowhere Way" if is_invalid_address else "100 Innovation Way",
                    "city": "Austin",
                    "state": "TX",
                    "postal_code": "78701",
                    "country": "USA",
                },
                "billing_address": {
                    "street_1": "100 Innovation Way",
                    "city": "Austin",
                    "state": "TX",
                    "postal_code": "78701",
                    "country": "USA",
                },
            }

        return self.client.get(f"/{order_id}", order_id=order_id)

    def fetch_order_details(self, order_id: str) -> List[Dict[str, Any]]:
        """Fetches line items for an order from ORDER_DETAILS API."""
        if self.use_mock:
            if "RACE" in order_id:
                return [
                    {
                        "item_id": "ITEM-101",
                        "product_id": "PROD-A",
                        "sku": "SKU-A-BLUE",
                        "product_name": "Premium Wireless Headphones",
                        "quantity_ordered": 1,
                        "unit_price": 199.99,
                        "is_digital": False,
                    },
                    {
                        "item_id": "ITEM-102",
                        "product_id": "PROD-B",
                        "sku": "SKU-B-FAIL_DEDUCT",
                        "product_name": "High-Demand Hot Commodity Item",
                        "quantity_ordered": 1,
                        "unit_price": 89.99,
                        "is_digital": False,
                    },
                ]

            if "SHORTAGE" in order_id:
                return [
                    {
                        "item_id": "ITEM-101",
                        "product_id": "PROD-A",
                        "sku": "SKU-A-BLUE",
                        "product_name": "Premium Wireless Headphones",
                        "quantity_ordered": 1,
                        "unit_price": 199.99,
                        "is_digital": False,
                    },
                    {
                        "item_id": "ITEM-102",
                        "product_id": "PROD-B",
                        "sku": "SKU-OOS-MOUSE",
                        "product_name": "Ergonomic Bluetooth Mouse",
                        "quantity_ordered": 2,
                        "unit_price": 49.99,
                        "is_digital": False,
                    },
                    {
                        "item_id": "ITEM-103",
                        "product_id": "PROD-C",
                        "sku": "SKU-DISC-ADAPTER",
                        "product_name": "Legacy Serial Adapter Cable",
                        "quantity_ordered": 1,
                        "unit_price": 15.00,
                        "is_digital": False,
                    },
                ]

            return [
                {
                    "item_id": "ITEM-101",
                    "product_id": "PROD-A",
                    "sku": "SKU-A-BLUE",
                    "product_name": "Premium Wireless Headphones",
                    "quantity_ordered": 1,
                    "unit_price": 199.99,
                    "is_digital": False,
                },
                {
                    "item_id": "ITEM-102",
                    "product_id": "PROD-B",
                    "sku": "SKU-B-BLACK",
                    "product_name": "USB-C Charging Hub",
                    "quantity_ordered": 2,
                    "unit_price": 49.99,
                    "is_digital": False,
                },
            ]

        res = self.client.get(f"/{order_id}/items", order_id=order_id)
        return res.get("items", [])
