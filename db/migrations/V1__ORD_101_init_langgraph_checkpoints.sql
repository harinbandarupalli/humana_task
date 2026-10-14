-- ============================================================================
-- Migration: V1__ORD_101_init_langgraph_checkpoints.sql
-- Ticket: ORD-101
-- Description: Core schema for LangGraph PostgreSQL state checkpointing.
-- Compatible with: langgraph-checkpoint-postgres (v2.x)
-- ============================================================================

-- 1. Checkpoint Migrations tracking table (used by LangGraph internal checkpointer)
CREATE TABLE IF NOT EXISTS checkpoint_migrations (
    v INTEGER PRIMARY KEY
);

COMMENT ON TABLE checkpoint_migrations IS 
'Internal ledger used by LangGraph checkpointer library to track applied internal migration versions.';

COMMENT ON COLUMN checkpoint_migrations.v IS 
'Monotonically increasing version integer of the internal LangGraph checkpoint schema.';

-- Seed internal migration version 1 to maintain compatibility with checkpointer.setup()
INSERT INTO checkpoint_migrations (v) VALUES (1) ON CONFLICT DO NOTHING;

-- 2. Core Checkpoints Table
-- Stores state snapshots, thread identifiers, metadata, and parent checkpoint graph links
CREATE TABLE IF NOT EXISTS checkpoints (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    checkpoint_id TEXT NOT NULL,
    parent_checkpoint_id TEXT,
    type TEXT,
    checkpoint JSONB NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}',
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
);

COMMENT ON TABLE checkpoints IS 
'Stores serialized LangGraph state graph snapshots for each thread, checkpoint step, and namespace.';

COMMENT ON COLUMN checkpoints.thread_id IS 
'Unique identifier for the execution thread; in this system, thread_id maps directly to the order_id.';

COMMENT ON COLUMN checkpoints.checkpoint_ns IS 
'Namespace for the checkpoint, supporting subgraph executions and isolated task scopes.';

COMMENT ON COLUMN checkpoints.checkpoint_id IS 
'Unique checkpoint identifier for this specific snapshot in time.';

COMMENT ON COLUMN checkpoints.parent_checkpoint_id IS 
'Pointer to the predecessor checkpoint ID to form an execution lineage DAG.';

COMMENT ON COLUMN checkpoints.type IS 
'Serialization format type descriptor (e.g., json, msgpack).';

COMMENT ON COLUMN checkpoints.checkpoint IS 
'The complete serialized state graph channels and values snapshot.';

COMMENT ON COLUMN checkpoints.metadata IS 
'Arbitrary runtime metadata associated with this checkpoint step (e.g., step number, node name).';

CREATE INDEX IF NOT EXISTS idx_checkpoints_thread_id 
    ON checkpoints (thread_id);

CREATE INDEX IF NOT EXISTS idx_checkpoints_parent_id 
    ON checkpoints (thread_id, parent_checkpoint_id);

-- 3. Checkpoint Blobs Table
-- Stores serialized state payloads (channels, versions, binary blobs)
CREATE TABLE IF NOT EXISTS checkpoint_blobs (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    channel TEXT NOT NULL,
    version TEXT NOT NULL,
    type TEXT NOT NULL,
    blob BYTEA,
    PRIMARY KEY (thread_id, checkpoint_ns, channel, version)
);

COMMENT ON TABLE checkpoint_blobs IS 
'Stores serialized data blobs and channel states associated with checkpoints.';

COMMENT ON COLUMN checkpoint_blobs.thread_id IS 
'Thread identifier associated with this data blob.';

COMMENT ON COLUMN checkpoint_blobs.checkpoint_ns IS 
'Checkpoint namespace for isolation.';

COMMENT ON COLUMN checkpoint_blobs.channel IS 
'Channel name within the LangGraph state definition.';

COMMENT ON COLUMN checkpoint_blobs.version IS 
'Channel version identifier.';

COMMENT ON COLUMN checkpoint_blobs.type IS 
'Serialization type for the blob.';

COMMENT ON COLUMN checkpoint_blobs.blob IS 
'Binary payload or serialized data for this channel state.';

CREATE INDEX IF NOT EXISTS idx_checkpoint_blobs_thread_channel 
    ON checkpoint_blobs (thread_id, channel);

-- 4. Checkpoint Writes Table
-- Stores intermediate task writes, pending node outputs, and Human-in-the-loop pending inputs
CREATE TABLE IF NOT EXISTS checkpoint_writes (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    checkpoint_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    idx INTEGER NOT NULL,
    channel TEXT NOT NULL,
    type TEXT,
    blob BYTEA NOT NULL,
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
);

COMMENT ON TABLE checkpoint_writes IS 
'Stores pending or intermediate node writes, enabling fault tolerance and Human-in-the-loop interruptions.';

COMMENT ON COLUMN checkpoint_writes.thread_id IS 
'Thread identifier for the workflow execution.';

COMMENT ON COLUMN checkpoint_writes.checkpoint_ns IS 
'Checkpoint namespace.';

COMMENT ON COLUMN checkpoint_writes.checkpoint_id IS 
'Reference to the checkpoint for which this write was produced.';

COMMENT ON COLUMN checkpoint_writes.task_id IS 
'Unique task execution identifier inside LangGraph.';

COMMENT ON COLUMN checkpoint_writes.idx IS 
'Order index for writes produced by the same task.';

COMMENT ON COLUMN checkpoint_writes.channel IS 
'State channel to which this write applies.';

COMMENT ON COLUMN checkpoint_writes.type IS 
'Data serialization type.';

COMMENT ON COLUMN checkpoint_writes.blob IS 
'Serialized write payload.';

CREATE INDEX IF NOT EXISTS idx_checkpoint_writes_thread_checkpoint 
    ON checkpoint_writes (thread_id, checkpoint_id);
