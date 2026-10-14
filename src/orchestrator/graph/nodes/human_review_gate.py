"""Node 6: Human Review Gate."""

from typing import Any, Dict
from src.orchestrator.core.log_helper import get_order_logger, order_log_context
from src.orchestrator.schema.state import OrchestratorState

logger = get_order_logger(__name__)


def human_review_gate_node(state: OrchestratorState) -> Dict[str, Any]:
    """
    LangGraph Node 6: Human Review Gate.
    Provides operator triage review for address discrepancies, unfulfilled stock,
    or deduction loop threshold exhaustion.
    """
    order_id = state.get("order_id", "ORD-UNKNOWN")
    user_id = state.get("user_id", "USR-UNKNOWN")
    reason = state.get("human_review_reason", "Manual operator review required.")

    with order_log_context(order_id=order_id, node_name="human_review_gate", user_id=user_id) as log:
        log.append_state_warning(f"[human_review_gate] Order {order_id} escalated for human operator review. Reason: {reason}")

        return {
            "current_stage": "WAITING_HUMAN_REVIEW",
            "stage_history": ["WAITING_HUMAN_REVIEW"],
            "logs": log.get_buffered_logs(),
        }
