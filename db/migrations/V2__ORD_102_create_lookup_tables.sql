-- ============================================================================
-- Migration: V2__ORD_102_create_lookup_tables.sql
-- Ticket: ORD-102
-- Description: Static lookup and code tables for order orchestrator states.
-- Provides sequence-driven sort orders, descriptions, and referential integrity.
-- ============================================================================

-- Sequence for lookup display sort order
CREATE SEQUENCE IF NOT EXISTS lookup_sort_order_seq INCREMENT BY 10 START WITH 10;

-- ----------------------------------------------------------------------------
-- 1. Order Status Lookup
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS order_status_lookup (
    code VARCHAR(50) PRIMARY KEY,
    display_name VARCHAR(100) NOT NULL,
    description TEXT,
    is_terminal BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order INT NOT NULL DEFAULT nextval('lookup_sort_order_seq'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE order_status_lookup IS 
'Reference lookup for the high-level business lifecycle status of an order orchestration run.';
COMMENT ON COLUMN order_status_lookup.code IS 'Unique alphanumeric code key (e.g., PENDING, COMPLETED).';
COMMENT ON COLUMN order_status_lookup.display_name IS 'Human-readable label for dashboards and UI.';
COMMENT ON COLUMN order_status_lookup.description IS 'Detailed explanation of when an order assumes this status.';
COMMENT ON COLUMN order_status_lookup.is_terminal IS 'Flag indicating if this status is a final state in the workflow.';
COMMENT ON COLUMN order_status_lookup.is_active IS 'Soft toggle to enable or deprecate lookup codes.';
COMMENT ON COLUMN order_status_lookup.sort_order IS 'Ordering index for user interfaces and reports.';
COMMENT ON COLUMN order_status_lookup.created_at IS 'Timestamp when the lookup record was created.';

INSERT INTO order_status_lookup (code, display_name, description, is_terminal, sort_order) VALUES
('PENDING', 'Pending Initialization', 'Order event received but processing has not yet commenced.', FALSE, 10),
('RUNNING', 'Running', 'Order is actively progressing through workflow nodes.', FALSE, 20),
('DUPLICATE', 'Duplicate Order', 'Order was terminated early because a prior run with this order ID already completed or is active.', TRUE, 30),
('DEFERRED_PRE_ORDER', 'Deferred Pre-Order', 'Order contains pre-order items and has been re-queued for future processing.', TRUE, 40),
('WAITING_HUMAN_REVIEW', 'Waiting for Human Review', 'Workflow paused at human-in-the-loop gate due to address errors or partial inventory issues.', FALSE, 50),
('PARTIALLY_SHIPPED', 'Partially Shipped', 'Eligible in-stock items were shipped; remaining items require human operator review.', TRUE, 60),
('COMPLETED', 'Fully Completed', 'All items verified, deducted, and fully shipped.', TRUE, 70),
('FAILED', 'Failed', 'Workflow encountered an unrecoverable exception or rejection.', TRUE, 80)
ON CONFLICT (code) DO NOTHING;

-- ----------------------------------------------------------------------------
-- 2. Payment Status Lookup
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS payment_status_lookup (
    code VARCHAR(50) PRIMARY KEY,
    display_name VARCHAR(100) NOT NULL,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order INT NOT NULL DEFAULT nextval('lookup_sort_order_seq'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE payment_status_lookup IS 
'Reference lookup for financial payment validation states from the Payment Gateway / ORDER API.';
COMMENT ON COLUMN payment_status_lookup.code IS 'Payment status code (e.g. SUCCESS, PENDING).';

INSERT INTO payment_status_lookup (code, display_name, description, sort_order) VALUES
('PENDING', 'Payment Pending', 'Payment authorization is currently pending.', 10),
('SUCCESS', 'Payment Successful', 'Payment captured and funds verified.', 20),
('FAILED', 'Payment Failed', 'Payment authorization or capture failed.', 30),
('REFUNDED', 'Refunded', 'Transaction funds were returned to customer.', 40)
ON CONFLICT (code) DO NOTHING;

-- ----------------------------------------------------------------------------
-- 3. Workflow Stage Lookup
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS workflow_stage_lookup (
    code VARCHAR(50) PRIMARY KEY,
    display_name VARCHAR(100) NOT NULL,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order INT NOT NULL DEFAULT nextval('lookup_sort_order_seq'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE workflow_stage_lookup IS 
'Reference lookup of sequential stage nodes within the LangGraph orchestrator.';
COMMENT ON COLUMN workflow_stage_lookup.code IS 'Stage code name matching LangGraph node definitions.';

INSERT INTO workflow_stage_lookup (code, display_name, description, sort_order) VALUES
('INGESTION', 'Order Ingestion & Validation', 'Initial node validating order data, duplicates, pre-orders, and payment.', 10),
('INVENTORY_CHECK', 'Inventory Assessment', 'Queries inventory API to check availability and discontinued flags for each item.', 20),
('NOTIFICATION_REVIEW', 'Notification & LLM Explanation', 'Generates human-friendly comments via LLM and idempotently dispatches alerts.', 30),
('INVENTORY_DEDUCT', 'Inventory Deduction & Reservation', 'Deducts available items; dynamically loops back to notification on stock races.', 40),
('SHIPPING_FULFILLMENT', 'Shipping & Address Validation', 'Validates shipping address and dispatches full or partial carrier shipment.', 50),
('COMPLETED', 'Workflow Completed', 'Terminal stage when order processing successfully completes.', 60),
('FAILED', 'Workflow Failed', 'Terminal stage on unhandled failure.', 70)
ON CONFLICT (code) DO NOTHING;

-- ----------------------------------------------------------------------------
-- 4. Stock Status Lookup
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stock_status_lookup (
    code VARCHAR(50) PRIMARY KEY,
    display_name VARCHAR(100) NOT NULL,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order INT NOT NULL DEFAULT nextval('lookup_sort_order_seq'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE stock_status_lookup IS 
'Reference lookup for line item availability status returned by the Inventory API.';

INSERT INTO stock_status_lookup (code, display_name, description, sort_order) VALUES
('PENDING_CHECK', 'Pending Inventory Check', 'Item has not yet been verified against inventory balance.', 10),
('IN_STOCK', 'In Stock', 'Inventory balance is sufficient to fulfill the requested quantity.', 20),
('OUT_OF_STOCK', 'Out of Stock', 'Warehouse has zero inventory for this SKU.', 30),
('PARTIAL_STOCK', 'Partial Stock Available', 'Warehouse has some inventory, but less than requested quantity.', 40),
('DISCONTINUED', 'Product Discontinued', 'Product is no longer manufactured or restocked.', 50)
ON CONFLICT (code) DO NOTHING;

-- ----------------------------------------------------------------------------
-- 5. Deduction Status Lookup
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS deduction_status_lookup (
    code VARCHAR(50) PRIMARY KEY,
    display_name VARCHAR(100) NOT NULL,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order INT NOT NULL DEFAULT nextval('lookup_sort_order_seq'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE deduction_status_lookup IS 
'Reference lookup for physical inventory deduction state per line item.';

INSERT INTO deduction_status_lookup (code, display_name, description, sort_order) VALUES
('NOT_DEDUCTED', 'Not Deducted', 'Item has not been deducted from warehouse inventory.', 10),
('DEDUCTED', 'Deducted Successfully', 'Item quantity reserved/deducted from warehouse ledger.', 20),
('FAILED_OUT_OF_STOCK', 'Deduction Failed Out of Stock', 'Deduction failed due to concurrent race condition snatching stock.', 30),
('ROLLED_BACK', 'Rolled Back / Released', 'Previously deducted quantity was released back to warehouse balance.', 40)
ON CONFLICT (code) DO NOTHING;

-- ----------------------------------------------------------------------------
-- 6. Notification Status Lookup
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS notification_status_lookup (
    code VARCHAR(50) PRIMARY KEY,
    display_name VARCHAR(100) NOT NULL,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order INT NOT NULL DEFAULT nextval('lookup_sort_order_seq'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE notification_status_lookup IS 
'Reference lookup for email and alert delivery status.';

INSERT INTO notification_status_lookup (code, display_name, description, sort_order) VALUES
('PENDING', 'Pending Dispatch', 'Notification queued for delivery.', 10),
('SENT', 'Sent Successfully', 'Notification delivered by email service provider.', 20),
('FAILED', 'Dispatch Failed', 'Delivery attempt encountered an error.', 30),
('SKIPPED_DUPLICATE', 'Skipped (Duplicate Idempotency Key)', 'Notification was skipped because idempotency check confirmed prior delivery.', 40)
ON CONFLICT (code) DO NOTHING;

-- ----------------------------------------------------------------------------
-- 7. Notification Type Lookup
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS notification_type_lookup (
    code VARCHAR(50) PRIMARY KEY,
    display_name VARCHAR(100) NOT NULL,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order INT NOT NULL DEFAULT nextval('lookup_sort_order_seq'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE notification_type_lookup IS 
'Reference lookup of alert and email notification categories.';

INSERT INTO notification_type_lookup (code, display_name, description, sort_order) VALUES
('OUT_OF_STOCK_ALERT', 'Out of Stock Alert', 'Notifies customer/ops that one or more items are out of stock.', 10),
('DISCONTINUED_ALERT', 'Discontinued Product Notice', 'Notifies customer that a product has been permanently discontinued.', 20),
('ADDRESS_ISSUE', 'Address Validation Error', 'Alerts human review team and customer about an invalid shipping destination.', 30),
('DISPATCH_CONFIRMATION', 'Full Dispatch Confirmation', 'Customer email confirming entire order was shipped with tracking.', 40),
('PARTIAL_SHIPMENT', 'Partial Shipment Notification', 'Customer email explaining split shipment and backorder details.', 50)
ON CONFLICT (code) DO NOTHING;

-- ----------------------------------------------------------------------------
-- 8. Fulfillment Type Lookup
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fulfillment_type_lookup (
    code VARCHAR(50) PRIMARY KEY,
    display_name VARCHAR(100) NOT NULL,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order INT NOT NULL DEFAULT nextval('lookup_sort_order_seq'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE fulfillment_type_lookup IS 
'Reference lookup for carrier shipment completeness.';

INSERT INTO fulfillment_type_lookup (code, display_name, description, sort_order) VALUES
('NONE', 'No Shipment Dispatched', 'No packages handed to carrier yet.', 10),
('FULL', 'Full Order Dispatched', 'All requested items included in carrier shipment.', 20),
('PARTIAL', 'Partial Order Dispatched', 'Subset of items shipped; remaining items pending or cancelled.', 30)
ON CONFLICT (code) DO NOTHING;
