"""Base entity class for domain models."""

from datetime import datetime
from typing import Any, Dict
from pydantic import BaseModel, ConfigDict


class BaseEntity(BaseModel):
    """Base Pydantic model for all domain entities."""

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        validate_assignment=True,
    )

    def to_dict(self) -> Dict[str, Any]:
        """Serializes entity to dictionary."""
        return self.model_dump()
