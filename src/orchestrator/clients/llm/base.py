"""Abstract base class for LLM clients."""

from abc import ABC, abstractmethod
from typing import Optional


class BaseLLMClient(ABC):
    """Unified interface for LLM completions."""

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """Generates completion text from prompt."""
        pass
