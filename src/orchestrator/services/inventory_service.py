"""Inventory service for stock verification, atomic deductions, and rollbacks."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from src.orchestrator.adapters.inventory_adapter import InventoryApiAdapter
from src.orchestrator.core.logging import logger
from src.orchestrator.entities.inventory_transaction import OrderInventoryTransaction
from src.orchestrator.entities.node_checkpoint import NodeExecutionCheckpoint
from src.orchestrator.repositories.inventory_transaction_repository import (
    InventoryTransactionRepository,
)
from src.orchestrator.repositories.line_item_repository import LineItemRepository
from src.orchestrator.repositories.node_checkpoint_repository import NodeCheckpointRepository
from src.orchestrator.repositories.order_run_repository import OrderRunRepository


class InventoryService:
    """Service orchestrating inventory assessment, deductions, and rollbacks."""

    def __init__(
        self,
        inventory_adapter: Optional[InventoryApiAdapter] = None,
        line_item_repo: Optional[LineItemRepository] = None,
        inv_tx_repo: Optional[InventoryTransactionRepository] = None,
        order_repo: Optional[OrderRunRepository] = None,
        checkpoint_repo: Optional[NodeCheckpointRepository] = None,
    ):
        self.inventory_adapter = inventory_adapter or InventoryApiAdapter()
        self.line_item_repo = line_item_repo or LineItemRepository()
        self.inv_tx_repo = inv_tx_repo or InventoryTransactionRepository()
        self.order_repo = order_repo or OrderRunRepository()
        self.checkpoint_repo = checkpoint_repo or NodeCheckpointRepository()

    def assess_inventory(
        self,
        order_id: str,
        state_line_items: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Executes Node 2: Queries Inventory API to assess stock for all line items.
        Updates line items in DB (with offline resilience) and categorizes eligible vs ineligible items.
        """
        start_time = datetime.now(timezone.utc)
        items: List[Dict[str, Any]] = []

        # 1. Fetch line items from DB, falling back to state_line_items if DB is offline or empty
        try:
            db_items = self.line_item_repo.find_by_order_id(order_id)
            if db_items:
                items = [item.to_dict() for item in db_items]
        except Exception as e:
            logger.warning(f"[{order_id}] Database offline when querying line items: {e}")

        if not items and state_line_items:
            items = [dict(item) for item in state_line_items]

        if not items:
            raise ValueError(f"No line items found for order {order_id}")

        # 2. Query Warehouse Inventory API
        skus = [item["sku"] for item in items]
        stock_map = self.inventory_adapter.check_inventory(skus, order_id=order_id)

        eligible_items: List[Dict[str, Any]] = []
        ineligible_items: List[Dict[str, Any]] = []
        assessed_items: List[Dict[str, Any]] = []

        # 3. Assess stock balance and classify each SKU
        for item in items:
            sku = item["sku"]
            stock_info = stock_map.get(sku, {"quantity_available": 0, "is_discontinued": False})
            qty_available = stock_info.get("quantity_available", 0)
            is_discontinued = stock_info.get("is_discontinued", False)
            qty_ordered = item.get("quantity_ordered", 1)

            if is_discontinued:
                status = "DISCONTINUED"
            elif qty_available >= qty_ordered:
                status = "IN_STOCK"
            elif qty_available > 0:
                status = "PARTIAL_STOCK"
            else:
                status = "OUT_OF_STOCK"

            # 4. Attempt DB update with resilience
            try:
                self.line_item_repo.update_inventory_assessment(
                    order_id=order_id,
                    item_id=item["item_id"],
                    quantity_available=qty_available,
                    is_discontinued=is_discontinued,
                    stock_status=status,
                )
            except Exception as e:
                logger.warning(
                    f"[{order_id}] Could not persist inventory assessment for item {item.get('item_id')}: {e}"
                )

            updated_item = dict(item)
            updated_item.update({
                "quantity_available": qty_available,
                "is_discontinued": is_discontinued,
                "stock_status": status,
            })
            assessed_items.append(updated_item)

            if status == "IN_STOCK" and not is_discontinued:
                eligible_items.append(updated_item)
            else:
                ineligible_items.append(updated_item)

        # 5. Determine order fulfillment classification
        if len(eligible_items) == len(items):
            fulfillment_type = "FULL"
        elif len(eligible_items) > 0:
            fulfillment_type = "PARTIAL"
        else:
            fulfillment_type = "NONE"

        # 6. Update order run status in DB
        try:
            self.order_repo.update_stage_and_status(
                order_id=order_id,
                current_stage="INVENTORY_CHECK",
                status="RUNNING",
                stage_version=2,
                fulfillment_type=fulfillment_type,
            )
        except Exception as e:
            logger.warning(f"[{order_id}] Could not update order stage in DB: {e}")

        # 7. Record checkpoint
        duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
        try:
            self.checkpoint_repo.record_checkpoint(
                NodeExecutionCheckpoint(
                    order_id=order_id,
                    node_name="inventory_check",
                    stage_version=2,
                    execution_status="COMPLETED",
                    node_output_metadata={
                        "total_items": len(items),
                        "eligible_count": len(eligible_items),
                        "ineligible_count": len(ineligible_items),
                        "fulfillment_type": fulfillment_type,
                    },
                    duration_ms=duration_ms,
                )
            )
        except Exception as e:
            logger.warning(f"[{order_id}] Could not record checkpoint in DB: {e}")

        logger.info(
            f"[{order_id}] Inventory check: {len(eligible_items)} eligible, "
            f"{len(ineligible_items)} ineligible, fulfillment_type={fulfillment_type} (duration={duration_ms}ms)"
        )

        return {
            "order_id": order_id,
            "current_stage": "INVENTORY_CHECK",
            "stage_version": 2,
            "line_items": assessed_items,
            "eligible_items": eligible_items,
            "ineligible_items": ineligible_items,
            "fulfillment_type": fulfillment_type,
            "has_shortages": len(ineligible_items) > 0,
            "duration_ms": duration_ms,
        }

    def deduct_inventory(
        self,
        order_id: str,
        items_to_deduct: List[Dict[str, Any]],
        all_line_items: Optional[List[Dict[str, Any]]] = None,
        ineligible_items: Optional[List[Dict[str, Any]]] = None,
        deduction_loop_count: int = 0,
        stage_version: int = 4,
    ) -> Dict[str, Any]:
        """
        Executes Node 4: Deducts eligible items from warehouse inventory.
        Handles race-condition failures, updates ledger transactions, and prepares
        rollback loopback if needed.
        """
        start_time = datetime.now(timezone.utc)
        all_items = [dict(it) for it in (all_line_items or items_to_deduct)]
        ineligible = [dict(it) for it in (ineligible_items or [])]

        if not items_to_deduct:
            logger.info(f"[{order_id}] Zero eligible items to deduct.")
            return {
                "success": True,
                "deducted_count": 0,
                "rollback_needed": False,
                "deduction_completed": True,
                "eligible_items": [],
                "ineligible_items": ineligible,
                "line_items": all_items,
                "deduction_loop_count": deduction_loop_count,
            }

        deduct_payload = [
            {"sku": item["sku"], "quantity": item.get("quantity_ordered", 1), "product_id": item.get("product_id", "")}
            for item in items_to_deduct
        ]

        deduction_result = self.inventory_adapter.deduct_inventory(order_id, deduct_payload)
        success = deduction_result.get("success", False)
        tx_id = deduction_result.get("transaction_id", "")

        if success:
            logger.info(f"[{order_id}] Inventory deduction succeeded: tx={tx_id}")
            for item in items_to_deduct:
                try:
                    self.line_item_repo.update_deduction_status(
                        order_id=order_id,
                        item_id=item["item_id"],
                        quantity_deducted=item.get("quantity_ordered", 1),
                        deduction_status="DEDUCTED",
                    )
                except Exception as e:
                    logger.warning(f"[{order_id}] Could not persist deduction status to DB: {e}")

                try:
                    self.inv_tx_repo.record_transaction(
                        OrderInventoryTransaction(
                            order_id=order_id,
                            product_id=item.get("product_id", "PROD-UNKNOWN"),
                            sku=item["sku"],
                            transaction_type="DEDUCTION",
                            quantity=item.get("quantity_ordered", 1),
                            status="SUCCESS",
                            external_reference_id=tx_id,
                        )
                    )
                except Exception as e:
                    logger.warning(f"[{order_id}] Could not record inventory transaction to DB: {e}")

            # Update item states in memory
            for it in all_items:
                if any(ded.get("sku") == it.get("sku") for ded in items_to_deduct):
                    it["quantity_deducted"] = it.get("quantity_ordered", 1)
                    it["deduction_status"] = "DEDUCTED"

            try:
                self.order_repo.update_stage_and_status(
                    order_id=order_id,
                    current_stage="INVENTORY_DEDUCT",
                    status="RUNNING",
                    stage_version=stage_version,
                    deduction_completed=True,
                )
            except Exception as e:
                logger.warning(f"[{order_id}] Could not update order stage in DB: {e}")

            duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            try:
                self.checkpoint_repo.record_checkpoint(
                    NodeExecutionCheckpoint(
                        order_id=order_id,
                        node_name="inventory_deduct",
                        stage_version=stage_version,
                        execution_status="COMPLETED",
                        node_output_metadata={"transaction_id": tx_id, "deducted_count": len(items_to_deduct)},
                        duration_ms=duration_ms,
                    )
                )
            except Exception as e:
                logger.warning(f"[{order_id}] Could not record checkpoint in DB: {e}")

            return {
                "success": True,
                "deducted_count": len(items_to_deduct),
                "rollback_needed": False,
                "deduction_completed": True,
                "transaction_id": tx_id,
                "eligible_items": items_to_deduct,
                "ineligible_items": ineligible,
                "line_items": all_items,
                "deduction_loop_count": deduction_loop_count,
            }

        # -------------------------------------------------------------------------
        # Failure / Race Condition Handling
        # -------------------------------------------------------------------------
        failed_skus = deduction_result.get("failed_skus", [])
        error_reason = deduction_result.get("error_reason", "Deduction failed due to concurrent stock exhaustion")
        logger.warning(f"[{order_id}] Deduction failed on SKUs {failed_skus}: {error_reason}")

        new_eligible: List[Dict[str, Any]] = []
        new_ineligible: List[Dict[str, Any]] = list(ineligible)

        for item in items_to_deduct:
            sku = item.get("sku")
            if sku in failed_skus:
                try:
                    self.line_item_repo.update_deduction_status(
                        order_id=order_id,
                        item_id=item["item_id"],
                        quantity_deducted=0,
                        deduction_status="FAILED_OUT_OF_STOCK",
                    )
                    self.line_item_repo.update_inventory_assessment(
                        order_id=order_id,
                        item_id=item["item_id"],
                        quantity_available=0,
                        is_discontinued=False,
                        stock_status="OUT_OF_STOCK",
                    )
                except Exception as e:
                    logger.warning(f"[{order_id}] Could not update failed item in DB: {e}")

                try:
                    self.inv_tx_repo.record_transaction(
                        OrderInventoryTransaction(
                            order_id=order_id,
                            product_id=item.get("product_id", "PROD-UNKNOWN"),
                            sku=sku,
                            transaction_type="DEDUCTION",
                            quantity=item.get("quantity_ordered", 1),
                            status="FAILED",
                            reason=error_reason,
                            external_reference_id=tx_id,
                        )
                    )
                except Exception as e:
                    logger.warning(f"[{order_id}] Could not record failed transaction in DB: {e}")

                failed_item = dict(item)
                failed_item.update({
                    "quantity_available": 0,
                    "quantity_deducted": 0,
                    "stock_status": "OUT_OF_STOCK",
                    "deduction_status": "FAILED_OUT_OF_STOCK",
                })
                new_ineligible.append(failed_item)

                # Update in master line_items
                for it in all_items:
                    if it.get("sku") == sku:
                        it.update(failed_item)
            else:
                new_eligible.append(item)

        # Loop protection
        updated_loop_count = deduction_loop_count + 1
        max_loops_exceeded = updated_loop_count >= 2

        new_fulfillment = "NONE" if not new_eligible else "PARTIAL"

        duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
        try:
            self.checkpoint_repo.record_checkpoint(
                NodeExecutionCheckpoint(
                    order_id=order_id,
                    node_name="inventory_deduct",
                    stage_version=stage_version,
                    execution_status="ROLLBACK_TRIGGERED" if not max_loops_exceeded else "FAILED_MAX_LOOPS",
                    node_output_metadata={
                        "failed_skus": failed_skus,
                        "error_reason": error_reason,
                        "loop_count": updated_loop_count,
                        "max_loops_exceeded": max_loops_exceeded,
                    },
                    duration_ms=duration_ms,
                )
            )
        except Exception as e:
            logger.warning(f"[{order_id}] Could not record checkpoint in DB: {e}")

        return {
            "success": False,
            "deducted_count": len(new_eligible),
            "rollback_needed": not max_loops_exceeded,
            "deduction_completed": False,
            "deduction_loop_count": updated_loop_count,
            "human_in_loop": max_loops_exceeded,
            "human_review_reason": f"Concurrent stock shortage after {updated_loop_count} attempts: {error_reason}" if max_loops_exceeded else None,
            "failed_skus": failed_skus,
            "error_reason": error_reason,
            "eligible_items": new_eligible,
            "ineligible_items": new_ineligible,
            "line_items": all_items,
            "fulfillment_type": new_fulfillment,
        }
