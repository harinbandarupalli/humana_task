"""Dedicated repository for order_orchestration_runs table."""

import json
from decimal import Decimal
from typing import Any, Dict, List, Optional
import psycopg
from src.orchestrator.entities.order_run import OrderOrchestrationRun
from src.orchestrator.repositories.base import BaseRepository
from src.orchestrator.repositories.exceptions import DuplicateEntityError, EntityNotFoundError


class OrderRunRepository(BaseRepository):
    """Data access repository for order_orchestration_runs."""

    def __init__(self, conn: Optional[psycopg.Connection] = None):
        super().__init__(conn)

    @staticmethod
    def _from_row(row: Dict[str, Any]) -> OrderOrchestrationRun:
        """Converts raw database dictionary row to OrderOrchestrationRun entity."""
        return OrderOrchestrationRun.model_validate(dict(row))

    def create(self, run: OrderOrchestrationRun) -> OrderOrchestrationRun:
        """Inserts a new order orchestration run record into database."""
        query = """
            INSERT INTO order_orchestration_runs (
                order_id, thread_id, user_id, customer_email, customer_phone,
                order_placed_at, order_type, payment_status, current_stage, status,
                fulfillment_type, human_in_loop, human_review_reason, is_duplicate,
                deduction_completed, shipping_completed, currency, total_amount,
                shipping_address, billing_address, carrier_name, tracking_number,
                llm_summary_report, stage_version
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s
            )
            RETURNING *;
        """
        params = (
            run.order_id,
            run.thread_id,
            run.user_id,
            run.customer_email,
            run.customer_phone,
            run.order_placed_at,
            run.order_type,
            run.payment_status,
            run.current_stage,
            run.status,
            run.fulfillment_type,
            run.human_in_loop,
            run.human_review_reason,
            run.is_duplicate,
            run.deduction_completed,
            run.shipping_completed,
            run.currency,
            run.total_amount,
            json.dumps(run.shipping_address),
            json.dumps(run.billing_address),
            run.carrier_name,
            run.tracking_number,
            run.llm_summary_report,
            run.stage_version,
        )

        with self.get_connection() as conn:
            try:
                row = conn.execute(query, params).fetchone()
                return self._from_row(row)
            except psycopg.errors.UniqueViolation as e:
                raise DuplicateEntityError(f"OrderRun with order_id='{run.order_id}' or thread_id='{run.thread_id}' already exists.") from e

    def find_by_order_id(self, order_id: str) -> Optional[OrderOrchestrationRun]:
        """Fetches an order run by primary key order_id."""
        query = "SELECT * FROM order_orchestration_runs WHERE order_id = %s;"
        with self.get_connection() as conn:
            row = conn.execute(query, (order_id,)).fetchone()
            return self._from_row(row) if row else None

    def find_by_thread_id(self, thread_id: str) -> Optional[OrderOrchestrationRun]:
        """Fetches an order run by LangGraph thread_id."""
        query = "SELECT * FROM order_orchestration_runs WHERE thread_id = %s;"
        with self.get_connection() as conn:
            row = conn.execute(query, (thread_id,)).fetchone()
            return self._from_row(row) if row else None

    def find_by_user_id(self, user_id: str, limit: int = 50) -> List[OrderOrchestrationRun]:
        """Fetches order runs placed by a specific user_id using idx_order_runs_user_id."""
        query = """
            SELECT * FROM order_orchestration_runs
            WHERE user_id = %s
            ORDER BY order_placed_at DESC
            LIMIT %s;
        """
        with self.get_connection() as conn:
            rows = conn.execute(query, (user_id, limit)).fetchall()
            return [self._from_row(row) for row in rows]

    def find_by_customer_email(self, customer_email: str) -> List[OrderOrchestrationRun]:
        """Fetches orders by customer email using idx_order_runs_customer_email."""
        query = """
            SELECT * FROM order_orchestration_runs
            WHERE customer_email = %s
            ORDER BY order_placed_at DESC;
        """
        with self.get_connection() as conn:
            rows = conn.execute(query, (customer_email,)).fetchall()
            return [self._from_row(row) for row in rows]

    def find_by_customer_phone(self, customer_phone: str) -> List[OrderOrchestrationRun]:
        """Fetches orders by customer phone using idx_order_runs_customer_phone."""
        query = """
            SELECT * FROM order_orchestration_runs
            WHERE customer_phone = %s
            ORDER BY order_placed_at DESC;
        """
        with self.get_connection() as conn:
            rows = conn.execute(query, (customer_phone,)).fetchall()
            return [self._from_row(row) for row in rows]

    def is_duplicate(self, order_id: str) -> bool:
        """
        Checks whether an order_id has already been processed or is active.
        Orders that are COMPLETED, RUNNING, or already marked DUPLICATE are considered duplicates.
        """
        query = """
            SELECT 1 FROM order_orchestration_runs
            WHERE order_id = %s
              AND status IN ('COMPLETED', 'RUNNING', 'PARTIALLY_SHIPPED', 'DUPLICATE');
        """
        try:
            with self.get_connection() as conn:
                row = conn.execute(query, (order_id,)).fetchone()
                return row is not None
        except Exception:
            return False

    def mark_duplicate(self, order_id: str) -> None:
        """Flags an order as DUPLICATE and terminal."""
        query = """
            UPDATE order_orchestration_runs
            SET is_duplicate = TRUE,
                status = 'DUPLICATE',
                updated_at = CURRENT_TIMESTAMP
            WHERE order_id = %s;
        """
        with self.get_connection() as conn:
            res = conn.execute(query, (order_id,))
            if res.rowcount == 0:
                raise EntityNotFoundError(f"Order '{order_id}' not found to mark duplicate.")

    def update_stage_and_status(
        self,
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
        """Updates workflow progress, state flags, and tracking metadata."""
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
        params = (
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
        )
        with self.get_connection() as conn:
            res = conn.execute(query, params)
            if res.rowcount == 0:
                raise EntityNotFoundError(f"Order '{order_id}' not found for update.")

    def mark_human_review_required(self, order_id: str, reason: str) -> None:
        """Flags order for operator intervention and pauses execution."""
        query = """
            UPDATE order_orchestration_runs
            SET human_in_loop = TRUE,
                status = 'WAITING_HUMAN_REVIEW',
                human_review_reason = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE order_id = %s;
        """
        with self.get_connection() as conn:
            res = conn.execute(query, (reason, order_id))
            if res.rowcount == 0:
                raise EntityNotFoundError(f"Order '{order_id}' not found.")

    def mark_completed(
        self,
        order_id: str,
        fulfillment_type: str,
        tracking_number: Optional[str] = None,
        carrier_name: Optional[str] = None,
        llm_summary_report: Optional[str] = None,
    ) -> None:
        """Marks workflow as COMPLETED (or PARTIALLY_SHIPPED)."""
        status = "COMPLETED" if fulfillment_type == "FULL" else "PARTIALLY_SHIPPED"
        human_in_loop = True if fulfillment_type == "PARTIAL" else False

        query = """
            UPDATE order_orchestration_runs
            SET current_stage = 'COMPLETED',
                status = %s,
                fulfillment_type = %s,
                human_in_loop = %s,
                shipping_completed = TRUE,
                tracking_number = %s,
                carrier_name = %s,
                llm_summary_report = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE order_id = %s;
        """
        params = (
            status,
            fulfillment_type,
            human_in_loop,
            tracking_number,
            carrier_name,
            llm_summary_report,
            order_id,
        )
        with self.get_connection() as conn:
            res = conn.execute(query, params)
            if res.rowcount == 0:
                raise EntityNotFoundError(f"Order '{order_id}' not found.")
