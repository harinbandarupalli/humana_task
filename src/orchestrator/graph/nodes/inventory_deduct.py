"""Node 4: Inventory Deduction & Physical Stock Allocation."""

from typing import Any, Dict
from src.orchestrator.core.log_helper import get_order_logger, order_log_context
from src.orchestrator.schema.state import OrchestratorState
from src.orchestrator.services.inventory_service import InventoryService

logger = get_order_logger(__name__)


def inventory_deduct_node(state: OrchestratorState) -> Dict[str, Any]:
    """
    LangGraph Node 4: Inventory Deduction & Physical Stock Allocation.
    Invokes Warehouse Management API to deduct stock for all eligible line items.
    If a race condition occurs, records ledger rollback, moves failed items to shortages,
    and sets rollback_needed = True to trigger dynamic loopback to Node 3.
    """
    order_id = state.get("order_id", "ORD-UNKNOWN")
    user_id = state.get("user_id", "USR-UNKNOWN")
    eligible_items = state.get("eligible_items", [])
    ineligible_items = state.get("ineligible_items", [])
    line_items = state.get("line_items", [])
    deduction_loop_count = state.get("deduction_loop_count", 0)

    with order_log_context(order_id=order_id, node_name="inventory_deduct", user_id=user_id, stage_version=4) as log:
        log.append_state_info(
            f"[inventory_deduct] Initiating inventory deduction for {order_id} "
            f"({len(eligible_items)} eligible items, loop attempt {deduction_loop_count})..."
        )

        service = InventoryService()
        try:
            result = service.deduct_inventory(
                order_id=order_id,
                items_to_deduct=eligible_items,
                all_line_items=line_items,
                ineligible_items=ineligible_items,
                deduction_loop_count=deduction_loop_count,
                stage_version=4,
            )
        except Exception as exc:
            log.append_state_error(f"[inventory_deduct] Inventory deduction failed unexpectedly for {order_id}: {exc}")
            raise

        if result.get("success"):
            log.append_state_info(
                f"[inventory_deduct] Warehouse stock deducted successfully "
                f"({result.get('deducted_count')} items, tx={result.get('transaction_id')}). Ready for shipping."
            )
        else:
            if result.get("rollback_needed"):
                log.append_state_warning(
                    f"[inventory_deduct] Stock race-condition shortage on SKUs {result.get('failed_skus')}: "
                    f"{result.get('error_reason')}. Dynamic loopback to notification_review triggered!"
                )
            else:
                log.append_state_error(
                    f"[inventory_deduct] Maximum deduction loop count ({result.get('deduction_loop_count')}) exceeded. "
                    f"Escalating order {order_id} to human review gate."
                )

        return {
            "current_stage": "INVENTORY_DEDUCT",
            "stage_version": 4,
            "deduction_completed": result.get("deduction_completed", False),
            "rollback_needed": result.get("rollback_needed", False),
            "deduction_loop_count": result.get("deduction_loop_count", deduction_loop_count),
            "human_in_loop": result.get("human_in_loop", False),
            "human_review_reason": result.get("human_review_reason"),
            "line_items": result.get("line_items", line_items),
            "eligible_items": result.get("eligible_items", eligible_items),
            "ineligible_items": result.get("ineligible_items", ineligible_items),
            "fulfillment_type": result.get("fulfillment_type", state.get("fulfillment_type")),
            "stage_history": ["INVENTORY_DEDUCT"],
            "logs": log.get_buffered_logs(),
        }
