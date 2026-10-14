"""Stage 4: Completion Node and Final State Persistence."""

from typing import Any, Dict
from src.orchestrator.graph.nodes.base import stage_tracker
from src.orchestrator.db.session import update_workflow_stage
from src.orchestrator.schema.state import OrchestratorState, WorkflowStage, WorkflowStatus


@stage_tracker(WorkflowStage.COMPLETED.value)
def complete_node(state: OrchestratorState) -> Dict[str, Any]:
    """
    Finalizes execution, marks the run as COMPLETED in PostgreSQL,
    and consolidates output payloads.
    """
    thread_id = state.get("thread_id", "")
    run_id = state.get("run_id", "")
    output_payload = state.get("output_payload", {})
    stage_version = state.get("stage_version", 1)

    final_output = {
        **output_payload,
        "completed": True,
        "summary": "Workflow completed successfully across all stages.",
    }

    # Update database status to COMPLETED
    try:
        if run_id:
            update_workflow_stage(
                thread_id=thread_id,
                current_stage=WorkflowStage.COMPLETED.value,
                status=WorkflowStatus.COMPLETED.value,
                stage_version=stage_version,
                output_payload=final_output,
            )
    except Exception:
        pass

    return {
        "output_payload": final_output,
    }
