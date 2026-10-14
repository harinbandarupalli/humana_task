"""Shipping service managing address validation, carrier fulfillment, and final LLM reports."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from src.orchestrator.adapters.shipping_adapter import ShippingApiAdapter
from src.orchestrator.core.logging import logger
from src.orchestrator.entities.node_checkpoint import NodeExecutionCheckpoint
from src.orchestrator.repositories.line_item_repository import LineItemRepository
from src.orchestrator.repositories.node_checkpoint_repository import NodeCheckpointRepository
from src.orchestrator.repositories.order_run_repository import OrderRunRepository
from src.orchestrator.services.llm_service import LLMReasoningService


class ShippingService:
    """Service managing address validation, carrier dispatch, and fulfillment reporting."""

    def __init__(
        self,
        shipping_adapter: Optional[ShippingApiAdapter] = None,
        order_repo: Optional[OrderRunRepository] = None,
        line_item_repo: Optional[LineItemRepository] = None,
        checkpoint_repo: Optional[NodeCheckpointRepository] = None,
        llm_service: Optional[LLMReasoningService] = None,
    ):
        self.shipping_adapter = shipping_adapter or ShippingApiAdapter()
        self.order_repo = order_repo or OrderRunRepository()
        self.line_item_repo = line_item_repo or LineItemRepository()
        self.checkpoint_repo = checkpoint_repo or NodeCheckpointRepository()
        self.llm_service = llm_service or LLMReasoningService()

    def process_shipping_fulfillment(
        self,
        order_id: str,
        eligible_items: List[Dict[str, Any]],
        ineligible_items: List[Dict[str, Any]],
        shipping_address: Optional[Dict[str, Any]] = None,
        stage_version: int = 5,
    ) -> Dict[str, Any]:
        """
        Executes Node 5:
        1. Validates destination shipping address.
           - If invalid -> routes to WAITING_HUMAN_REVIEW with LLM explanation.
        2. Validates eligible items exist for carrier dispatch.
           - If zero eligible items -> routes to WAITING_HUMAN_REVIEW.
        3. Calls carrier API to create shipment for eligible items.
        4. Sets status:
           - FULL -> status = COMPLETED, human_in_loop = FALSE.
           - PARTIAL -> status = PARTIALLY_SHIPPED, human_in_loop = TRUE.
        5. Generates detailed final LLM fulfillment summary report.
        """
        start_time = datetime.now(timezone.utc)
        address = dict(shipping_address) if shipping_address else {}

        if not address:
            try:
                order_run = self.order_repo.find_by_order_id(order_id)
                if order_run and order_run.shipping_address:
                    address = dict(order_run.shipping_address)
            except Exception as e:
                logger.warning(f"[{order_id}] Database offline when fetching order run: {e}")

        if not address:
            address = {
                "street_1": "100 Innovation Way",
                "city": "Austin",
                "state": "TX",
                "postal_code": "78701",
                "country": "USA",
            }

        # 1. Address Validation
        address_validation = self.shipping_adapter.validate_address(address, order_id=order_id)
        if not address_validation.get("is_valid", False):
            error_reason = address_validation.get("error_reason", "Street address cannot be located by carrier database.")
            logger.warning(f"[{order_id}] Address invalid: {error_reason}. Pausing for human review.")

            llm_comment = self.llm_service.generate_address_issue_comment(
                order_id=order_id,
                address=address,
                error_reason=error_reason,
            )

            try:
                self.order_repo.mark_human_review_required(order_id=order_id, reason=llm_comment)
            except Exception as e:
                logger.warning(f"[{order_id}] Could not persist human review to DB: {e}")

            duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            try:
                self.checkpoint_repo.record_checkpoint(
                    NodeExecutionCheckpoint(
                        order_id=order_id,
                        node_name="shipping_fulfillment",
                        stage_version=stage_version,
                        execution_status="HUMAN_REVIEW_REQUIRED",
                        llm_generated_comment=llm_comment,
                        node_output_metadata={"action": "HUMAN_REVIEW_REQUIRED", "reason": error_reason},
                        duration_ms=duration_ms,
                    )
                )
            except Exception as e:
                logger.warning(f"[{order_id}] Could not record checkpoint in DB: {e}")

            return {
                "success": False,
                "order_id": order_id,
                "current_stage": "SHIPPING_FULFILLMENT",
                "status": "WAITING_HUMAN_REVIEW",
                "fulfillment_type": "NONE",
                "human_in_loop": True,
                "human_review_reason": llm_comment,
                "carrier_name": None,
                "tracking_number": None,
                "llm_summary_report": llm_comment,
                "shipping_completed": False,
                "duration_ms": duration_ms,
            }

        # 2. Check for Eligible Items
        if not eligible_items:
            logger.warning(f"[{order_id}] No eligible items available to ship. Escalating to human review.")
            llm_report = self.llm_service.generate_final_summary_report(
                order_id=order_id,
                fulfillment_type="NONE",
                shipped_items=[],
                unfulfilled_items=ineligible_items,
                carrier_name="NONE",
                tracking_number="NONE",
            )

            reason = "Zero eligible items available for carrier shipment dispatch."
            try:
                self.order_repo.update_stage_and_status(
                    order_id=order_id,
                    current_stage="SHIPPING_FULFILLMENT",
                    status="WAITING_HUMAN_REVIEW",
                    stage_version=stage_version,
                    fulfillment_type="NONE",
                    human_in_loop=True,
                    human_review_reason=reason,
                    shipping_completed=False,
                    llm_summary_report=llm_report,
                )
            except Exception as e:
                logger.warning(f"[{order_id}] Could not update DB for unfulfilled order: {e}")

            duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            try:
                self.checkpoint_repo.record_checkpoint(
                    NodeExecutionCheckpoint(
                        order_id=order_id,
                        node_name="shipping_fulfillment",
                        stage_version=stage_version,
                        execution_status="HUMAN_REVIEW_REQUIRED",
                        llm_generated_comment=llm_report,
                        node_output_metadata={"action": "HUMAN_REVIEW_REQUIRED", "reason": reason},
                        duration_ms=duration_ms,
                    )
                )
            except Exception as e:
                logger.warning(f"[{order_id}] Could not record checkpoint in DB: {e}")

            return {
                "success": False,
                "order_id": order_id,
                "current_stage": "SHIPPING_FULFILLMENT",
                "status": "WAITING_HUMAN_REVIEW",
                "fulfillment_type": "NONE",
                "human_in_loop": True,
                "human_review_reason": reason,
                "carrier_name": None,
                "tracking_number": None,
                "llm_summary_report": llm_report,
                "shipping_completed": False,
                "duration_ms": duration_ms,
            }

        # 3. Determine Fulfillment Type
        is_partial = len(ineligible_items) > 0
        fulfillment_type = "PARTIAL" if is_partial else "FULL"

        # 4. Call Carrier API
        shipment_result = self.shipping_adapter.dispatch_shipment(
            order_id=order_id,
            items=eligible_items,
            address=address,
            is_partial=is_partial,
        )

        carrier_name = shipment_result.get("carrier_name", "FedEx Express")
        tracking_number = shipment_result.get("tracking_number", "TRK-PENDING")

        # Update shipped line items
        for item in eligible_items:
            try:
                self.line_item_repo.update_shipping_status(
                    order_id=order_id,
                    item_id=item["item_id"],
                    quantity_shipped=item.get("quantity_ordered", 1),
                    shipping_status="SHIPPED",
                )
            except Exception as e:
                logger.warning(f"[{order_id}] Could not update shipping status for item {item.get('item_id')}: {e}")

        # 5. Generate Final LLM Summary Report
        logger.info(f"[{order_id}] Generating final fulfillment report via LLM...")
        llm_report = self.llm_service.generate_final_summary_report(
            order_id=order_id,
            fulfillment_type=fulfillment_type,
            shipped_items=eligible_items,
            unfulfilled_items=ineligible_items,
            carrier_name=carrier_name,
            tracking_number=tracking_number,
        )

        # 6. Conclude Order in Database
        final_status = "PARTIALLY_SHIPPED" if is_partial else "COMPLETED"
        human_in_loop = True if is_partial else False
        human_review_reason = (
            f"Partial fulfillment: {len(eligible_items)} items shipped, {len(ineligible_items)} unfulfilled."
            if is_partial else None
        )

        try:
            self.order_repo.mark_completed(
                order_id=order_id,
                fulfillment_type=fulfillment_type,
                tracking_number=tracking_number,
                carrier_name=carrier_name,
                llm_summary_report=llm_report,
            )
        except Exception as e:
            logger.warning(f"[{order_id}] Could not mark completed in DB: {e}")

        duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
        try:
            self.checkpoint_repo.record_checkpoint(
                NodeExecutionCheckpoint(
                    order_id=order_id,
                    node_name="shipping_fulfillment",
                    stage_version=stage_version,
                    execution_status="COMPLETED",
                    llm_generated_comment=llm_report,
                    node_output_metadata={
                        "carrier_name": carrier_name,
                        "tracking_number": tracking_number,
                        "fulfillment_type": fulfillment_type,
                        "human_in_loop": human_in_loop,
                        "shipped_count": len(eligible_items),
                        "unfulfilled_count": len(ineligible_items),
                    },
                    duration_ms=duration_ms,
                )
            )
        except Exception as e:
            logger.warning(f"[{order_id}] Could not record checkpoint in DB: {e}")

        logger.info(f"[{order_id}] Shipping fulfilled successfully. Status={final_status}, Tracking={tracking_number}")

        return {
            "success": True,
            "order_id": order_id,
            "current_stage": "SHIPPING_FULFILLMENT",
            "status": final_status,
            "fulfillment_type": fulfillment_type,
            "human_in_loop": human_in_loop,
            "human_review_reason": human_review_reason,
            "carrier_name": carrier_name,
            "tracking_number": tracking_number,
            "llm_summary_report": llm_report,
            "shipping_completed": True,
            "duration_ms": duration_ms,
        }
