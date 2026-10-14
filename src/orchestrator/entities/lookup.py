"""Domain entity for status and type lookups."""

from datetime import datetime
from typing import Optional
from pydantic import Field
from src.orchestrator.entities.base import BaseEntity


class LookupCode(BaseEntity):
    """Represents a code record from reference lookup tables."""

    code: str = Field(..., description="Unique alphanumeric code key")
    display_name: str = Field(..., description="Human-readable label")
    description: Optional[str] = Field(default=None, description="Detailed explanation of code")
    is_terminal: Optional[bool] = Field(default=False, description="Flag for terminal lifecycle status")
    is_active: bool = Field(default=True, description="Active toggle")
    sort_order: int = Field(default=10, description="Display order")
    created_at: Optional[datetime] = Field(default=None, description="Creation timestamp")
