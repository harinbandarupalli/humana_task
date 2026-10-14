"""Stage 1: Input Ingestion and Validation Node."""

from typing import Any, Dict
from src.orchestrator.graph.nodes.base import stage_tracker
from src.orchestrator.schema.state import OrchestratorState, WorkflowStage


@stage_tracker(WorkflowStage.INGESTION.value)
def ingest_node(state: OrchestratorState) -> Dict[str, Any]:
    """
    Validates the input payload, normalizes parameters, and initializes execution state.
    """
    input_payload = state.get("input_payload", {})

    # Example placeholder validation:
    if not isinstance(input_payload, dict):
        raise ValueError("Invalid input payload format; expected dictionary.")

    # Determine whether downstream human review is required based on input flags
    requires_approval = bool(input_payload.get("require_review", False))

    normalized_data = {
        **input_payload,
        "ingested_at": "now",
        "validation_passed": True,
    }

    return {
        "input_payload": normalized_data,
        "requires_approval": requires_approval,
        "output_payload": {"initial_status": "ingested"},
    }
