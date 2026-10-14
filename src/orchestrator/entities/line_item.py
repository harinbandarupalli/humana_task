"""Domain entity for order line items."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional
from uuid import UUID
from pydantic import Field
from src.orchestrator.entities.base import BaseEntity


class OrderLineItem(BaseEntity):
    """
    Domain entity mapping to `order_line_items` table.
    Represents an individual item in an order, tracking its stock and deduction state.
    """

    id: Optional[UUID] = Field(default=None, description="Surrogate primary key UUID")
    line_number: Optional[int] = Field(default=None, description="Sequential line item number")
    order_id: str = Field(..., description="Foreign key to order_orchestration_runs(order_id)")
    item_id: str = Field(..., description="Line item identifier from ORDER_DETAILS API")
    product_id: str = Field(..., description="Product catalog identifier")
    sku: str = Field(..., description="Stock keeping unit code")
    product_name: str = Field(..., description="Product title")
    quantity_ordered: int = Field(..., gt=0, description="Quantity requested by customer")
    quantity_available: int = Field(default=0, ge=0, description="Available quantity from inventory check")
    quantity_deducted: int = Field(default=0, ge=0, description="Quantity deducted from inventory")
    quantity_shipped: int = Field(default=0, ge=0, description="Quantity included in shipping manifest")
    unit_price: Decimal = Field(default=Decimal("0.00"), description="Unit price per item")
    is_discontinued: bool = Field(default=False, description="Discontinued catalog status")
    stock_status: str = Field(default="PENDING_CHECK", description="Inventory check status")
    deduction_status: str = Field(default="NOT_DEDUCTED", description="Inventory deduction status")
    shipping_status: str = Field(default="UNSHIPPED", description="Fulfillment status")
    item_metadata: Dict[str, Any] = Field(default_factory=dict, description="Custom line item metadata")
    created_at: Optional[datetime] = Field(default=None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(default=None, description="Last update timestamp")
