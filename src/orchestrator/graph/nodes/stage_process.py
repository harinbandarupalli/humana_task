"""Stage 2: Core Processing and Transformation Node."""

from typing import Any, Dict
from src.orchestrator.graph.nodes.base import stage_tracker
from src.orchestrator.schema.state import OrchestratorState, WorkflowStage


@stage_tracker(WorkflowStage.PROCESSING.value)
def process_node(state: OrchestratorState) -> Dict[str, Any]:
    """
    Core business logic / agent execution stage.
    Placeholder for LLM calls, data transformations, or external API orchestrations.
    """
    input_payload = state.get("input_payload", {})

    # Simulate processing transformation
    processed_items = input_payload.get("items", ["default_task"])
    transformed_results = [f"Processed: {item}" for item in processed_items]

    return {
        "output_payload": {
            "processed_results": transformed_results,
            "items_count": len(transformed_results),
            "status": "processed",
        }
    }
