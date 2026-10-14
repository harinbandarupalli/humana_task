"""Workflow management and execution endpoints."""

from fastapi import APIRouter, HTTPException
from src.orchestrator.schema.models import (
    WorkflowResumeRequest,
    WorkflowStartRequest,
    WorkflowStartResponse,
    WorkflowStateResponse,
)
from src.orchestrator.services.workflow_service import WorkflowService

router = APIRouter(prefix="/api/v1/workflows", tags=["Workflows"])


@router.post("/start", response_model=WorkflowStartResponse)
def start_workflow(request: WorkflowStartRequest):
    """
    Starts a new orchestrated LangGraph workflow.
    State is persisted to PostgreSQL checkpoints at every stage transition.
    """
    try:
        return WorkflowService.start_workflow(
            workflow_name=request.workflow_name,
            input_payload=request.input_payload,
            thread_id=request.thread_id,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start workflow: {e}")


@router.get("/{thread_id}/state", response_model=WorkflowStateResponse)
def get_workflow_state(thread_id: str):
    """
    Fetches the current state snapshot and stage progress for a given thread ID.
    """
    try:
        return WorkflowService.get_workflow_state(thread_id=thread_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve workflow state: {e}")


@router.post("/{thread_id}/resume", response_model=WorkflowStartResponse)
def resume_workflow(thread_id: str, request: WorkflowResumeRequest):
    """
    Resumes an interrupted workflow at an approval gate stage.
    """
    try:
        return WorkflowService.resume_workflow(
            thread_id=thread_id,
            is_approved=request.is_approved,
            feedback=request.feedback,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to resume workflow: {e}")
