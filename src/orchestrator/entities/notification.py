"""Domain entity for order notifications."""

from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import Field
from src.orchestrator.entities.base import BaseEntity


class OrderNotification(BaseEntity):
    """
    Domain entity mapping to `order_notifications` table.
    Enforces idempotency to guarantee emails/alerts are dispatched once per alert condition.
    """

    id: Optional[UUID] = Field(default=None, description="Surrogate primary key UUID")
    notification_number: Optional[int] = Field(default=None, description="Chronological sequence number")
    order_id: str = Field(..., description="Foreign key to order_orchestration_runs(order_id)")
    node_name: str = Field(..., description="LangGraph node triggering notification")
    idempotency_key: str = Field(..., description="Unique hash preventing duplicate delivery")
    recipient_email: str = Field(..., description="Target recipient email address")
    notification_type: str = Field(..., description="Notification category code")
    subject: str = Field(..., description="Email subject line")
    body_text: str = Field(..., description="Complete email body text")
    status: str = Field(default="PENDING", description="Delivery status (PENDING, SENT, FAILED)")
    sent_at: Optional[datetime] = Field(default=None, description="Delivery completion timestamp")
    retry_count: int = Field(default=0, description="Dispatch retry attempt counter")
    error_log: Optional[str] = Field(default=None, description="Provider error log if delivery failed")
    created_at: Optional[datetime] = Field(default=None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(default=None, description="Update timestamp")
