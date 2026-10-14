"""Edge routing functions for order orchestrator StateGraph."""

from typing import Literal
from src.orchestrator.schema.state import OrchestratorState


def route_after_ingest(state: OrchestratorState) -> Literal["failed", "inventory_check"]:
    """Routes to failed terminal node if error/terminate is set, otherwise advances to inventory check."""
    if state.get("error") or state.get("status") in ("FAILED", "DUPLICATE", "DEFERRED_PRE_ORDER"):
        return "failed"
    return "inventory_check"


def route_after_deduct(
    state: OrchestratorState,
) -> Literal["notification_review", "shipping_fulfillment", "human_review_gate"]:
    """Routes back to notification review on rollback, human review if loops exceeded, otherwise advances to shipping."""
    if state.get("human_in_loop") is True:
        return "human_review_gate"
    if state.get("rollback_needed") is True:
        return "notification_review"
    return "shipping_fulfillment"


def route_after_shipping(state: OrchestratorState) -> Literal["human_review_gate", "complete"]:
    """Routes to human review gate if operator review is flagged, otherwise concludes at complete."""
    if state.get("human_in_loop") is True:
        return "human_review_gate"
    return "complete"
