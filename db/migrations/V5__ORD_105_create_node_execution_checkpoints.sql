-- ============================================================================
-- Migration: V5__ORD_105_create_node_execution_checkpoints.sql
-- Ticket: ORD-105
-- Description: Post-node execution metadata store capturing state snapshots,
-- LLM generated commentary, execution latencies, and error stack traces.
-- ============================================================================

-- Sequence for global ordering of node checkpoint events
CREATE SEQUENCE IF NOT EXISTS node_execution_checkpoint_seq INCREMENT BY 1 START WITH 1;

CREATE TABLE IF NOT EXISTS node_execution_checkpoints (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sequence_number BIGINT NOT NULL DEFAULT nextval('node_execution_checkpoint_seq'),
    order_id VARCHAR(64) NOT NULL REFERENCES order_orchestration_runs(order_id) ON DELETE CASCADE,
    node_name VARCHAR(100) NOT NULL,
    stage_version INT NOT NULL,
    execution_status VARCHAR(50) NOT NULL,
    node_input JSONB NOT NULL DEFAULT '{}',
    node_output_metadata JSONB NOT NULL DEFAULT '{}',
    llm_generated_comment TEXT,
    duration_ms INT,
    error_message TEXT,
    stack_trace TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- Detailed Documentation & Comments
-- ============================================================================
COMMENT ON TABLE node_execution_checkpoints IS 
'Stores structured audit metadata, LLM comments, execution durations, and output snapshots after each LangGraph node.';

COMMENT ON COLUMN node_execution_checkpoints.id IS 
'Surrogate UUID primary key.';

COMMENT ON COLUMN node_execution_checkpoints.sequence_number IS 
'Global chronological sequence counter driven by node_execution_checkpoint_seq.';

COMMENT ON COLUMN node_execution_checkpoints.order_id IS 
'Reference to order_orchestration_runs(order_id) with cascade delete.';

COMMENT ON COLUMN node_execution_checkpoints.node_name IS 
'Name of the executing LangGraph node (e.g. order_ingest, inventory_check, notification_review).';

COMMENT ON COLUMN node_execution_checkpoints.stage_version IS 
'Version counter at the time of node execution, enabling tracking across dynamic retry loops.';

COMMENT ON COLUMN node_execution_checkpoints.execution_status IS 
'Outcome of the node execution: STARTED, COMPLETED, FAILED, ROLLBACK_TRIGGERED.';

COMMENT ON COLUMN node_execution_checkpoints.node_input IS 
'JSONB snapshot of state variables consumed as input by this node.';

COMMENT ON COLUMN node_execution_checkpoints.node_output_metadata IS 
'JSONB payload holding extra metadata, inventory balances, API response payloads, and operational flags.';

COMMENT ON COLUMN node_execution_checkpoints.llm_generated_comment IS 
'Text comments produced by LLM for human comprehension (ops review or customer notifications).';

COMMENT ON COLUMN node_execution_checkpoints.duration_ms IS 
'Node execution latency in milliseconds for performance profiling.';

COMMENT ON COLUMN node_execution_checkpoints.error_message IS 
'High-level error summary if the node failed.';

COMMENT ON COLUMN node_execution_checkpoints.stack_trace IS 
'Detailed stack trace captured when an unhandled exception occurred in the node.';

COMMENT ON COLUMN node_execution_checkpoints.created_at IS 
'Timestamp when checkpoint record was logged.';

-- ============================================================================
-- Indexes
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_node_checkpoints_order_id 
    ON node_execution_checkpoints (order_id);

CREATE INDEX IF NOT EXISTS idx_node_checkpoints_node_name 
    ON node_execution_checkpoints (node_name);

CREATE INDEX IF NOT EXISTS idx_node_checkpoints_created_at 
    ON node_execution_checkpoints (created_at);

CREATE INDEX IF NOT EXISTS idx_node_checkpoints_status 
    ON node_execution_checkpoints (execution_status);
