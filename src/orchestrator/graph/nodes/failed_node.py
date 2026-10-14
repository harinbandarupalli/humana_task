"""Node 8: Failed Terminal Node."""

from typing import Any, Dict
from src.orchestrator.core.log_helper import get_order_logger, order_log_context
from src.orchestrator.schema.state import OrchestratorState

logger = get_order_logger(__name__)


def failed_node(state: OrchestratorState) -> Dict[str, Any]:
    """
    LangGraph Node 8: Failed / Terminated Terminal Node.
    Handles terminal failure states including duplicate suppression, pre-orders, and unrecoverable errors.
    """
    order_id = state.get("order_id", "ORD-UNKNOWN")
    user_id = state.get("user_id", "USR-UNKNOWN")
    status = state.get("status", "FAILED")
    error = state.get("error")

    with order_log_context(order_id=order_id, node_name="failed_node", user_id=user_id) as log:
        log.append_state_error(f"[failed_node] Order {order_id} workflow terminated with status {status}. Reason: {error or 'Terminated'}")

        return {
            "current_stage": "FAILED",
            "status": status,
            "stage_history": ["FAILED"],
            "logs": log.get_buffered_logs(),
        }
