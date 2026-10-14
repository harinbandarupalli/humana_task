"""Node 5: Shipping Fulfillment & Carrier Dispatch."""

from typing import Any, Dict
from src.orchestrator.core.log_helper import get_order_logger, order_log_context
from src.orchestrator.schema.state import OrchestratorState
from src.orchestrator.services.shipping_service import ShippingService

logger = get_order_logger(__name__)


def shipping_fulfillment_node(state: OrchestratorState) -> Dict[str, Any]:
    """
    LangGraph Node 5: Shipping Fulfillment & Carrier Dispatch.
    Validates destination address, dispatches shipment via carrier API,
    generates closing executive fulfillment report via LLM, and marks order completed.
    If address is invalid or stock is completely unavailable, routes to WAITING_HUMAN_REVIEW.
    """
    order_id = state.get("order_id", "ORD-UNKNOWN")
    user_id = state.get("user_id", "USR-UNKNOWN")
    stage_version = 5
    eligible_items = state.get("eligible_items", [])
    ineligible_items = state.get("ineligible_items", [])
    shipping_address = state.get("shipping_address")

    with order_log_context(order_id=order_id, node_name="shipping_fulfillment", user_id=user_id, stage_version=stage_version) as log:
        log.append_state_info(
            f"[shipping_fulfillment] Starting shipping fulfillment for order {order_id} "
            f"({len(eligible_items)} eligible items)..."
        )

        service = ShippingService()
        result = service.process_shipping_fulfillment(
            order_id=order_id,
            eligible_items=eligible_items,
            ineligible_items=ineligible_items,
            shipping_address=shipping_address,
            stage_version=stage_version,
        )

        if result.get("human_in_loop") and not result.get("shipping_completed"):
            log.append_state_warning(
                f"[shipping_fulfillment] Shipping paused for human review: {result.get('human_review_reason')}"
            )
        else:
            log.append_state_info(
                f"[shipping_fulfillment] Shipment dispatched via {result.get('carrier_name')} "
                f"(tracking={result.get('tracking_number')}, type={result.get('fulfillment_type')})."
            )

        llm_report = result.get("llm_summary_report")
        llm_comments = [llm_report] if llm_report else []

        return {
            "current_stage": "SHIPPING_FULFILLMENT",
            "stage_version": stage_version,
            "status": result.get("status", "COMPLETED"),
            "fulfillment_type": result.get("fulfillment_type", state.get("fulfillment_type", "FULL")),
            "human_in_loop": result.get("human_in_loop", False),
            "human_review_reason": result.get("human_review_reason"),
            "carrier_name": result.get("carrier_name"),
            "tracking_number": result.get("tracking_number"),
            "shipping_completed": result.get("shipping_completed", False),
            "llm_summary_report": llm_report,
            "llm_comments": llm_comments,
            "stage_history": ["SHIPPING_FULFILLMENT"],
            "logs": log.get_buffered_logs(),
        }
