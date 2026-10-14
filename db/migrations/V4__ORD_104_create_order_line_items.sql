-- ============================================================================
-- Migration: V4__ORD_104_create_order_line_items.sql
-- Ticket: ORD-104
-- Description: Line item level tracking of inventory balance, deduction state,
-- discontinued flags, and individual shipping fulfillment.
-- ============================================================================

-- Sequence for sequential line item numbering
CREATE SEQUENCE IF NOT EXISTS order_line_item_seq INCREMENT BY 1 START WITH 1;

CREATE TABLE IF NOT EXISTS order_line_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    line_number INT NOT NULL DEFAULT nextval('order_line_item_seq'),
    order_id VARCHAR(64) NOT NULL REFERENCES order_orchestration_runs(order_id) ON DELETE CASCADE,
    item_id VARCHAR(64) NOT NULL,
    product_id VARCHAR(64) NOT NULL,
    sku VARCHAR(64) NOT NULL,
    product_name VARCHAR(255) NOT NULL,
    quantity_ordered INT NOT NULL CHECK (quantity_ordered > 0),
    quantity_available INT NOT NULL DEFAULT 0,
    quantity_deducted INT NOT NULL DEFAULT 0,
    quantity_shipped INT NOT NULL DEFAULT 0,
    unit_price NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    is_discontinued BOOLEAN NOT NULL DEFAULT FALSE,
    stock_status VARCHAR(50) NOT NULL DEFAULT 'PENDING_CHECK' REFERENCES stock_status_lookup(code),
    deduction_status VARCHAR(50) NOT NULL DEFAULT 'NOT_DEDUCTED' REFERENCES deduction_status_lookup(code),
    shipping_status VARCHAR(50) NOT NULL DEFAULT 'UNSHIPPED',
    item_metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uk_order_line_item UNIQUE (order_id, item_id)
);

-- ============================================================================
-- Detailed Documentation & Comments
-- ============================================================================
COMMENT ON TABLE order_line_items IS 
'Stores individual line items under an order, capturing granular inventory checks, deduction state, and shipping completeness.';

COMMENT ON COLUMN order_line_items.id IS 
'Surrogate UUID primary key for line item record.';

COMMENT ON COLUMN order_line_items.line_number IS 
'Sequential line item number driven by order_line_item_seq.';

COMMENT ON COLUMN order_line_items.order_id IS 
'Foreign key referencing parent order_orchestration_runs(order_id) with cascading deletion.';

COMMENT ON COLUMN order_line_items.item_id IS 
'Line item business identifier returned by ORDER_DETAILS API.';

COMMENT ON COLUMN order_line_items.product_id IS 
'Product catalog identifier used for inventory queries and catalog updates.';

COMMENT ON COLUMN order_line_items.sku IS 
'Stock Keeping Unit code identifying physical warehouse product variation.';

COMMENT ON COLUMN order_line_items.product_name IS 
'Human-readable product title at the time of order placement.';

COMMENT ON COLUMN order_line_items.quantity_ordered IS 
'Count of items requested by the customer; must be greater than zero.';

COMMENT ON COLUMN order_line_items.quantity_available IS 
'Warehouse inventory count available when the inventory_check node executed.';

COMMENT ON COLUMN order_line_items.quantity_deducted IS 
'Count of items successfully reserved/deducted during the inventory_deduct node.';

COMMENT ON COLUMN order_line_items.quantity_shipped IS 
'Count of items included in the carrier shipping manifest.';

COMMENT ON COLUMN order_line_items.unit_price IS 
'Price charged per unit.';

COMMENT ON COLUMN order_line_items.is_discontinued IS 
'Boolean flag set when catalog indicates product has been permanently discontinued.';

COMMENT ON COLUMN order_line_items.stock_status IS 
'Current inventory availability category referencing stock_status_lookup(code).';

COMMENT ON COLUMN order_line_items.deduction_status IS 
'Status of inventory deduction referencing deduction_status_lookup(code).';

COMMENT ON COLUMN order_line_items.shipping_status IS 
'Fulfillment dispatch status for this line item (e.g. UNSHIPPED, SHIPPED, CANCELLED_UNAVAILABLE).';

COMMENT ON COLUMN order_line_items.item_metadata IS 
'JSONB payload holding warehouse bin location, tax codes, variant attributes, or discounts.';

COMMENT ON COLUMN order_line_items.created_at IS 
'Timestamp when item record was created.';

COMMENT ON COLUMN order_line_items.updated_at IS 
'Timestamp when item record was last updated.';

-- ============================================================================
-- Indexes
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_line_items_order_id 
    ON order_line_items (order_id);

CREATE INDEX IF NOT EXISTS idx_line_items_product_id 
    ON order_line_items (product_id);

CREATE INDEX IF NOT EXISTS idx_line_items_sku 
    ON order_line_items (sku);

CREATE INDEX IF NOT EXISTS idx_line_items_stock_status 
    ON order_line_items (stock_status);

CREATE INDEX IF NOT EXISTS idx_line_items_deduction_status 
    ON order_line_items (deduction_status);

-- ============================================================================
-- Trigger for automatic updated_at timestamp maintenance
-- ============================================================================
CREATE OR REPLACE FUNCTION update_order_line_items_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_order_line_items_updated_at ON order_line_items;

CREATE TRIGGER trigger_order_line_items_updated_at
    BEFORE UPDATE ON order_line_items
    FOR EACH ROW
    EXECUTE FUNCTION update_order_line_items_updated_at();
