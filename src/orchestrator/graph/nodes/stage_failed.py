"""Stage Failure Node for error capture and graceful state termination."""

from typing import Any, Dict
from src.orchestrator.graph.nodes.base import stage_tracker
from src.orchestrator.db.session import update_workflow_stage
from src.orchestrator.schema.state import OrchestratorState, WorkflowStage, WorkflowStatus


@stage_tracker(WorkflowStage.FAILED.value)
def failed_node(state: OrchestratorState) -> Dict[str, Any]:
    """
    Terminates execution gracefully when an unrecoverable failure or rejection happens.
    Persists error details to PostgreSQL.
    """
    thread_id = state.get("thread_id", "")
    run_id = state.get("run_id", "")
    stage_version = state.get("stage_version", 1)
    error = state.get("error", "Unknown workflow error")

    # Update database status to FAILED
    try:
        if run_id:
            update_workflow_stage(
                thread_id=thread_id,
                current_stage=WorkflowStage.FAILED.value,
                status=WorkflowStatus.FAILED.value,
                stage_version=stage_version,
                error_message=error,
            )
    except Exception:
        pass

    return {
        "output_payload": {"failure_reason": error},
    }
