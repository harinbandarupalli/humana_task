-- ============================================================================
-- Migration: V3__ORD_103_create_order_orchestration_runs.sql
-- Ticket: ORD-103
-- Description: Master order workflow catalog and state tracking table.
-- Links external Order IDs to LangGraph threads with comprehensive indexing.
-- ============================================================================

CREATE TABLE IF NOT EXISTS order_orchestration_runs (
    order_id VARCHAR(64) PRIMARY KEY,
    thread_id VARCHAR(128) NOT NULL UNIQUE,
    user_id VARCHAR(64) NOT NULL,
    customer_email VARCHAR(255) NOT NULL,
    customer_phone VARCHAR(50),
    order_placed_at TIMESTAMPTZ NOT NULL,
    order_type VARCHAR(50) NOT NULL DEFAULT 'STANDARD',
    payment_status VARCHAR(50) NOT NULL DEFAULT 'PENDING' REFERENCES payment_status_lookup(code),
    current_stage VARCHAR(50) NOT NULL DEFAULT 'INGESTION' REFERENCES workflow_stage_lookup(code),
    status VARCHAR(50) NOT NULL DEFAULT 'PENDING' REFERENCES order_status_lookup(code),
    fulfillment_type VARCHAR(50) NOT NULL DEFAULT 'NONE' REFERENCES fulfillment_type_lookup(code),
    human_in_loop BOOLEAN NOT NULL DEFAULT FALSE,
    human_review_reason TEXT,
    is_duplicate BOOLEAN NOT NULL DEFAULT FALSE,
    deduction_completed BOOLEAN NOT NULL DEFAULT FALSE,
    shipping_completed BOOLEAN NOT NULL DEFAULT FALSE,
    currency VARCHAR(10) NOT NULL DEFAULT 'USD',
    total_amount NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    shipping_address JSONB NOT NULL DEFAULT '{}',
    billing_address JSONB NOT NULL DEFAULT '{}',
    carrier_name VARCHAR(64),
    tracking_number VARCHAR(128),
    llm_summary_report TEXT,
    stage_version INT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- Detailed Documentation & Comments
-- ============================================================================
COMMENT ON TABLE order_orchestration_runs IS 
'Master order fulfillment workflow catalog, orchestrating the state lifecycle across LangGraph nodes.';

COMMENT ON COLUMN order_orchestration_runs.order_id IS 
'Unique business identifier for the order from ORDER API; serves as the primary key.';

COMMENT ON COLUMN order_orchestration_runs.thread_id IS 
'Unique execution thread identifier in LangGraph; enables thread-level state recovery and checkpointing.';

COMMENT ON COLUMN order_orchestration_runs.user_id IS 
'Customer account identifier who placed the order; indexed for customer history queries.';

COMMENT ON COLUMN order_orchestration_runs.customer_email IS 
'Customer contact email address; indexed for communication, search, and notification auditing.';

COMMENT ON COLUMN order_orchestration_runs.customer_phone IS 
'Customer telephone contact; indexed for support and SMS/carrier routing lookups.';

COMMENT ON COLUMN order_orchestration_runs.order_placed_at IS 
'Timestamp when customer submitted order on e-commerce storefront.';

COMMENT ON COLUMN order_orchestration_runs.order_type IS 
'Order category (e.g. STANDARD, PRE_ORDER, SUBSCRIPTION, EXPRESS).';

COMMENT ON COLUMN order_orchestration_runs.payment_status IS 
'Financial settlement verification status referencing payment_status_lookup(code). Must be SUCCESS to ship.';

COMMENT ON COLUMN order_orchestration_runs.current_stage IS 
'Current execution node name referencing workflow_stage_lookup(code).';

COMMENT ON COLUMN order_orchestration_runs.status IS 
'Overall pipeline lifecycle status referencing order_status_lookup(code).';

COMMENT ON COLUMN order_orchestration_runs.fulfillment_type IS 
'Fulfillment classification referencing fulfillment_type_lookup(code) (NONE, FULL, PARTIAL).';

COMMENT ON COLUMN order_orchestration_runs.human_in_loop IS 
'Flag indicating human operator intervention is required (e.g. address errors, partial shipments).';

COMMENT ON COLUMN order_orchestration_runs.human_review_reason IS 
'Detailed explanation or LLM generated reason describing why operator review was flagged.';

COMMENT ON COLUMN order_orchestration_runs.is_duplicate IS 
'Flag set to true if this order was identified as a re-submission of an existing run.';

COMMENT ON COLUMN order_orchestration_runs.deduction_completed IS 
'True if physical inventory deduction has completed for all eligible items.';

COMMENT ON COLUMN order_orchestration_runs.shipping_completed IS 
'True if shipping carrier API call succeeded and tracking number was generated.';

COMMENT ON COLUMN order_orchestration_runs.currency IS 
'Three-letter ISO currency code (e.g., USD, EUR).';

COMMENT ON COLUMN order_orchestration_runs.total_amount IS 
'Total monetary transaction amount.';

COMMENT ON COLUMN order_orchestration_runs.shipping_address IS 
'JSONB payload containing street, unit, city, state, postal_code, country, and validation flags.';

COMMENT ON COLUMN order_orchestration_runs.billing_address IS 
'JSONB payload containing customer billing address.';

COMMENT ON COLUMN order_orchestration_runs.carrier_name IS 
'Shipping carrier provider (e.g. FedEx, UPS, DHL, USPS).';

COMMENT ON COLUMN order_orchestration_runs.tracking_number IS 
'Waybill or carrier tracking identifier.';

COMMENT ON COLUMN order_orchestration_runs.llm_summary_report IS 
'Comprehensive natural language narrative generated by LLM summarizing fulfillment details and next actions.';

COMMENT ON COLUMN order_orchestration_runs.stage_version IS 
'Monotonically increasing version number incremented upon every stage progression.';

COMMENT ON COLUMN order_orchestration_runs.created_at IS 
'Timestamp when workflow orchestration record was initialized.';

COMMENT ON COLUMN order_orchestration_runs.updated_at IS 
'Timestamp of last modification, maintained automatically via trigger.';

-- ============================================================================
-- Explicit Indexing Strategy
-- ============================================================================

-- Critical user & contact indexes requested for rapid support and analytics queries
CREATE INDEX IF NOT EXISTS idx_order_runs_user_id 
    ON order_orchestration_runs (user_id);

CREATE INDEX IF NOT EXISTS idx_order_runs_customer_email 
    ON order_orchestration_runs (customer_email);

CREATE INDEX IF NOT EXISTS idx_order_runs_customer_phone 
    ON order_orchestration_runs (customer_phone);

-- Workflow lifecycle & queue filtering indexes
CREATE INDEX IF NOT EXISTS idx_order_runs_status 
    ON order_orchestration_runs (status);

CREATE INDEX IF NOT EXISTS idx_order_runs_current_stage 
    ON order_orchestration_runs (current_stage);

CREATE INDEX IF NOT EXISTS idx_order_runs_placed_at 
    ON order_orchestration_runs (order_placed_at);

-- Partial index for fast operational dashboard queries for human-in-the-loop review
CREATE INDEX IF NOT EXISTS idx_order_runs_human_in_loop 
    ON order_orchestration_runs (human_in_loop) 
    WHERE human_in_loop = TRUE;

-- ============================================================================
-- Trigger for automatic updated_at timestamp maintenance
-- ============================================================================
CREATE OR REPLACE FUNCTION update_order_runs_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_order_runs_updated_at ON order_orchestration_runs;

CREATE TRIGGER trigger_order_runs_updated_at
    BEFORE UPDATE ON order_orchestration_runs
    FOR EACH ROW
    EXECUTE FUNCTION update_order_runs_updated_at();
