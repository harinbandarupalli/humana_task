"""LangGraph StateGraph builder for Order Orchestrator."""

from typing import Any, Optional
import httpx
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy
from src.orchestrator.clients.base_http import HttpServerError
from src.orchestrator.config.settings import settings
from src.orchestrator.core.logging import logger
from src.orchestrator.graph.edges.routers import (
    route_after_deduct,
    route_after_ingest,
    route_after_shipping,
)
from src.orchestrator.graph.nodes import (
    complete_node,
    failed_node,
    human_review_gate_node,
    inventory_check_node,
    inventory_deduct_node,
    notification_review_node,
    order_ingest_node,
    shipping_fulfillment_node,
)
from src.orchestrator.schema.state import OrchestratorState


def is_transient_retryable_error(exc: Exception) -> bool:
    """
    Classifies transient infrastructure errors for automatic node retries.
    Returns True for retryable network drops, timeouts, and 5xx errors;
    Returns False for deterministic business failures.
    """
    if isinstance(exc, (ConnectionError, TimeoutError, OSError)):
        logger.warning(f"[RetryableError] Transient system/network error: {exc}")
        return True
    if isinstance(exc, (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError)):
        logger.warning(f"[RetryableError] Transient HTTP transport error: {exc}")
        return True
    if isinstance(exc, HttpServerError) and exc.status_code in (500, 502, 503, 504):
        logger.warning(f"[RetryableError] Transient 5xx server error (status {exc.status_code}): {exc}")
        return True
    return False


def get_node_retry_policy() -> RetryPolicy:
    """Constructs LangGraph node-level retry policy from centralized settings."""
    return RetryPolicy(
        initial_interval=settings.NODE_RETRY_INITIAL_INTERVAL,
        backoff_factor=settings.NODE_RETRY_BACKOFF_FACTOR,
        max_interval=settings.NODE_RETRY_MAX_INTERVAL,
        max_attempts=settings.NODE_MAX_RETRIES,
        jitter=settings.NODE_RETRY_JITTER,
        retry_on=is_transient_retryable_error,
    )


def build_orchestrator_graph(
    checkpointer: Optional[Any] = None,
    enable_interrupts: bool = True,
):
    """
    Constructs and compiles the order orchestrator StateGraph.

    Args:
        checkpointer: LangGraph PostgresSaver or MemorySaver instance.
        enable_interrupts: If True, pauses execution at human_review_gate.
    """
    workflow = StateGraph(OrchestratorState)
    retry_policy = get_node_retry_policy()

    # 1. Register Nodes with System Retry Policy on Operational Nodes
    workflow.add_node("order_ingest", order_ingest_node, retry_policy=retry_policy)
    workflow.add_node("inventory_check", inventory_check_node, retry_policy=retry_policy)
    workflow.add_node("notification_review", notification_review_node, retry_policy=retry_policy)
    workflow.add_node("inventory_deduct", inventory_deduct_node, retry_policy=retry_policy)
    workflow.add_node("shipping_fulfillment", shipping_fulfillment_node, retry_policy=retry_policy)
    workflow.add_node("human_review_gate", human_review_gate_node)
    workflow.add_node("complete", complete_node)
    workflow.add_node("failed", failed_node)

    # 2. Register Normal Edges & Conditional Routers
    workflow.add_edge(START, "order_ingest")

    workflow.add_conditional_edges(
        "order_ingest",
        route_after_ingest,
        {
            "inventory_check": "inventory_check",
            "failed": "failed",
        },
    )

    workflow.add_edge("inventory_check", "notification_review")
    workflow.add_edge("notification_review", "inventory_deduct")

    workflow.add_conditional_edges(
        "inventory_deduct",
        route_after_deduct,
        {
            "notification_review": "notification_review",
            "shipping_fulfillment": "shipping_fulfillment",
            "human_review_gate": "human_review_gate",
        },
    )

    workflow.add_conditional_edges(
        "shipping_fulfillment",
        route_after_shipping,
        {
            "human_review_gate": "human_review_gate",
            "complete": "complete",
        },
    )

    workflow.add_edge("human_review_gate", "complete")
    workflow.add_edge("complete", END)
    workflow.add_edge("failed", END)

    # 3. Configure Human-In-The-Loop Interrupts
    interrupt_before = ["human_review_gate"] if enable_interrupts else None

    # Fallback to MemorySaver if checkpointer is not provided
    active_checkpointer = checkpointer if checkpointer is not None else MemorySaver()

    return workflow.compile(
        checkpointer=active_checkpointer,
        interrupt_before=interrupt_before,
    )
