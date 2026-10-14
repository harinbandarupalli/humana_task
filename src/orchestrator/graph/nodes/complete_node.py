"""Node 7: Complete Terminal Node."""

from typing import Any, Dict
from src.orchestrator.core.log_helper import get_order_logger, order_log_context
from src.orchestrator.schema.state import OrchestratorState

logger = get_order_logger(__name__)


def complete_node(state: OrchestratorState) -> Dict[str, Any]:
    """
    LangGraph Node 7: Complete Terminal Node.
    Concludes the order orchestration workflow lifecycle and finalizes audit logs.
    """
    order_id = state.get("order_id", "ORD-UNKNOWN")
    user_id = state.get("user_id", "USR-UNKNOWN")
    status = state.get("status", "COMPLETED")

    with order_log_context(order_id=order_id, node_name="complete_node", user_id=user_id) as log:
        log.append_state_info(f"[complete_node] Order {order_id} workflow concluded. Final status: {status}")

        return {
            "current_stage": "COMPLETED",
            "status": status,
            "stage_history": ["COMPLETED"],
            "logs": log.get_buffered_logs(),
        }
