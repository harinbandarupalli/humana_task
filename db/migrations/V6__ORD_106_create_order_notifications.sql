-- ============================================================================
-- Migration: V6__ORD_106_create_order_notifications.sql
-- Ticket: ORD-106
-- Description: Idempotent email and communication ledger.
-- Prevents duplicate alert dispatches across dynamic node retries.
-- ============================================================================

-- Sequence for notification ordering
CREATE SEQUENCE IF NOT EXISTS order_notification_seq INCREMENT BY 1 START WITH 1;

CREATE TABLE IF NOT EXISTS order_notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    notification_number BIGINT NOT NULL DEFAULT nextval('order_notification_seq'),
    order_id VARCHAR(64) NOT NULL REFERENCES order_orchestration_runs(order_id) ON DELETE CASCADE,
    node_name VARCHAR(100) NOT NULL,
    idempotency_key VARCHAR(128) NOT NULL UNIQUE,
    recipient_email VARCHAR(255) NOT NULL,
    notification_type VARCHAR(50) NOT NULL REFERENCES notification_type_lookup(code),
    subject VARCHAR(255) NOT NULL,
    body_text TEXT NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'PENDING' REFERENCES notification_status_lookup(code),
    sent_at TIMESTAMPTZ,
    retry_count INT NOT NULL DEFAULT 0,
    error_log TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- Detailed Documentation & Comments
-- ============================================================================
COMMENT ON TABLE order_notifications IS 
'Idempotent log of customer emails, warehouse alerts, and carrier notifications triggered during workflow execution.';

COMMENT ON COLUMN order_notifications.id IS 
'Surrogate UUID primary key.';

COMMENT ON COLUMN order_notifications.notification_number IS 
'Chronological sequence number driven by order_notification_seq.';

COMMENT ON COLUMN order_notifications.order_id IS 
'Reference to order_orchestration_runs(order_id) with cascading deletion.';

COMMENT ON COLUMN order_notifications.node_name IS 
'LangGraph node that initiated this notification (e.g. notification_review, shipping_fulfillment).';

COMMENT ON COLUMN order_notifications.idempotency_key IS 
'Unique hash (e.g. order_id:alert_type:product_list) ensuring the same email is never sent twice across node retries.';

COMMENT ON COLUMN order_notifications.recipient_email IS 
'Target email address; indexed for recipient history lookups and spam audit checks.';

COMMENT ON COLUMN order_notifications.notification_type IS 
'Category referencing notification_type_lookup(code) (e.g. OUT_OF_STOCK_ALERT, DISPATCH_CONFIRMATION).';

COMMENT ON COLUMN order_notifications.subject IS 
'Subject line of the dispatched email.';

COMMENT ON COLUMN order_notifications.body_text IS 
'Complete email message body (incorporating LLM generated summaries and explanations).';

COMMENT ON COLUMN order_notifications.status IS 
'Delivery status referencing notification_status_lookup(code) (PENDING, SENT, FAILED, SKIPPED_DUPLICATE).';

COMMENT ON COLUMN order_notifications.sent_at IS 
'Exact timestamp when email provider accepted and delivered message.';

COMMENT ON COLUMN order_notifications.retry_count IS 
'Number of failed delivery attempts made for this notification.';

COMMENT ON COLUMN order_notifications.error_log IS 
'Failure diagnostics if delivery encountered an SMTP or provider API error.';

COMMENT ON COLUMN order_notifications.created_at IS 
'Timestamp when notification intent was queued.';

COMMENT ON COLUMN order_notifications.updated_at IS 
'Timestamp of last status modification.';

-- ============================================================================
-- Indexes
-- ============================================================================
-- Explicit recipient email index requested for fast communication auditing
CREATE INDEX IF NOT EXISTS idx_order_notifications_recipient_email 
    ON order_notifications (recipient_email);

CREATE INDEX IF NOT EXISTS idx_order_notifications_order_id 
    ON order_notifications (order_id);

CREATE INDEX IF NOT EXISTS idx_order_notifications_status 
    ON order_notifications (status);

CREATE INDEX IF NOT EXISTS idx_order_notifications_type 
    ON order_notifications (notification_type);

-- ============================================================================
-- Trigger for automatic updated_at timestamp maintenance
-- ============================================================================
CREATE OR REPLACE FUNCTION update_order_notifications_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_order_notifications_updated_at ON order_notifications;

CREATE TRIGGER trigger_order_notifications_updated_at
    BEFORE UPDATE ON order_notifications
    FOR EACH ROW
    EXECUTE FUNCTION update_order_notifications_updated_at();
