"""Domain entity for inventory transactions."""

from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import Field
from src.orchestrator.entities.base import BaseEntity


class OrderInventoryTransaction(BaseEntity):
    """
    Domain entity mapping to `order_inventory_transactions` table.
    Immutable ledger of physical inventory reservations, deductions, and rollback releases.
    """

    id: Optional[UUID] = Field(default=None, description="Surrogate primary key UUID")
    tx_number: Optional[int] = Field(default=None, description="Chronological transaction sequence number")
    order_id: str = Field(..., description="Foreign key to order_orchestration_runs(order_id)")
    product_id: str = Field(..., description="Catalog product identifier")
    sku: str = Field(..., description="Stock keeping unit code")
    transaction_type: str = Field(..., description="DEDUCTION or ROLLBACK_RELEASE")
    quantity: int = Field(..., gt=0, description="Number of units affected")
    external_reference_id: Optional[str] = Field(default=None, description="Inventory system confirmation ID")
    status: str = Field(..., description="SUCCESS or FAILED")
    reason: Optional[str] = Field(default=None, description="Failure diagnosis or operational note")
    created_at: Optional[datetime] = Field(default=None, description="Transaction timestamp")
