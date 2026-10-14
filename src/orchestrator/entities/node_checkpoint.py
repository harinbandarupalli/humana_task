"""Domain entity for node execution checkpoints."""

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID
from pydantic import Field
from src.orchestrator.entities.base import BaseEntity


class NodeExecutionCheckpoint(BaseEntity):
    """
    Domain entity mapping to `node_execution_checkpoints` table.
    Captures state snapshots, metrics, LLM reasoning, and errors after node execution.
    """

    id: Optional[UUID] = Field(default=None, description="Surrogate primary key UUID")
    sequence_number: Optional[int] = Field(default=None, description="Global chronological sequence number")
    order_id: str = Field(..., description="Foreign key to order_orchestration_runs(order_id)")
    node_name: str = Field(..., description="Executing LangGraph node name")
    stage_version: int = Field(default=1, description="Version counter at execution time")
    execution_status: str = Field(..., description="STARTED, COMPLETED, FAILED, ROLLBACK_TRIGGERED")
    node_input: Dict[str, Any] = Field(default_factory=dict, description="State input snapshot")
    node_output_metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata and output metrics")
    llm_generated_comment: Optional[str] = Field(default=None, description="Natural language reasoning from LLM")
    duration_ms: Optional[int] = Field(default=None, description="Node runtime latency in milliseconds")
    error_message: Optional[str] = Field(default=None, description="Error message if failed")
    stack_trace: Optional[str] = Field(default=None, description="Exception stack trace")
    created_at: Optional[datetime] = Field(default=None, description="Checkpoint timestamp")
