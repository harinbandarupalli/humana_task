"""Notification service orchestrating idempotent operations alerts and LLM dossiers."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from src.orchestrator.adapters.notification_adapter import NotificationApiAdapter
from src.orchestrator.core.logging import logger
from src.orchestrator.entities.node_checkpoint import NodeExecutionCheckpoint
from src.orchestrator.entities.notification import OrderNotification
from src.orchestrator.repositories.node_checkpoint_repository import NodeCheckpointRepository
from src.orchestrator.repositories.notification_repository import NotificationRepository
from src.orchestrator.repositories.order_run_repository import OrderRunRepository
from src.orchestrator.services.llm_service import LLMReasoningService


class NotificationService:
    """Service managing LLM operational dossiers and idempotent escalation alerts."""

    def __init__(
        self,
        notification_adapter: Optional[NotificationApiAdapter] = None,
        notification_repo: Optional[NotificationRepository] = None,
        order_repo: Optional[OrderRunRepository] = None,
        checkpoint_repo: Optional[NodeCheckpointRepository] = None,
        llm_service: Optional[LLMReasoningService] = None,
    ):
        self.notification_adapter = notification_adapter or NotificationApiAdapter()
        self.notification_repo = notification_repo or NotificationRepository()
        self.order_repo = order_repo or OrderRunRepository()
        self.checkpoint_repo = checkpoint_repo or NodeCheckpointRepository()
        self.llm_service = llm_service or LLMReasoningService()

    def process_notification_review(
        self,
        order_id: str,
        line_items: List[Dict[str, Any]],
        ineligible_items: List[Dict[str, Any]],
        fulfillment_type: str = "FULL",
        customer_email: Optional[str] = None,
        order_metadata: Optional[Dict[str, Any]] = None,
        stage_version: int = 3,
    ) -> Dict[str, Any]:
        """
        Executes Node 3:
        1. When shortages/discontinued items exist, uses LLM to generate an exhaustive
           operational dossier for human fulfillment agents to investigate in ERP/WMS.
        2. Idempotently dispatches the alert to the internal operations team.
        3. If no shortages exist (100% in stock), skips alert cleanly.
        """
        start_time = datetime.now(timezone.utc)
        order_run = None
        try:
            order_run = self.order_repo.find_by_order_id(order_id)
        except Exception as e:
            logger.warning(f"[{order_id}] Database offline when querying order run: {e}")

        email = customer_email or (order_run.customer_email if order_run else "customer@example.com")
        llm_comment: Optional[str] = None
        email_sent = False

        if ineligible_items:
            logger.info(
                f"[{order_id}] Compiling operational dossier for {len(ineligible_items)} shortage item(s)..."
            )

            meta = dict(order_metadata or {})
            if order_run:
                placed = order_run.order_placed_at
                meta.setdefault("order_placed_at", placed.isoformat() if hasattr(placed, "isoformat") else str(placed))
                meta.setdefault("customer_email", order_run.customer_email)
                meta.setdefault("shipping_address", order_run.shipping_address)

            # 1. Generate Operations Dossier via LLM
            llm_comment = self.llm_service.generate_ops_shortage_briefing(
                order_id=order_id,
                line_items=line_items,
                fulfillment_type=fulfillment_type,
                order_metadata=meta,
            )

            # 2. Compute Deterministic Idempotency Key
            sku_sig = "-".join(sorted([f"{it.get('sku')}:{it.get('stock_status')}" for it in ineligible_items]))
            idempotency_key = f"{order_id}:OPS_ALERT:{sku_sig}"

            # 3. Idempotency Check with Database
            already_sent = False
            try:
                already_sent = self.notification_repo.is_already_sent(idempotency_key)
            except Exception as e:
                logger.warning(f"[{order_id}] Could not verify notification idempotency against DB: {e}")

            if already_sent:
                logger.info(f"[{order_id}] Ops alert already delivered (key='{idempotency_key}'). Skipping duplicate dispatch.")
                email_sent = True
            else:
                ops_recipient = "ops-fulfillment@internal.store"
                subject = f"[OPS REVIEW REQUIRED] Order {order_id} - Inventory Shortage & Fulfillment Disposition"
                body = llm_comment

                # Queue pending notification record
                notif_entity = OrderNotification(
                    order_id=order_id,
                    node_name="notification_review",
                    idempotency_key=idempotency_key,
                    recipient_email=ops_recipient,
                    notification_type="OUT_OF_STOCK_ALERT",
                    subject=subject,
                    body_text=body,
                    status="PENDING",
                )
                try:
                    self.notification_repo.queue_notification(notif_entity)
                except Exception as e:
                    logger.warning(f"[{order_id}] Could not queue notification in DB: {e}")

                # Dispatch via adapter
                try:
                    res = self.notification_adapter.send_email(
                        recipient_email=ops_recipient,
                        subject=subject,
                        body=body,
                        idempotency_key=idempotency_key,
                    )
                    if res.get("success"):
                        email_sent = True
                        try:
                            self.notification_repo.mark_sent(idempotency_key=idempotency_key)
                        except Exception:
                            pass
                    else:
                        try:
                            self.notification_repo.mark_failed(
                                idempotency_key=idempotency_key,
                                error_log="Provider dispatch returned unsuccessful status",
                            )
                        except Exception:
                            pass
                except Exception as e:
                    try:
                        self.notification_repo.mark_failed(idempotency_key=idempotency_key, error_log=str(e))
                    except Exception:
                        pass
                    raise
        else:
            logger.info(f"[{order_id}] Zero shortages detected. Skipping ops alert dispatch.")

        # 4. Record Execution Checkpoint
        duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
        try:
            self.checkpoint_repo.record_checkpoint(
                NodeExecutionCheckpoint(
                    order_id=order_id,
                    node_name="notification_review",
                    stage_version=stage_version,
                    execution_status="COMPLETED",
                    llm_generated_comment=llm_comment,
                    node_output_metadata={
                        "email_sent": email_sent,
                        "ineligible_count": len(ineligible_items),
                        "fulfillment_type": fulfillment_type,
                        "recipient": "ops-fulfillment@internal.store" if ineligible_items else None,
                    },
                    duration_ms=duration_ms,
                )
            )
        except Exception as e:
            logger.warning(f"[{order_id}] Could not record checkpoint in DB: {e}")

        return {
            "order_id": order_id,
            "current_stage": "NOTIFICATION_REVIEW",
            "stage_version": stage_version,
            "llm_comment": llm_comment,
            "email_sent": email_sent,
            "duration_ms": duration_ms,
        }
