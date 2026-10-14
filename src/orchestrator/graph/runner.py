"""CLI and Local Runner for end-to-end orchestration execution."""

import sys
from datetime import datetime, timezone
from src.orchestrator.core.log_helper import get_order_logger
from src.orchestrator.graph.builder import build_orchestrator_graph
from src.orchestrator.schema.state import OrchestratorState

logger = get_order_logger(__name__)


def run_e2e_orchestration(order_id: str = "ORD-DEMO-001") -> None:
    """Executes the complete order orchestration graph end-to-end."""
    print("=" * 70)
    print(f"Starting E2E LangGraph Orchestrator Execution for Order: {order_id}")
    print("=" * 70)

    # 1. Compile Graph with in-memory checkpointer
    graph = build_orchestrator_graph(enable_interrupts=False)

    # 2. Prepare initial state
    initial_state: OrchestratorState = {
        "order_id": order_id,
        "thread_id": order_id,
        "user_id": "USR-1001",
        "customer_email": "customer@example.com",
        "customer_phone": "+1-555-010-9988",
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
        "line_items": [
            {
                "item_id": "ITEM-1",
                "product_id": "PROD-101",
                "sku": "SKU-A",
                "product_name": "Premium Keyboard",
                "quantity_ordered": 1,
                "quantity_available": 10,
                "quantity_deducted": 0,
                "quantity_shipped": 0,
                "unit_price": 99.0,
                "is_discontinued": False,
                "stock_status": "PENDING_CHECK",
                "deduction_status": "NOT_DEDUCTED",
                "shipping_status": "UNSHIPPED",
                "item_metadata": {},
            }
        ],
        "eligible_items": [],
        "ineligible_items": [],
        "shipping_address": {"city": "Austin", "state": "TX", "postal_code": "78701"},
        "billing_address": {"city": "Austin", "state": "TX", "postal_code": "78701"},
        "carrier_name": None,
        "tracking_number": None,
        "llm_comments": [],
        "llm_summary_report": None,
        "email_sent": False,
        "stage_history": [],
        "logs": [],
        "error": None,
    }

    # 3. Invoke Graph
    config = {"configurable": {"thread_id": order_id}}
    try:
        final_state = graph.invoke(initial_state, config=config)

        # 4. Print Summary
        print("\n" + "=" * 70)
        print("Orchestration Finished Successfully!")
        print("=" * 70)
        print(f"Final Order ID:      {final_state.get('order_id')}")
        print(f"Final Stage:         {final_state.get('current_stage')}")
        print(f"Final Status:        {final_state.get('status')}")
        print(f"Fulfillment Type:    {final_state.get('fulfillment_type')}")
        print(f"Tracking Number:     {final_state.get('tracking_number')}")
        if final_state.get("human_review_reason"):
            print(f"Human Review Reason: {final_state.get('human_review_reason')}")

        print(f"Stage History:       {' -> '.join(final_state.get('stage_history', []))}")
        print("\nLogs Produced Across Nodes:")
        for log_msg in final_state.get("logs", []):
            print(f"  • {log_msg}")

        if final_state.get("llm_comments"):
            print("\nLLM Operations Briefings / Commentary:")
            for comment in final_state.get("llm_comments", []):
                print(f"{comment}\n")

        if final_state.get("llm_summary_report") and final_state.get("llm_summary_report") not in final_state.get("llm_comments", []):
            print("\nLLM Final Executive Summary Report:")
            print(f"{final_state.get('llm_summary_report')}\n")

        print("=" * 70)
    finally:
        from src.orchestrator.db.session import close_connection_pool
        close_connection_pool()


if __name__ == "__main__":
    order_id_arg = sys.argv[1] if len(sys.argv) > 1 else "ORD-DEMO-001"
    run_e2e_orchestration(order_id_arg)
