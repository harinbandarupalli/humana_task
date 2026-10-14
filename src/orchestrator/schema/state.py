"""LangGraph Orchestrator State definitions, Stage Enums, and Item models."""

from enum import Enum
import operator
from typing import Annotated, Any, Dict, List, Optional, TypedDict


class WorkflowStage(str, Enum):
    """Lifecycle stages matching workflow_stage_lookup in PostgreSQL."""
    INGESTION = "INGESTION"
    INVENTORY_CHECK = "INVENTORY_CHECK"
    NOTIFICATION_REVIEW = "NOTIFICATION_REVIEW"
    INVENTORY_DEDUCT = "INVENTORY_DEDUCT"
    SHIPPING_FULFILLMENT = "SHIPPING_FULFILLMENT"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class OrderStatus(str, Enum):
    """Business status matching order_status_lookup in PostgreSQL."""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    DUPLICATE = "DUPLICATE"
    DEFERRED_PRE_ORDER = "DEFERRED_PRE_ORDER"
    WAITING_HUMAN_REVIEW = "WAITING_HUMAN_REVIEW"
    PARTIALLY_SHIPPED = "PARTIALLY_SHIPPED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class StockStatus(str, Enum):
    """Item inventory availability matching stock_status_lookup."""
    PENDING_CHECK = "PENDING_CHECK"
    IN_STOCK = "IN_STOCK"
    OUT_OF_STOCK = "OUT_OF_STOCK"
    PARTIAL_STOCK = "PARTIAL_STOCK"
    DISCONTINUED = "DISCONTINUED"


class DeductionStatus(str, Enum):
    """Physical deduction state matching deduction_status_lookup."""
    NOT_DEDUCTED = "NOT_DEDUCTED"
    DEDUCTED = "DEDUCTED"
    FAILED_OUT_OF_STOCK = "FAILED_OUT_OF_STOCK"
    ROLLED_BACK = "ROLLED_BACK"


class OrderLineItem(TypedDict):
    """Granular state for an individual order line item."""
    item_id: str
    product_id: str
    sku: str
    product_name: str
    quantity_ordered: int
    quantity_available: int
    quantity_deducted: int
    quantity_shipped: int
    unit_price: float
    is_discontinued: bool
    stock_status: str
    deduction_status: str
    shipping_status: str
    item_metadata: Dict[str, Any]


class OrchestratorState(TypedDict):
    """
    Main state schema passed between LangGraph nodes.
    Uniquely identified by order_id (which acts as thread_id).
    """
    order_id: str
    thread_id: str
    user_id: str
    customer_email: str
    customer_phone: Optional[str]
    order_placed_at: str
    order_type: str
    payment_status: str
    current_stage: str
    status: str
    fulfillment_type: str
    stage_version: int

    # Flags & Controls
    is_duplicate: bool
    is_pre_order: bool
    human_in_loop: bool
    human_review_reason: Optional[str]
    deduction_completed: bool
    rollback_needed: bool
    deduction_loop_count: int
    shipping_completed: bool

    # Payloads & Items
    line_items: List[OrderLineItem]
    eligible_items: List[OrderLineItem]
    ineligible_items: List[OrderLineItem]
    shipping_address: Dict[str, Any]
    billing_address: Dict[str, Any]
    carrier_name: Optional[str]
    tracking_number: Optional[str]

    # LLM & Communication
    llm_comments: Annotated[List[str], operator.add]
    llm_summary_report: Optional[str]
    email_sent: bool

    # Audit & History
    stage_history: Annotated[List[str], operator.add]
    logs: Annotated[List[str], operator.add]
    error: Optional[str]
