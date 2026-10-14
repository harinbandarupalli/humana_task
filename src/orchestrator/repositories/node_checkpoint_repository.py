"""Dedicated repository for node_execution_checkpoints table."""

import json
from typing import Any, Dict, List, Optional
import psycopg
from src.orchestrator.entities.node_checkpoint import NodeExecutionCheckpoint
from src.orchestrator.repositories.base import BaseRepository


class NodeCheckpointRepository(BaseRepository):
    """Data access repository for node_execution_checkpoints."""

    def __init__(self, conn: Optional[psycopg.Connection] = None):
        super().__init__(conn)

    @staticmethod
    def _from_row(row: Dict[str, Any]) -> NodeExecutionCheckpoint:
        """Converts database row dictionary to NodeExecutionCheckpoint entity."""
        return NodeExecutionCheckpoint.model_validate(dict(row))

    def record_checkpoint(self, checkpoint: NodeExecutionCheckpoint) -> NodeExecutionCheckpoint:
        """Inserts a structured checkpoint record after a node completes or fails."""
        query = """
            INSERT INTO node_execution_checkpoints (
                order_id, node_name, stage_version, execution_status,
                node_input, node_output_metadata, llm_generated_comment,
                duration_ms, error_message, stack_trace
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s
            )
            RETURNING *;
        """
        params = (
            checkpoint.order_id,
            checkpoint.node_name,
            checkpoint.stage_version,
            checkpoint.execution_status,
            json.dumps(checkpoint.node_input),
            json.dumps(checkpoint.node_output_metadata),
            checkpoint.llm_generated_comment,
            checkpoint.duration_ms,
            checkpoint.error_message,
            checkpoint.stack_trace,
        )

        with self.get_connection() as conn:
            row = conn.execute(query, params).fetchone()
            return self._from_row(row)

    def get_latest_checkpoint(self, order_id: str) -> Optional[NodeExecutionCheckpoint]:
        """Retrieves the most recent node execution checkpoint for an order."""
        query = """
            SELECT * FROM node_execution_checkpoints
            WHERE order_id = %s
            ORDER BY sequence_number DESC
            LIMIT 1;
        """
        with self.get_connection() as conn:
            row = conn.execute(query, (order_id,)).fetchone()
            return self._from_row(row) if row else None

    def get_checkpoints_for_order(self, order_id: str) -> List[NodeExecutionCheckpoint]:
        """Retrieves the complete chronological history of node checkpoints for an order."""
        query = """
            SELECT * FROM node_execution_checkpoints
            WHERE order_id = %s
            ORDER BY sequence_number ASC;
        """
        with self.get_connection() as conn:
            rows = conn.execute(query, (order_id,)).fetchall()
            return [self._from_row(row) for row in rows]

    def get_error_checkpoints(self, order_id: str) -> List[NodeExecutionCheckpoint]:
        """Retrieves only checkpoints where execution_status is FAILED."""
        query = """
            SELECT * FROM node_execution_checkpoints
            WHERE order_id = %s AND execution_status = 'FAILED'
            ORDER BY sequence_number ASC;
        """
        with self.get_connection() as conn:
            rows = conn.execute(query, (order_id,)).fetchall()
            return [self._from_row(row) for row in rows]
