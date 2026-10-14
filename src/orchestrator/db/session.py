"""PostgreSQL database connection pool and query helpers for order orchestration."""

import json
from contextlib import contextmanager
from typing import Any, Dict, Generator, List, Optional
import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from src.orchestrator.config import settings
from src.orchestrator.core.logging import logger

_pool: Optional[ConnectionPool] = None


def get_connection_pool() -> ConnectionPool:
    """Initializes or retrieves the global connection pool."""
    global _pool
    if _pool is None:
        logger.info(f"Initializing PostgreSQL connection pool to {settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}...")
        _pool = ConnectionPool(
            conninfo=settings.DATABASE_URL,
            min_size=settings.DB_POOL_MIN_SIZE,
            max_size=settings.DB_POOL_MAX_SIZE,
            timeout=settings.DB_POOL_TIMEOUT,
            kwargs={"row_factory": dict_row, "autocommit": True},
        )
    return _pool


def close_connection_pool() -> None:
    """Closes the PostgreSQL connection pool."""
    global _pool
    if _pool is not None:
        logger.info("Closing PostgreSQL connection pool...")
        _pool.close()
        _pool = None


@contextmanager
def get_db_connection() -> Generator[psycopg.Connection, None, None]:
    """Context manager yielding a pooled database connection."""
    pool = get_connection_pool()
    with pool.connection() as conn:
        yield conn


# ============================================================================
# Order Orchestration Runs & State Queries
# ============================================================================

def get_order_run(order_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves order run record by order_id."""
    with get_db_connection() as conn:
        query = """
            SELECT order_id, thread_id, user_id, customer_email, customer_phone,
                   order_placed_at, order_type, payment_status, current_stage, status,
                   fulfillment_type, human_in_loop, human_review_reason, is_duplicate,
                   deduction_completed, shipping_completed, currency, total_amount,
                   shipping_address, billing_address, carrier_name, tracking_number,
                   llm_summary_report, stage_version, created_at, updated_at
            FROM order_orchestration_runs
            WHERE order_id = %s;
        """
        row = conn.execute(query, (order_id,)).fetchone()
        return dict(row) if row else None


def create_order_run(
    order_id: str,
    thread_id: str,
    user_id: str,
    customer_email: str,
    customer_phone: Optional[str],
    order_placed_at: str,
    order_type: str,
    payment_status: str,
    current_stage: str,
    status: str,
    total_amount: float = 0.0,
    shipping_address: Optional[Dict[str, Any]] = None,
    billing_address: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Creates a new order orchestration run record."""
    with get_db_connection() as conn:
        query = """
            INSERT INTO order_orchestration_runs (
                order_id, thread_id, user_id, customer_email, customer_phone,
                order_placed_at, order_type, payment_status, current_stage, status,
                total_amount, shipping_address, billing_address, stage_version
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1)
            RETURNING *;
        """
        row = conn.execute(
            query,
            (
                order_id,
                thread_id,
                user_id,
                customer_email,
                customer_phone,
                order_placed_at,
                order_type,
                payment_status,
                current_stage,
                status,
                total_amount,
                json.dumps(shipping_address or {}),
                json.dumps(billing_address or {}),
            ),
        ).fetchone()
        return dict(row)


def update_order_stage(
    order_id: str,
    current_stage: str,
    status: str,
    stage_version: int,
    fulfillment_type: Optional[str] = None,
    human_in_loop: Optional[bool] = None,
    human_review_reason: Optional[str] = None,
    deduction_completed: Optional[bool] = None,
    shipping_completed: Optional[bool] = None,
    tracking_number: Optional[str] = None,
    carrier_name: Optional[str] = None,
    llm_summary_report: Optional[str] = None,
) -> None:
    """Updates order orchestration status and stage version."""
    with get_db_connection() as conn:
        query = """
            UPDATE order_orchestration_runs
            SET current_stage = %s,
                status = %s,
                stage_version = %s,
                fulfillment_type = COALESCE(%s, fulfillment_type),
                human_in_loop = COALESCE(%s, human_in_loop),
                human_review_reason = COALESCE(%s, human_review_reason),
                deduction_completed = COALESCE(%s, deduction_completed),
                shipping_completed = COALESCE(%s, shipping_completed),
                tracking_number = COALESCE(%s, tracking_number),
                carrier_name = COALESCE(%s, carrier_name),
                llm_summary_report = COALESCE(%s, llm_summary_report),
                updated_at = CURRENT_TIMESTAMP
            WHERE order_id = %s;
        """
        conn.execute(
            query,
            (
                current_stage,
                status,
                stage_version,
                fulfillment_type,
                human_in_loop,
                human_review_reason,
                deduction_completed,
                shipping_completed,
                tracking_number,
                carrier_name,
                llm_summary_report,
                order_id,
            ),
        )


# ============================================================================
# Order Line Items
# ============================================================================

def upsert_order_line_items(order_id: str, line_items: List[Dict[str, Any]]) -> None:
    """Inserts or updates line items for an order."""
    with get_db_connection() as conn:
        query = """
            INSERT INTO order_line_items (
                order_id, item_id, product_id, sku, product_name,
                quantity_ordered, quantity_available, quantity_deducted, quantity_shipped,
                unit_price, is_discontinued, stock_status, deduction_status, shipping_status, item_metadata
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (order_id, item_id) DO UPDATE
            SET quantity_available = EXCLUDED.quantity_available,
                quantity_deducted = EXCLUDED.quantity_deducted,
                quantity_shipped = EXCLUDED.quantity_shipped,
                is_discontinued = EXCLUDED.is_discontinued,
                stock_status = EXCLUDED.stock_status,
                deduction_status = EXCLUDED.deduction_status,
                shipping_status = EXCLUDED.shipping_status,
                updated_at = CURRENT_TIMESTAMP;
        """
        for item in line_items:
            conn.execute(
                query,
                (
                    order_id,
                    item["item_id"],
                    item["product_id"],
                    item["sku"],
                    item["product_name"],
                    item["quantity_ordered"],
                    item.get("quantity_available", 0),
                    item.get("quantity_deducted", 0),
                    item.get("quantity_shipped", 0),
                    item.get("unit_price", 0.0),
                    item.get("is_discontinued", False),
                    item.get("stock_status", "PENDING_CHECK"),
                    item.get("deduction_status", "NOT_DEDUCTED"),
                    item.get("shipping_status", "UNSHIPPED"),
                    json.dumps(item.get("item_metadata", {})),
                ),
            )


# ============================================================================
# Node Checkpoints & Metadata Audit
# ============================================================================

def record_node_checkpoint(
    order_id: str,
    node_name: str,
    stage_version: int,
    execution_status: str,
    node_input: Optional[Dict[str, Any]] = None,
    node_output_metadata: Optional[Dict[str, Any]] = None,
    llm_generated_comment: Optional[str] = None,
    duration_ms: Optional[int] = None,
    error_message: Optional[str] = None,
    stack_trace: Optional[str] = None,
) -> None:
    """Captures post-node execution state snapshot and metadata in PostgreSQL."""
    with get_db_connection() as conn:
        query = """
            INSERT INTO node_execution_checkpoints (
                order_id, node_name, stage_version, execution_status,
                node_input, node_output_metadata, llm_generated_comment,
                duration_ms, error_message, stack_trace
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        """
        conn.execute(
            query,
            (
                order_id,
                node_name,
                stage_version,
                execution_status,
                json.dumps(node_input or {}),
                json.dumps(node_output_metadata or {}),
                llm_generated_comment,
                duration_ms,
                error_message,
                stack_trace,
            ),
        )


# ============================================================================
# Idempotent Notifications
# ============================================================================

def is_notification_already_sent(idempotency_key: str) -> bool:
    """Checks whether an email/alert was already sent to avoid duplicate dispatches."""
    with get_db_connection() as conn:
        query = """
            SELECT 1 FROM order_notifications
            WHERE idempotency_key = %s AND status = 'SENT';
        """
        row = conn.execute(query, (idempotency_key,)).fetchone()
        return row is not None


def record_notification(
    order_id: str,
    node_name: str,
    idempotency_key: str,
    recipient_email: str,
    notification_type: str,
    subject: str,
    body_text: str,
    status: str,
    sent_at: Optional[str] = None,
    error_log: Optional[str] = None,
) -> None:
    """Records an idempotent notification attempt."""
    with get_db_connection() as conn:
        query = """
            INSERT INTO order_notifications (
                order_id, node_name, idempotency_key, recipient_email,
                notification_type, subject, body_text, status, sent_at, error_log
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (idempotency_key) DO UPDATE
            SET status = EXCLUDED.status,
                sent_at = EXCLUDED.sent_at,
                retry_count = order_notifications.retry_count + 1,
                error_log = EXCLUDED.error_log,
                updated_at = CURRENT_TIMESTAMP;
        """
        conn.execute(
            query,
            (
                order_id,
                node_name,
                idempotency_key,
                recipient_email,
                notification_type,
                subject,
                body_text,
                status,
                sent_at,
                error_log,
            ),
        )


# ============================================================================
# Inventory Transactions
# ============================================================================

def record_inventory_transaction(
    order_id: str,
    product_id: str,
    sku: str,
    transaction_type: str,
    quantity: int,
    status: str,
    external_reference_id: Optional[str] = None,
    reason: Optional[str] = None,
) -> None:
    """Logs an inventory deduction or rollback release transaction."""
    with get_db_connection() as conn:
        query = """
            INSERT INTO order_inventory_transactions (
                order_id, product_id, sku, transaction_type,
                quantity, status, external_reference_id, reason
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
        """
        conn.execute(
            query,
            (
                order_id,
                product_id,
                sku,
                transaction_type,
                quantity,
                status,
                external_reference_id,
                reason,
            ),
        )
