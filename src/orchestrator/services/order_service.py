"""Order processing service managing ingestion, duplicate detection, and pre-orders."""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Optional
from src.orchestrator.adapters.order_adapter import OrderApiAdapter
from src.orchestrator.core.logging import logger
from src.orchestrator.entities.line_item import OrderLineItem
from src.orchestrator.entities.node_checkpoint import NodeExecutionCheckpoint
from src.orchestrator.entities.order_run import OrderOrchestrationRun
from src.orchestrator.repositories.line_item_repository import LineItemRepository
from src.orchestrator.repositories.node_checkpoint_repository import NodeCheckpointRepository
from src.orchestrator.repositories.order_run_repository import OrderRunRepository


class OrderService:
    """Service orchestrating order ingestion, duplicate detection, and validation."""

    def __init__(
        self,
        order_adapter: Optional[OrderApiAdapter] = None,
        order_repo: Optional[OrderRunRepository] = None,
        line_item_repo: Optional[LineItemRepository] = None,
        checkpoint_repo: Optional[NodeCheckpointRepository] = None,
    ):
        self.order_adapter = order_adapter or OrderApiAdapter()
        self.order_repo = order_repo or OrderRunRepository()
        self.line_item_repo = line_item_repo or LineItemRepository()
        self.checkpoint_repo = checkpoint_repo or NodeCheckpointRepository()

    def ingest_order(self, order_id: str, thread_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Executes Node 1: Ingestion & Validation logic:
        1. Checks for duplicates via OrderRunRepository.
        2. Calls ORDER API (with transparent OAuth2 in RestClient).
        3. Identifies pre-orders (defers if detected).
        4. Verifies payment success and status == PENDING_TO_SHIP.
        5. Calls ORDER_DETAILS API for line items.
        6. Persists OrderRun and LineItems to database.
        7. Records execution checkpoint.
        """
        thread_id = thread_id or order_id
        start_time = datetime.now(timezone.utc)

        logger.info(f"Ingesting order {order_id} (thread={thread_id})...")

        # 1. Duplicate check
        is_dup = False
        try:
            is_dup = self.order_repo.is_duplicate(order_id)
        except Exception as e:
            logger.warning(f"Could not verify duplicate check against DB: {e}")

        if is_dup:
            logger.warning(f"Order '{order_id}' is a duplicate submission. Terminating run.")
            try:
                self.order_repo.mark_duplicate(order_id)
            except Exception:
                pass
            self._record_checkpoint(
                order_id=order_id,
                status="COMPLETED",
                metadata={"is_duplicate": True, "action": "TERMINATE_DUPLICATE"},
                start_time=start_time,
            )
            return {
                "order_id": order_id,
                "thread_id": thread_id,
                "is_duplicate": True,
                "status": "DUPLICATE",
                "current_stage": "INGESTION",
                "stage_version": 1,
                "terminate": True,
                "error": "Duplicate order detected.",
            }

        # 2. Call ORDER API
        order_data = self.order_adapter.fetch_order(order_id)

        # 3. Check Pre-order
        if order_data.get("order_type") == "PRE_ORDER":
            logger.info(f"Order '{order_id}' is a PRE_ORDER. Re-queuing and deferring workflow.")
            self._save_order_run(order_data, thread_id, status="DEFERRED_PRE_ORDER")
            self._record_checkpoint(
                order_id=order_id,
                status="COMPLETED",
                metadata={"is_pre_order": True, "action": "DEFER_PRE_ORDER"},
                start_time=start_time,
            )
            return {
                "order_id": order_id,
                "thread_id": thread_id,
                "is_pre_order": True,
                "status": "DEFERRED_PRE_ORDER",
                "current_stage": "INGESTION",
                "stage_version": 1,
                "terminate": True,
                "error": "Order deferred: pre-order placed.",
            }

        # 4. Verify Payment and Order Status
        payment_status = order_data.get("payment_status")
        order_status = order_data.get("order_status")
        if payment_status != "SUCCESS" or order_status != "PENDING_TO_SHIP":
            error_msg = f"Order not eligible for shipping: payment={payment_status}, status={order_status}"
            logger.warning(f"[{order_id}] {error_msg}")
            self._save_order_run(order_data, thread_id, status="FAILED")
            return {
                "order_id": order_id,
                "thread_id": thread_id,
                "status": "FAILED",
                "current_stage": "INGESTION",
                "stage_version": 1,
                "terminate": True,
                "error": error_msg,
            }

        # 5. Call ORDER_DETAILS API
        items_data = self.order_adapter.fetch_order_details(order_id)
        if not items_data:
            error_msg = f"Order '{order_id}' has no line items."
            logger.error(error_msg)
            return {
                "order_id": order_id,
                "thread_id": thread_id,
                "status": "FAILED",
                "current_stage": "INGESTION",
                "stage_version": 1,
                "terminate": True,
                "error": error_msg,
            }

        # 6. Persist to Database (with graceful DB tolerance)
        run_entity = self._save_order_run(order_data, thread_id, status="RUNNING")
        line_item_entities = [
            OrderLineItem(
                order_id=order_id,
                item_id=item["item_id"],
                product_id=item["product_id"],
                sku=item["sku"],
                product_name=item["product_name"],
                quantity_ordered=item["quantity_ordered"],
                unit_price=Decimal(str(item.get("unit_price", 0.0))),
                item_metadata={"is_digital": item.get("is_digital", False)},
            )
            for item in items_data
        ]

        try:
            self.line_item_repo.bulk_upsert(line_item_entities)
        except Exception as e:
            logger.warning(f"Could not persist line items to DB: {e}")

        # 7. Record Checkpoint
        self._record_checkpoint(
            order_id=order_id,
            status="COMPLETED",
            metadata={"item_count": len(line_item_entities), "total_amount": float(run_entity.total_amount)},
            start_time=start_time,
        )

        return {
            "order_id": order_id,
            "thread_id": thread_id,
            "user_id": run_entity.user_id,
            "customer_email": run_entity.customer_email,
            "customer_phone": run_entity.customer_phone,
            "order_placed_at": run_entity.order_placed_at.isoformat(),
            "order_type": run_entity.order_type,
            "payment_status": run_entity.payment_status,
            "current_stage": "INGESTION",
            "status": "RUNNING",
            "is_duplicate": False,
            "is_pre_order": False,
            "line_items": [item.to_dict() for item in line_item_entities],
            "shipping_address": run_entity.shipping_address,
            "billing_address": run_entity.billing_address,
            "terminate": False,
            "error": None,
        }

    def _save_order_run(self, data: Dict[str, Any], thread_id: str, status: str) -> OrderOrchestrationRun:
        placed_at = data.get("order_placed_at")
        dt_placed_at = (
            datetime.fromisoformat(placed_at) if isinstance(placed_at, str)
            else datetime.now(timezone.utc)
        )

        run = OrderOrchestrationRun(
            order_id=data["order_id"],
            thread_id=thread_id,
            user_id=data["user_id"],
            customer_email=data.get("customer_email", "unknown@example.com"),
            customer_phone=data.get("customer_phone"),
            order_placed_at=dt_placed_at,
            order_type=data.get("order_type", "STANDARD"),
            payment_status=data.get("payment_status", "PENDING"),
            current_stage="INGESTION",
            status=status,
            total_amount=Decimal(str(data.get("total_amount", 0.0))),
            shipping_address=data.get("shipping_address", {}),
            billing_address=data.get("billing_address", {}),
            is_duplicate=(status == "DUPLICATE"),
        )
        try:
            existing = self.order_repo.find_by_order_id(run.order_id)
            if existing:
                self.order_repo.update_stage_and_status(
                    order_id=run.order_id,
                    current_stage=run.current_stage,
                    status=run.status,
                    stage_version=existing.stage_version + 1,
                )
                return existing
            return self.order_repo.create(run)
        except Exception as e:
            logger.warning(f"Could not persist order run to DB: {e}")
            return run

    def _record_checkpoint(self, order_id: str, status: str, metadata: Dict[str, Any], start_time: datetime) -> None:
        duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
        try:
            self.checkpoint_repo.record_checkpoint(
                NodeExecutionCheckpoint(
                    order_id=order_id,
                    node_name="order_ingest",
                    stage_version=1,
                    execution_status=status,
                    node_output_metadata=metadata,
                    duration_ms=duration_ms,
                )
            )
        except Exception as e:
            logger.warning(f"Could not record checkpoint in DB: {e}")
