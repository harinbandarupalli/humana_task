"""Stage 3 (Conditional): Human-in-the-Loop Review Node."""

from typing import Any, Dict
from src.orchestrator.graph.nodes.base import stage_tracker
from src.orchestrator.schema.state import OrchestratorState, WorkflowStage


@stage_tracker(WorkflowStage.APPROVAL_REQUIRED.value)
def human_review_node(state: OrchestratorState) -> Dict[str, Any]:
    """
    Approval gate. In an interrupted workflow, execution pauses prior to or inside
    this node until an external approval payload is provided.
    """
    is_approved = state.get("is_approved")

    if is_approved is False:
        return {
            "error": "Workflow rejected during human review stage.",
            "output_payload": {
                **state.get("output_payload", {}),
                "approval_status": "REJECTED",
            },
        }

    return {
        "output_payload": {
            **state.get("output_payload", {}),
            "approval_status": "APPROVED",
        }
    }
