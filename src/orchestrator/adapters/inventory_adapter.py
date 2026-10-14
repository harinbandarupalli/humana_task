"""External API adapter for Warehouse Inventory Management System."""

import uuid
from typing import Any, Dict, List, Optional
from src.orchestrator.adapters.base import BaseApiAdapter
from src.orchestrator.config.settings import settings
from src.orchestrator.core.logging import logger


class InventoryApiAdapter(BaseApiAdapter):
    """Adapter for inventory checks, atomic stock deductions, and rollback releases."""

    def __init__(self, base_url: str = settings.INVENTORY_API_URL):
        super().__init__(base_url)

    def check_inventory(self, skus: List[str], order_id: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        """
        Queries current stock balance and discontinued status for each SKU.
        Returns a dictionary keyed by SKU:
        { "SKU-A": { "quantity_available": 10, "is_discontinued": False } }
        """
        if self.use_mock:
            logger.info(f"[Mock InventoryApi] Checking stock for SKUs: {skus}")
            result = {}
            for sku in skus:
                # Custom mock hooks for deterministic testing
                if "OOS" in sku:
                    result[sku] = {"quantity_available": 0, "is_discontinued": False}
                elif "DISC" in sku:
                    result[sku] = {"quantity_available": 0, "is_discontinued": True}
                else:
                    result[sku] = {"quantity_available": 50, "is_discontinued": False}
            return result

        res = self.client.post("/check", json_data={"skus": skus}, order_id=order_id)
        return res.get("inventory", {})

    def deduct_inventory(self, order_id: str, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calls inventory service to deduct/reserve available products.
        Returns:
            {
                "success": bool,
                "transaction_id": str,
                "deducted_skus": list,
                "failed_skus": list,
                "error_reason": str (optional)
            }
        """
        if self.use_mock:
            tx_id = f"INV-TX-{uuid.uuid4().hex[:8]}"
            logger.info(f"[Mock InventoryApi] Deducting inventory for order={order_id}, tx={tx_id}")

            # Check if any SKU triggers a simulated race condition failure
            failed_skus = [item["sku"] for item in items if "FAIL_DEDUCT" in item["sku"]]
            if failed_skus:
                logger.warning(f"[Mock InventoryApi] Simulated race condition on SKUs: {failed_skus}")
                return {
                    "success": False,
                    "transaction_id": tx_id,
                    "deducted_skus": [],
                    "failed_skus": failed_skus,
                    "error_reason": "Stock snatched by concurrent order during deduction.",
                }

            return {
                "success": True,
                "transaction_id": tx_id,
                "deducted_skus": [item["sku"] for item in items],
                "failed_skus": [],
            }

        return self.client.post("/deduct", json_data={"order_id": order_id, "items": items}, order_id=order_id)

    def release_inventory(self, order_id: str, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Rollback release: releases previously reserved stock back to warehouse balance.
        """
        if self.use_mock:
            tx_id = f"REL-TX-{uuid.uuid4().hex[:8]}"
            logger.info(f"[Mock InventoryApi] Releasing stock for order={order_id}, tx={tx_id}")
            return {
                "success": True,
                "transaction_id": tx_id,
                "released_skus": [item["sku"] for item in items],
            }

        return self.client.post("/release", json_data={"order_id": order_id, "items": items}, order_id=order_id)
