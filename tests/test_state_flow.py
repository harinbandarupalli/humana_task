"""Unit tests for LangGraph Order Orchestration State flow and stage transitions."""

from datetime import datetime, timezone
import pytest
from langgraph.checkpoint.memory import MemorySaver
from src.orchestrator.graph.builder import build_orchestrator_graph
from src.orchestrator.schema.state import OrchestratorState, WorkflowStage, OrderStatus


def _create_initial_state(order_id: str) -> OrchestratorState:
    return {
        "order_id": order_id,
        "thread_id": order_id,
        "user_id": "USR-TEST-01",
        "customer_email": "tester@example.com",
        "customer_phone": "+1-555-010-0000",
        "order_placed_at": datetime.now(timezone.utc).isoformat(),
        "order_type": "STANDARD",
        "payment_status": "SUCCESS",
        "current_stage": "INIT",
        "status": "PENDING",
        "fulfillment_type": "NONE",
        "stage_version": 0,
        "is_duplicate": False,
        "is_pre_order": False,
        "human_in_loop": False,
        "human_review_reason": None,
        "deduction_completed": False,
        "rollback_needed": False,
        "deduction_loop_count": 0,
        "shipping_completed": False,
        "line_items": [],
        "eligible_items": [],
        "ineligible_items": [],
        "shipping_address": {},
        "billing_address": {},
        "carrier_name": None,
        "tracking_number": None,
        "llm_comments": [],
        "llm_summary_report": None,
        "email_sent": False,
        "stage_history": [],
        "logs": [],
        "error": None,
    }


def test_standard_order_orchestration_flow():
    """Tests end-to-end flow for 100% in-stock order resulting in COMPLETED."""
    checkpointer = MemorySaver()
    graph = build_orchestrator_graph(checkpointer=checkpointer, enable_interrupts=False)

    order_id = "ORD-DEMO-001"
    config = {"configurable": {"thread_id": order_id}}
    initial_state = _create_initial_state(order_id)

    final_state = graph.invoke(initial_state, config=config)

    assert final_state["current_stage"] == "COMPLETED"
    assert final_state["status"] == "COMPLETED"
    assert final_state["fulfillment_type"] == "FULL"
    assert final_state["tracking_number"] is not None
    assert final_state["tracking_number"].startswith("TRK-")
    assert "INGESTION" in final_state["stage_history"]
    assert "INVENTORY_CHECK" in final_state["stage_history"]
    assert "NOTIFICATION_REVIEW" in final_state["stage_history"]
    assert "INVENTORY_DEDUCT" in final_state["stage_history"]
    assert "SHIPPING_FULFILLMENT" in final_state["stage_history"]
    assert "COMPLETED" in final_state["stage_history"]


def test_shortage_order_orchestration_flow():
    """Tests shortage order resulting in PARTIALLY_SHIPPED with operations dossier."""
    checkpointer = MemorySaver()
    graph = build_orchestrator_graph(checkpointer=checkpointer, enable_interrupts=False)

    order_id = "ORD-SHORTAGE-001"
    config = {"configurable": {"thread_id": order_id}}
    initial_state = _create_initial_state(order_id)

    final_state = graph.invoke(initial_state, config=config)

    assert final_state["status"] == "PARTIALLY_SHIPPED"
    assert final_state["fulfillment_type"] == "PARTIAL"
    assert final_state["tracking_number"] is not None
    assert "WAITING_HUMAN_REVIEW" in final_state["stage_history"]
    assert len(final_state["llm_comments"]) > 0


def test_race_condition_loopback_flow():
    """Tests dynamic rollback and loopback from deduct to notification_review."""
    checkpointer = MemorySaver()
    graph = build_orchestrator_graph(checkpointer=checkpointer, enable_interrupts=False)

    order_id = "ORD-RACE-001"
    config = {"configurable": {"thread_id": order_id}}
    initial_state = _create_initial_state(order_id)

    final_state = graph.invoke(initial_state, config=config)

    assert final_state["status"] == "PARTIALLY_SHIPPED"
    history = final_state["stage_history"]
    deduct_indices = [i for i, stage in enumerate(history) if stage == "INVENTORY_DEDUCT"]
    assert len(deduct_indices) == 2, "Expected 2 deduction attempts due to race loopback"


def test_invalid_address_routing_flow():
    """Tests invalid destination address triggering human review gate."""
    checkpointer = MemorySaver()
    graph = build_orchestrator_graph(checkpointer=checkpointer, enable_interrupts=False)

    order_id = "ORD-INVALID-001"
    config = {"configurable": {"thread_id": order_id}}
    initial_state = _create_initial_state(order_id)

    final_state = graph.invoke(initial_state, config=config)

    assert final_state["status"] == "WAITING_HUMAN_REVIEW"
    assert final_state["human_in_loop"] is True
    assert final_state["human_review_reason"] is not None
    assert "WAITING_HUMAN_REVIEW" in final_state["stage_history"]
