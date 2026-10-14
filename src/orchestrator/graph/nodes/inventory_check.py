"""Node 2: Inventory Assessment & Real-Time Stock Verification."""

from typing import Any, Dict
from src.orchestrator.core.log_helper import get_order_logger, order_log_context
from src.orchestrator.schema.state import OrchestratorState
from src.orchestrator.services.inventory_service import InventoryService

logger = get_order_logger(__name__)


def inventory_check_node(state: OrchestratorState) -> Dict[str, Any]:
    """
    LangGraph Node 2: Inventory Assessment.
    Evaluates real-time warehouse inventory for all items in the order,
    classifies stock availability, separates eligible vs ineligible items,
    and determines order fulfillment classification (FULL, PARTIAL, NONE).
    """
    order_id = state.get("order_id", "ORD-UNKNOWN")
    user_id = state.get("user_id", "USR-UNKNOWN")
    state_line_items = state.get("line_items", [])

    with order_log_context(order_id=order_id, node_name="inventory_check", user_id=user_id, stage_version=2) as log:
        log.append_state_info(
            f"[inventory_check] Starting inventory check for order {order_id} ({len(state_line_items)} line items)..."
        )

        service = InventoryService()
        try:
            result = service.assess_inventory(order_id=order_id, state_line_items=state_line_items)
        except Exception as exc:
            log.append_state_error(f"[inventory_check] Inventory evaluation failed for {order_id}: {exc}")
            raise

        # Log item-level assessment details
        for item in result.get("line_items", []):
            sku = item.get("sku")
            qty_avail = item.get("quantity_available", 0)
            qty_req = item.get("quantity_ordered", 1)
            status = item.get("stock_status", "UNKNOWN")

            if item.get("is_discontinued"):
                log.append_state_warning(f"[inventory_check] SKU {sku} is DISCONTINUED by supplier.")
            elif status == "OUT_OF_STOCK":
                log.append_state_warning(f"[inventory_check] SKU {sku} is OUT_OF_STOCK (0 available, {qty_req} ordered).")
            elif status == "PARTIAL_STOCK":
                log.append_state_warning(f"[inventory_check] SKU {sku} has PARTIAL_STOCK ({qty_avail} available, {qty_req} ordered).")
            else:
                log.append_state_info(f"[inventory_check] SKU {sku} is IN_STOCK (available: {qty_avail}, ordered: {qty_req}).")

        fulfillment = result.get("fulfillment_type", "NONE")
        eligible_count = len(result.get("eligible_items", []))
        ineligible_count = len(result.get("ineligible_items", []))

        if fulfillment == "FULL":
            log.append_state_info(
                f"[inventory_check] Order {order_id} 100% available ({eligible_count} eligible, 0 shortages). Ready for fulfillment."
            )
        else:
            log.append_state_warning(
                f"[inventory_check] Order {order_id} shortages detected ({eligible_count} eligible, {ineligible_count} shortages). Fulfillment set to {fulfillment}."
            )

        return {
            "current_stage": "INVENTORY_CHECK",
            "stage_version": 2,
            "line_items": result.get("line_items", []),
            "eligible_items": result.get("eligible_items", []),
            "ineligible_items": result.get("ineligible_items", []),
            "fulfillment_type": fulfillment,
            "stage_history": ["INVENTORY_CHECK"],
            "logs": log.get_buffered_logs(),
        }
