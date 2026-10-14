"""Node 1: Order Ingestion & Validation."""

from typing import Any, Dict
from src.orchestrator.core.log_helper import get_order_logger, order_log_context
from src.orchestrator.schema.state import OrchestratorState
from src.orchestrator.services.order_service import OrderService

logger = get_order_logger(__name__)


def order_ingest_node(state: OrchestratorState) -> Dict[str, Any]:
    """
    LangGraph Node 1: Order Ingestion & Validation.
    Calls Order API & Order Details API via OrderService.
    Identifies duplicates and pre-orders, and persists records to PostgreSQL.
    """
    order_id = state.get("order_id", "ORD-UNKNOWN")

    with order_log_context(order_id=order_id, node_name="order_ingest", stage_version=1) as log:
        log.append_state_info(f"[order_ingest] Processing ingestion for order {order_id}...")

        service = OrderService()
        result = service.ingest_order(order_id)

        if result.get("terminate"):
            err_msg = result.get("error", "Early termination")
            if result.get("status") in ("DUPLICATE", "DEFERRED_PRE_ORDER"):
                log.append_state_warning(f"[order_ingest] Order {order_id} flagged: {err_msg}")
            else:
                log.append_state_error(f"[order_ingest] Order {order_id} failed ingestion: {err_msg}")
        else:
            item_count = len(result.get("line_items", []))
            log.append_state_info(
                f"[order_ingest] Order {order_id} verified ({item_count} items). Ready for inventory check."
            )

        return {
            **result,
            "current_stage": "INGESTION",
            "stage_version": 1,
            "stage_history": ["INGESTION"],
            "logs": log.get_buffered_logs(),
        }
