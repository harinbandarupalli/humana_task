"""Workflow orchestration execution service."""

import uuid
from typing import Any, Dict, Optional
from src.orchestrator.core.logging import logger
from src.orchestrator.db.checkpointer import get_checkpointer
from src.orchestrator.db.session import (
    create_workflow_run,
    get_workflow_run_by_thread,
    update_workflow_stage,
)
from src.orchestrator.graph.builder import build_orchestrator_graph
from src.orchestrator.schema.models import WorkflowStartResponse, WorkflowStateResponse
from src.orchestrator.schema.state import OrchestratorState, WorkflowStage, WorkflowStatus


class WorkflowService:
    """Manages workflow invocations, resumption, and database synchronizations."""

    @staticmethod
    def start_workflow(
        workflow_name: str,
        input_payload: Dict[str, Any],
        thread_id: Optional[str] = None,
    ) -> WorkflowStartResponse:
        """Starts a new workflow execution run."""
        thread_id = thread_id or f"thread_{uuid.uuid4().hex[:12]}"
        run_id = str(uuid.uuid4())

        logger.info(f"Starting workflow '{workflow_name}' with thread_id={thread_id}")

        # 1. Create DB record in workflow_runs (if DB is configured)
        try:
            db_run = create_workflow_run(
                thread_id=thread_id,
                workflow_name=workflow_name,
                initial_stage=WorkflowStage.INIT.value,
                input_payload=input_payload,
            )
            run_id = str(db_run.get("id", run_id))
        except Exception as e:
            logger.warning(f"Could not persist workflow_runs DB record: {e}")

        # 2. Prepare initial state
        initial_state: OrchestratorState = {
            "thread_id": thread_id,
            "run_id": run_id,
            "workflow_name": workflow_name,
            "current_stage": WorkflowStage.INIT.value,
            "stage_version": 1,
            "input_payload": input_payload,
            "output_payload": {},
            "stage_history": [WorkflowStage.INIT.value],
            "logs": ["Workflow initialized."],
            "requires_approval": False,
            "is_approved": None,
            "error": None,
        }

        # 3. Execute graph with Postgres Checkpointer
        with get_checkpointer() as checkpointer:
            graph = build_orchestrator_graph(checkpointer=checkpointer)
            config = {"configurable": {"thread_id": thread_id}}

            # Run graph until completion or interrupt
            output_state = graph.invoke(initial_state, config=config)

            # Check if interrupted (e.g., waiting for human review)
            next_nodes = graph.get_state(config).next
            is_paused = bool(next_nodes)

            status = WorkflowStatus.WAITING_APPROVAL if is_paused else (
                WorkflowStatus.FAILED if output_state.get("error") else WorkflowStatus.COMPLETED
            )
            current_stage = output_state.get("current_stage", WorkflowStage.INIT.value)

            # Update DB with final / paused status
            try:
                update_workflow_stage(
                    thread_id=thread_id,
                    current_stage=current_stage,
                    status=status.value,
                    stage_version=output_state.get("stage_version", 1),
                    output_payload=output_state.get("output_payload"),
                    error_message=output_state.get("error"),
                )
            except Exception:
                pass

            msg = "Workflow paused for approval." if is_paused else "Workflow executed successfully."
            return WorkflowStartResponse(
                run_id=run_id,
                thread_id=thread_id,
                workflow_name=workflow_name,
                status=status,
                current_stage=current_stage,
                message=msg,
            )

    @staticmethod
    def resume_workflow(
        thread_id: str,
        is_approved: bool,
        feedback: Optional[str] = None,
    ) -> WorkflowStartResponse:
        """Resumes an interrupted workflow with human decision input."""
        logger.info(f"Resuming workflow thread_id={thread_id} with approval={is_approved}")

        with get_checkpointer() as checkpointer:
            graph = build_orchestrator_graph(checkpointer=checkpointer)
            config = {"configurable": {"thread_id": thread_id}}

            # Update state with approval payload
            graph.update_state(
                config,
                {
                    "is_approved": is_approved,
                    "logs": [f"Human review submitted: approved={is_approved}, feedback={feedback}"],
                },
            )

            # Resume execution
            output_state = graph.invoke(None, config=config)

            next_nodes = graph.get_state(config).next
            is_paused = bool(next_nodes)

            status = WorkflowStatus.WAITING_APPROVAL if is_paused else (
                WorkflowStatus.FAILED if output_state.get("error") else WorkflowStatus.COMPLETED
            )
            current_stage = output_state.get("current_stage", "UNKNOWN")

            return WorkflowStartResponse(
                run_id=output_state.get("run_id", ""),
                thread_id=thread_id,
                workflow_name=output_state.get("workflow_name", "resumed_workflow"),
                status=status,
                current_stage=current_stage,
                message="Workflow resumed and finished execution.",
            )

    @staticmethod
    def get_workflow_state(thread_id: str) -> WorkflowStateResponse:
        """Fetches the latest checkpoint snapshot for a workflow thread."""
        with get_checkpointer() as checkpointer:
            graph = build_orchestrator_graph(checkpointer=checkpointer)
            config = {"configurable": {"thread_id": thread_id}}
            state_snapshot = graph.get_state(config)

            if not state_snapshot or not state_snapshot.values:
                # Fallback to DB record if checkpoint cache not yet populated
                db_record = get_workflow_run_by_thread(thread_id)
                if not db_record:
                    raise ValueError(f"No workflow found with thread_id: {thread_id}")

                return WorkflowStateResponse(
                    run_id=str(db_record["id"]),
                    thread_id=thread_id,
                    workflow_name=db_record["workflow_name"],
                    status=WorkflowStatus(db_record["status"]),
                    current_stage=db_record["current_stage"],
                    stage_version=db_record["stage_version"],
                    stage_history=[db_record["current_stage"]],
                    input_payload=db_record["input_payload"] or {},
                    output_payload=db_record["output_payload"] or {},
                    logs=[],
                    error=db_record.get("error_message"),
                    checkpoint_id=None,
                )

            values = state_snapshot.values
            db_record = get_workflow_run_by_thread(thread_id)
            checkpoint_id = state_snapshot.config.get("configurable", {}).get("checkpoint_id")

            status = WorkflowStatus.WAITING_APPROVAL if state_snapshot.next else (
                WorkflowStatus.FAILED if values.get("error") else WorkflowStatus.COMPLETED
            )

            return WorkflowStateResponse(
                run_id=str(db_record["id"]) if db_record else values.get("run_id"),
                thread_id=thread_id,
                workflow_name=values.get("workflow_name", "unknown"),
                status=status,
                current_stage=values.get("current_stage", "UNKNOWN"),
                stage_version=values.get("stage_version", 1),
                stage_history=values.get("stage_history", []),
                input_payload=values.get("input_payload", {}),
                output_payload=values.get("output_payload", {}),
                logs=values.get("logs", []),
                error=values.get("error"),
                checkpoint_id=checkpoint_id,
            )
