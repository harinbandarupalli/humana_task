"""Service for generating natural language explanations and operational dossiers using LLMs."""

from typing import Any, Dict, List, Optional
from src.orchestrator.clients.llm.base import BaseLLMClient
from src.orchestrator.clients.llm.factory import get_llm_client
from src.orchestrator.config.prompts import PromptManager, prompt_manager


class LLMReasoningService:
    """Orchestrates structured domain prompts across Gemini Flash and Claude via PromptManager."""

    def __init__(
        self,
        llm_client: Optional[BaseLLMClient] = None,
        prompts: Optional[PromptManager] = None,
    ):
        self.llm = llm_client or get_llm_client()
        self.prompts = prompts or prompt_manager

    def generate_ops_shortage_briefing(
        self,
        order_id: str,
        line_items: List[Dict[str, Any]],
        fulfillment_type: str,
        order_metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Generates an exhaustive, highly detailed operational dossier for human operations agents
        to investigate inventory shortages, partial balances, and discontinued items in external ERP/WMS.
        """
        order_meta = order_metadata or {}
        placed_at = order_meta.get("order_placed_at", "N/A")
        email = order_meta.get("customer_email", "N/A")
        shipping = order_meta.get("shipping_address", {})
        city = shipping.get("city", "Unknown")
        state = shipping.get("state", "Unknown")
        postal = shipping.get("postal_code", "")
        dest = f"{city}, {state} {postal}".strip()

        # Compute granular inventory health counts
        in_stock = sum(1 for it in line_items if it.get("stock_status") == "IN_STOCK" and not it.get("is_discontinued"))
        partial = sum(
            1 for it in line_items
            if it.get("stock_status") == "PARTIAL_STOCK"
            or (0 < it.get("quantity_available", 0) < it.get("quantity_ordered", 1))
        )
        oos = sum(
            1 for it in line_items
            if (it.get("stock_status") == "OUT_OF_STOCK" or it.get("quantity_available", 0) <= 0)
            and not it.get("is_discontinued")
        )
        disc = sum(1 for it in line_items if it.get("is_discontinued") or it.get("stock_status") == "DISCONTINUED")

        # Format tabular presentation and narratives
        items_table = self._build_ascii_table(line_items)
        shortages_detail = self._build_shortage_narrative(line_items)
        recommended_actions = self._build_recommended_actions(line_items, fulfillment_type)

        user_prompt, system_instruction = self.prompts.format_prompt(
            "ops_inventory_shortage_briefing",
            order_id=order_id,
            order_placed_at=placed_at,
            customer_email=email,
            destination=dest,
            fulfillment_type=fulfillment_type,
            total_items=len(line_items),
            in_stock_count=in_stock,
            partial_count=partial,
            oos_count=oos,
            disc_count=disc,
            line_items_table=items_table,
            shortages_detail=shortages_detail,
            recommended_actions=recommended_actions,
        )

        return self.llm.generate(prompt=user_prompt, system_instruction=system_instruction)

    def generate_out_of_stock_comment(
        self,
        order_id: str,
        out_of_stock_items: List[Dict[str, Any]],
        discontinued_items: List[Dict[str, Any]],
        fulfillment_type: str = "PARTIAL",
        order_metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Alias forwarding to generate_ops_shortage_briefing with consolidated items."""
        all_items = out_of_stock_items + discontinued_items
        return self.generate_ops_shortage_briefing(
            order_id=order_id,
            line_items=all_items,
            fulfillment_type=fulfillment_type,
            order_metadata=order_metadata,
        )

    def generate_address_issue_comment(
        self,
        order_id: str,
        address: Dict[str, Any],
        error_reason: str,
    ) -> str:
        """Generates operational summary for human review regarding invalid shipping address."""
        user_prompt, system_instruction = self.prompts.format_prompt(
            "shipping_address_issue_briefing",
            order_id=order_id,
            address=str(address),
            error_reason=error_reason,
        )
        return self.llm.generate(prompt=user_prompt, system_instruction=system_instruction)

    def generate_final_summary_report(
        self,
        order_id: str,
        fulfillment_type: str,
        shipped_items: List[Dict[str, Any]],
        unfulfilled_items: List[Dict[str, Any]],
        carrier_name: Optional[str] = None,
        tracking_number: Optional[str] = None,
    ) -> str:
        """Generates executive fulfillment summary report for completed workflow."""
        user_prompt, system_instruction = self.prompts.format_prompt(
            "final_order_fulfillment_summary",
            order_id=order_id,
            fulfillment_type=fulfillment_type,
            carrier_name=carrier_name or "N/A",
            tracking_number=tracking_number or "N/A",
            shipped_count=len(shipped_items),
            unfulfilled_count=len(unfulfilled_items),
        )
        return self.llm.generate(prompt=user_prompt, system_instruction=system_instruction)

    @staticmethod
    def _build_ascii_table(line_items: List[Dict[str, Any]]) -> str:
        header = f"  {'SKU':<16} {'PRODUCT NAME':<24} {'REQ':<4} {'AVAIL':<6} {'STATUS':<14} {'UNIT':<8} {'TOTAL':<8}"
        divider = "  " + "-" * 82
        rows = [header, divider]
        for it in line_items:
            sku = str(it.get("sku", ""))[:15]
            name = str(it.get("product_name", it.get("sku", "Unknown")))[:23]
            req = it.get("quantity_ordered", 1)
            avail = it.get("quantity_available", 0)
            status = str(it.get("stock_status", "UNKNOWN"))[:13]
            price = float(it.get("unit_price", 0.0))
            total = price * req
            rows.append(f"  {sku:<16} {name:<24} {req:<4} {avail:<6} {status:<14} ${price:<7.2f} ${total:<7.2f}")
        rows.append(divider)
        return "\n".join(rows)

    @staticmethod
    def _build_shortage_narrative(line_items: List[Dict[str, Any]]) -> str:
        lines = []
        for it in line_items:
            sku = it.get("sku", "UNKNOWN")
            name = it.get("product_name", sku)
            status = it.get("stock_status")
            req = it.get("quantity_ordered", 1)
            avail = it.get("quantity_available", 0)

            if it.get("is_discontinued") or status == "DISCONTINUED":
                lines.append(f"  • SKU {sku} ({name}): Permanently DISCONTINUED by manufacturer. Zero warehouse balance, no reorder.")
            elif status == "OUT_OF_STOCK" or avail <= 0:
                lines.append(f"  • SKU {sku} ({name}): Completely OUT OF STOCK (ordered: {req}, available: 0). Backorder required.")
            elif status == "PARTIAL_STOCK" or (0 < avail < req):
                lines.append(f"  • SKU {sku} ({name}): PARTIAL STOCK ONLY. Warehouse balance is {avail} units; shortfall of {req - avail} units.")
        return "\n".join(lines) if lines else "  • No item shortages or discontinued products detected in this order."

    @staticmethod
    def _build_recommended_actions(line_items: List[Dict[str, Any]], fulfillment_type: str) -> str:
        actions = []
        step = 1
        has_partial = any(
            it.get("stock_status") == "PARTIAL_STOCK"
            or (0 < it.get("quantity_available", 0) < it.get("quantity_ordered", 1))
            for it in line_items
        )
        has_oos = any(
            (it.get("stock_status") == "OUT_OF_STOCK" or it.get("quantity_available", 0) <= 0)
            for it in line_items
            if not it.get("is_discontinued")
        )
        has_disc = any(it.get("is_discontinued") or it.get("stock_status") == "DISCONTINUED" for it in line_items)

        if fulfillment_type == "PARTIAL":
            actions.append(f"  [Step {step}] In WMS: Reserve and wave-pick currently available units for priority partial shipment dispatch.")
            step += 1
        if has_partial:
            actions.append(f"  [Step {step}] In ERP: Check secondary regional distribution centers (DCs) or incoming purchase orders (POs) for stock replenishment.")
            step += 1
        if has_disc:
            actions.append(f"  [Step {step}] In Catalog Admin: Check approved superseding replacement SKU for discontinued items or issue customer refund.")
            step += 1
        if has_oos:
            actions.append(f"  [Step {step}] In Order Management: Update backorder release schedule and notify client relationship specialist.")
            step += 1
        if not actions:
            actions.append("  [Step 1] In WMS: All items fully available. Proceed with standard batch picking and carrier staging.")
        return "\n".join(actions)
