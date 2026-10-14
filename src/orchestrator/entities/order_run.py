"""Domain entity for order orchestration runs."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional
from pydantic import Field
from src.orchestrator.entities.base import BaseEntity


class OrderOrchestrationRun(BaseEntity):
    """
    Domain entity mapping to `order_orchestration_runs` table.
    Represents the master lifecycle of an order pipeline in LangGraph.
    """

    order_id: str = Field(..., description="Unique business order identifier; primary key")
    thread_id: str = Field(..., description="LangGraph thread identifier")
    user_id: str = Field(..., description="Customer identifier")
    customer_email: str = Field(..., description="Customer contact email")
    customer_phone: Optional[str] = Field(default=None, description="Customer phone number")
    order_placed_at: datetime = Field(..., description="Order placement timestamp")
    order_type: str = Field(default="STANDARD", description="Order category (STANDARD, PRE_ORDER, etc.)")
    payment_status: str = Field(default="PENDING", description="Payment settlement status")
    current_stage: str = Field(default="INGESTION", description="Current executing LangGraph node")
    status: str = Field(default="PENDING", description="High-level workflow lifecycle status")
    fulfillment_type: str = Field(default="NONE", description="Fulfillment classification (NONE, FULL, PARTIAL)")
    human_in_loop: bool = Field(default=False, description="True if manual operator review is flagged")
    human_review_reason: Optional[str] = Field(default=None, description="Reason for operator review")
    is_duplicate: bool = Field(default=False, description="Duplicate detection flag")
    deduction_completed: bool = Field(default=False, description="Physical inventory deduction completed flag")
    shipping_completed: bool = Field(default=False, description="Carrier shipment completed flag")
    currency: str = Field(default="USD", description="Three-letter ISO currency code")
    total_amount: Decimal = Field(default=Decimal("0.00"), description="Total order amount")
    shipping_address: Dict[str, Any] = Field(default_factory=dict, description="Destination shipping address JSON")
    billing_address: Dict[str, Any] = Field(default_factory=dict, description="Billing address JSON")
    carrier_name: Optional[str] = Field(default=None, description="Assigned shipping carrier")
    tracking_number: Optional[str] = Field(default=None, description="Carrier tracking number")
    llm_summary_report: Optional[str] = Field(default=None, description="Final LLM summary narrative")
    stage_version: int = Field(default=1, description="Sequential stage version counter")
    created_at: Optional[datetime] = Field(default=None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(default=None, description="Last update timestamp")
