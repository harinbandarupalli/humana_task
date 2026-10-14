-- ============================================================================
-- Migration: V7__ORD_107_create_order_inventory_transactions.sql
-- Ticket: ORD-107
-- Description: Inventory transaction ledger capturing deductions, reservations,
-- and rollback releases for complete auditability across dynamic graph loops.
-- ============================================================================

-- Sequence for inventory transaction ordering
CREATE SEQUENCE IF NOT EXISTS order_inventory_tx_seq INCREMENT BY 1 START WITH 1;

CREATE TABLE IF NOT EXISTS order_inventory_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tx_number BIGINT NOT NULL DEFAULT nextval('order_inventory_tx_seq'),
    order_id VARCHAR(64) NOT NULL REFERENCES order_orchestration_runs(order_id) ON DELETE CASCADE,
    product_id VARCHAR(64) NOT NULL,
    sku VARCHAR(64) NOT NULL,
    transaction_type VARCHAR(50) NOT NULL,
    quantity INT NOT NULL CHECK (quantity > 0),
    external_reference_id VARCHAR(128),
    status VARCHAR(50) NOT NULL,
    reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- Detailed Documentation & Comments
-- ============================================================================
COMMENT ON TABLE order_inventory_transactions IS 
'Immutable ledger tracking warehouse inventory deduction calls, reservations, and rollback releases.';

COMMENT ON COLUMN order_inventory_transactions.id IS 
'Surrogate UUID primary key.';

COMMENT ON COLUMN order_inventory_transactions.tx_number IS 
'Chronological sequence number driven by order_inventory_tx_seq.';

COMMENT ON COLUMN order_inventory_transactions.order_id IS 
'Foreign key referencing order_orchestration_runs(order_id) with cascading deletion.';

COMMENT ON COLUMN order_inventory_transactions.product_id IS 
'Catalog product identifier for which inventory was modified.';

COMMENT ON COLUMN order_inventory_transactions.sku IS 
'Stock Keeping Unit code.';

COMMENT ON COLUMN order_inventory_transactions.transaction_type IS 
'Type of inventory action: DEDUCTION or ROLLBACK_RELEASE.';

COMMENT ON COLUMN order_inventory_transactions.quantity IS 
'Number of units affected by this transaction; must be greater than zero.';

COMMENT ON COLUMN order_inventory_transactions.external_reference_id IS 
'Transaction or confirmation ID returned by the external Inventory Management System.';

COMMENT ON COLUMN order_inventory_transactions.status IS 
'Transaction outcome: SUCCESS or FAILED.';

COMMENT ON COLUMN order_inventory_transactions.reason IS 
'Failure diagnosis or operational note (e.g. Insufficient warehouse stock on reservation).';

COMMENT ON COLUMN order_inventory_transactions.created_at IS 
'Timestamp when the inventory transaction occurred.';

-- ============================================================================
-- Indexes
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_inv_tx_order_id 
    ON order_inventory_transactions (order_id);

CREATE INDEX IF NOT EXISTS idx_inv_tx_product_id 
    ON order_inventory_transactions (product_id);

CREATE INDEX IF NOT EXISTS idx_inv_tx_sku 
    ON order_inventory_transactions (sku);

CREATE INDEX IF NOT EXISTS idx_inv_tx_status 
    ON order_inventory_transactions (status);

CREATE INDEX IF NOT EXISTS idx_inv_tx_created_at 
    ON order_inventory_transactions (created_at);
