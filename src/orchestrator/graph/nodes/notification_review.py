"""Node 3: Notification Review & Intelligent Operations Escalation."""

from typing import Any, Dict
from src.orchestrator.core.log_helper import get_order_logger, order_log_context
from src.orchestrator.schema.state import OrchestratorState
from src.orchestrator.services.notification_service import NotificationService

logger = get_order_logger(__name__)


def notification_review_node(state: OrchestratorState) -> Dict[str, Any]:
    """
    LangGraph Node 3: Notification Review & Operations Escalation.
    When inventory shortages or discontinued items occur, uses Multi-Model LLM
    via centralized prompts.json to generate an exhaustive operational dossier
    for human fulfillment agents, and idempotently dispatches an internal alert.
    If all items are in stock, skips escalation cleanly.
    """
    order_id = state.get("order_id", "ORD-UNKNOWN")
    user_id = state.get("user_id", "USR-UNKNOWN")
    line_items = state.get("line_items", [])
    ineligible_items = state.get("ineligible_items", [])
    fulfillment_type = state.get("fulfillment_type", "FULL")
    customer_email = state.get("customer_email")
    order_metadata = {
        "order_placed_at": state.get("order_placed_at"),
        "customer_email": customer_email,
        "shipping_address": state.get("shipping_address", {}),
    }

    with order_log_context(order_id=order_id, node_name="notification_review", user_id=user_id, stage_version=3) as log:
        log.append_state_info(
            f"[notification_review] Evaluating inventory health and ops escalation for {order_id} ({len(line_items)} items)..."
        )

        service = NotificationService()
        try:
            result = service.process_notification_review(
                order_id=order_id,
                line_items=line_items,
                ineligible_items=ineligible_items,
                fulfillment_type=fulfillment_type,
                customer_email=customer_email,
                order_metadata=order_metadata,
                stage_version=3,
            )
        except Exception as exc:
            log.append_state_error(f"[notification_review] Ops notification review failed for {order_id}: {exc}")
            raise

        llm_comment = result.get("llm_comment")
        if llm_comment:
            log.append_state_warning(
                f"[notification_review] Shortages detected ({len(ineligible_items)} items). "
                f"Ops review dossier compiled and dispatched to fulfillment operations."
            )
        else:
            log.append_state_info(
                f"[notification_review] All items in stock (fulfillment={fulfillment_type}). Ops escalation skipped."
            )

        llm_comments = [llm_comment] if llm_comment else []

        return {
            "current_stage": "NOTIFICATION_REVIEW",
            "stage_version": 3,
            "llm_comments": llm_comments,
            "email_sent": result.get("email_sent", False),
            "stage_history": ["NOTIFICATION_REVIEW"],
            "logs": log.get_buffered_logs(),
        }
