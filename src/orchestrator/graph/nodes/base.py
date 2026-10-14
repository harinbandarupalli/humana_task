"""Base utilities and decorators for LangGraph workflow nodes."""

from functools import wraps
from typing import Any, Callable, Dict
from src.orchestrator.core.logging import logger
from src.orchestrator.db.session import record_stage_event, update_workflow_stage
from src.orchestrator.schema.state import OrchestratorState


def stage_tracker(stage_name: str):
    """
    Decorator to wrap LangGraph node functions.
    Automatically captures stage entry, versions, and persists stage transitions.
    """
    def decorator(func: Callable[[OrchestratorState], Dict[str, Any]]):
        @wraps(func)
        def wrapper(state: OrchestratorState) -> Dict[str, Any]:
            thread_id = state.get("thread_id", "unknown")
            run_id = state.get("run_id", "")
            current_stage = state.get("current_stage", "INIT")
            stage_version = state.get("stage_version", 1) + 1

            logger.info(f"[{thread_id}] Entering Stage '{stage_name}' (Version {stage_version})...")

            # Try to log stage transition event to PostgreSQL
            try:
                if run_id:
                    record_stage_event(
                        run_id=run_id,
                        thread_id=thread_id,
                        stage_name=stage_name,
                        from_stage=current_stage,
                        to_stage=stage_name,
                        stage_version=stage_version,
                        event_type="ENTER_STAGE",
                        state_snapshot={"stage": stage_name, "version": stage_version},
                    )
            except Exception as e:
                logger.warning(f"Could not write stage transition event to DB: {e}")

            # Execute node logic
            try:
                result = func(state)
                # Ensure stage metadata is updated
                result["current_stage"] = stage_name
                result["stage_version"] = stage_version
                result.setdefault("stage_history", [stage_name])
                result.setdefault("logs", [f"Stage {stage_name} (v{stage_version}) completed."])

                # Update DB run record
                try:
                    if run_id:
                        update_workflow_stage(
                            thread_id=thread_id,
                            current_stage=stage_name,
                            status="RUNNING",
                            stage_version=stage_version,
                        )
                except Exception as e:
                    logger.warning(f"Could not update workflow stage in DB: {e}")

                return result
            except Exception as e:
                logger.error(f"[{thread_id}] Error in stage {stage_name}: {e}")
                # Record error in DB
                try:
                    if run_id:
                        update_workflow_stage(
                            thread_id=thread_id,
                            current_stage=stage_name,
                            status="FAILED",
                            stage_version=stage_version,
                            error_message=str(e),
                        )
                except Exception:
                    pass
                raise

        return wrapper
    return decorator
