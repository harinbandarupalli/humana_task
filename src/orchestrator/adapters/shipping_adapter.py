"""External API adapter for Carrier Logistics and Address Verification."""

import uuid
from typing import Any, Dict, List, Optional
from src.orchestrator.adapters.base import BaseApiAdapter
from src.orchestrator.config.settings import settings
from src.orchestrator.core.logging import logger


class ShippingApiAdapter(BaseApiAdapter):
    """Adapter for destination address validation and carrier shipment dispatch."""

    def __init__(self, base_url: str = settings.SHIPPING_API_URL):
        super().__init__(base_url)

    def validate_address(self, address: Dict[str, Any], order_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Validates destination shipping address.
        Returns:
            {
                "is_valid": bool,
                "standardized_address": dict,
                "error_reason": str (optional)
            }
        """
        if self.use_mock:
            street = address.get("street_1", "").upper()
            # Simulate invalid address if street contains "INVALID" or is empty
            if not street or "INVALID" in street:
                logger.warning(f"[Mock ShippingApi] Address invalid for street='{street}'")
                return {
                    "is_valid": False,
                    "standardized_address": address,
                    "error_reason": "Street address cannot be located by carrier database.",
                }

            logger.info("[Mock ShippingApi] Address validated successfully.")
            return {
                "is_valid": True,
                "standardized_address": {
                    **address,
                    "is_validated": True,
                    "carrier_dpv_confirmed": True,
                },
            }

        return self.client.post("/validate-address", json_data=address, order_id=order_id)

    def dispatch_shipment(
        self,
        order_id: str,
        items: List[Dict[str, Any]],
        address: Dict[str, Any],
        is_partial: bool = False,
    ) -> Dict[str, Any]:
        """
        Calls shipping carrier API (FedEx/UPS/DHL) to create shipment and tracking code.
        Returns:
            {
                "success": bool,
                "carrier_name": str,
                "tracking_number": str,
                "fulfillment_type": "FULL" or "PARTIAL",
                "label_url": str
            }
        """
        if self.use_mock:
            carrier = "FedEx Express"
            tracking = f"TRK-{uuid.uuid4().hex[:12].upper()}"
            fulfillment_type = "PARTIAL" if is_partial else "FULL"
            logger.info(
                f"[Mock ShippingApi] Shipment dispatched: order={order_id}, carrier={carrier}, tracking={tracking}, type={fulfillment_type}"
            )

            return {
                "success": True,
                "carrier_name": carrier,
                "tracking_number": tracking,
                "fulfillment_type": fulfillment_type,
                "label_url": f"https://shipping.labels.internal/{tracking}.pdf",
                "shipped_item_count": len(items),
            }

        payload = {
            "order_id": order_id,
            "items": items,
            "address": address,
            "is_partial": is_partial,
        }
        return self.client.post("/shipments", json_data=payload, order_id=order_id)
