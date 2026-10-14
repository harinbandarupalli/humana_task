"""Dedicated repository for order_notifications table."""

from datetime import datetime
from typing import Any, Dict, List, Optional
import psycopg
from src.orchestrator.entities.notification import OrderNotification
from src.orchestrator.repositories.base import BaseRepository
from src.orchestrator.repositories.exceptions import EntityNotFoundError


class NotificationRepository(BaseRepository):
    """Data access repository for order_notifications with idempotency guarantees."""

    def __init__(self, conn: Optional[psycopg.Connection] = None):
        super().__init__(conn)

    @staticmethod
    def _from_row(row: Dict[str, Any]) -> OrderNotification:
        """Converts database row dictionary to OrderNotification entity."""
        return OrderNotification.model_validate(dict(row))

    def is_already_sent(self, idempotency_key: str) -> bool:
        """
        Idempotency check: returns True if a notification with this key has already been delivered.
        Guarantees emails are not sent more than once on node retries.
        """
        query = """
            SELECT 1 FROM order_notifications
            WHERE idempotency_key = %s AND status = 'SENT';
        """
        with self.get_connection() as conn:
            row = conn.execute(query, (idempotency_key,)).fetchone()
            return row is not None

    def queue_notification(self, notification: OrderNotification) -> OrderNotification:
        """
        Inserts or updates a notification record using the idempotency_key.
        If record exists, increments retry_count.
        """
        query = """
            INSERT INTO order_notifications (
                order_id, node_name, idempotency_key, recipient_email,
                notification_type, subject, body_text, status, sent_at, error_log
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (idempotency_key) DO UPDATE
            SET retry_count = order_notifications.retry_count + 1,
                error_log = EXCLUDED.error_log,
                updated_at = CURRENT_TIMESTAMP
            RETURNING *;
        """
        params = (
            notification.order_id,
            notification.node_name,
            notification.idempotency_key,
            notification.recipient_email,
            notification.notification_type,
            notification.subject,
            notification.body_text,
            notification.status,
            notification.sent_at,
            notification.error_log,
        )

        with self.get_connection() as conn:
            row = conn.execute(query, params).fetchone()
            return self._from_row(row)

    def mark_sent(self, idempotency_key: str, sent_at: Optional[datetime] = None) -> None:
        """Updates notification status to SENT upon provider confirmation."""
        sent_timestamp = sent_at or datetime.utcnow()
        query = """
            UPDATE order_notifications
            SET status = 'SENT',
                sent_at = %s,
                error_log = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE idempotency_key = %s;
        """
        with self.get_connection() as conn:
            res = conn.execute(query, (sent_timestamp, idempotency_key))
            if res.rowcount == 0:
                raise EntityNotFoundError(f"Notification with idempotency_key='{idempotency_key}' not found.")

    def mark_failed(self, idempotency_key: str, error_log: str) -> None:
        """Updates notification status to FAILED with error diagnostic log."""
        query = """
            UPDATE order_notifications
            SET status = 'FAILED',
                error_log = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE idempotency_key = %s;
        """
        with self.get_connection() as conn:
            res = conn.execute(query, (error_log, idempotency_key))
            if res.rowcount == 0:
                raise EntityNotFoundError(f"Notification with idempotency_key='{idempotency_key}' not found.")

    def find_by_order_id(self, order_id: str) -> List[OrderNotification]:
        """Retrieves all notifications triggered for a given order."""
        query = """
            SELECT * FROM order_notifications
            WHERE order_id = %s
            ORDER BY notification_number ASC;
        """
        with self.get_connection() as conn:
            rows = conn.execute(query, (order_id,)).fetchall()
            return [self._from_row(row) for row in rows]

    def find_by_recipient_email(self, recipient_email: str) -> List[OrderNotification]:
        """Retrieves notifications by recipient email using idx_order_notifications_recipient_email."""
        query = """
            SELECT * FROM order_notifications
            WHERE recipient_email = %s
            ORDER BY created_at DESC;
        """
        with self.get_connection() as conn:
            rows = conn.execute(query, (recipient_email,)).fetchall()
            return [self._from_row(row) for row in rows]
