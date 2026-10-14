"""Pydantic request and response schemas for REST API."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from src.orchestrator.schema.state import WorkflowStatus


class WorkflowStartRequest(BaseModel):
    """Payload to trigger a new orchestrated workflow."""
    workflow_name: str = Field(default="sample_pipeline", description="Name of the workflow")
    thread_id: Optional[str] = Field(default=None, description="Optional custom thread ID; generated if omitted")
    input_payload: Dict[str, Any] = Field(default_factory=dict, description="Input parameters for the workflow")


class WorkflowStartResponse(BaseModel):
    """Response returned immediately after initializing a workflow."""
    run_id: str
    thread_id: str
    workflow_name: str
    status: WorkflowStatus
    current_stage: str
    message: str


class WorkflowResumeRequest(BaseModel):
    """Payload to resume an interrupted workflow (e.g. human-in-the-loop)."""
    is_approved: bool = Field(..., description="Approval decision flag")
    feedback: Optional[str] = Field(default=None, description="Optional feedback or parameters")


class StageTransitionEvent(BaseModel):
    """Individual stage transition record."""
    stage_name: str
    from_stage: Optional[str]
    to_stage: Optional[str]
    stage_version: int
    event_type: str
    checkpoint_id: Optional[str]
    created_at: datetime


class WorkflowStateResponse(BaseModel):
    """Full state snapshot returned from PostgreSQL state store."""
    run_id: Optional[str]
    thread_id: str
    workflow_name: str
    status: WorkflowStatus
    current_stage: str
    stage_version: int
    stage_history: List[str]
    input_payload: Dict[str, Any]
    output_payload: Dict[str, Any]
    logs: List[str]
    error: Optional[str]
    checkpoint_id: Optional[str]
