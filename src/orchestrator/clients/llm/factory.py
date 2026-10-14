"""Multi-Model LLM factory with automatic cross-provider fallback."""

from typing import Optional
from src.orchestrator.clients.llm.base import BaseLLMClient
from src.orchestrator.clients.llm.claude_client import ClaudeClient
from src.orchestrator.clients.llm.gemini_client import GeminiClient
from src.orchestrator.config.settings import settings
from src.orchestrator.core.logging import logger


class MultiModelLLMClient(BaseLLMClient):
    """
    Orchestrates completions with automatic fallback between Gemini and Claude.
    """

    def __init__(
        self,
        primary_provider: Optional[str] = None,
        enable_fallback: Optional[bool] = None,
    ):
        self.primary_provider = (primary_provider or settings.DEFAULT_LLM_PROVIDER).lower()
        self.enable_fallback = enable_fallback if enable_fallback is not None else settings.ENABLE_LLM_FALLBACK

        self.gemini = GeminiClient()
        self.claude = ClaudeClient()

    def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """Executes prompt using primary provider, falling back on secondary if configured."""
        primary = self.gemini if self.primary_provider == "gemini" else self.claude
        secondary = self.claude if self.primary_provider == "gemini" else self.gemini
        primary_name = "Gemini" if self.primary_provider == "gemini" else "Claude"
        secondary_name = "Claude" if self.primary_provider == "gemini" else "Gemini"

        try:
            return primary.generate(prompt, system_instruction, temperature)
        except Exception as e:
            if not self.enable_fallback:
                logger.error(f"Primary LLM provider {primary_name} failed and fallback is disabled: {e}")
                raise

            logger.warning(
                f"Primary LLM {primary_name} failed ({e}). Automatically falling back to {secondary_name}..."
            )
            try:
                return secondary.generate(prompt, system_instruction, temperature)
            except Exception as sec_err:
                logger.error(f"Secondary LLM {secondary_name} also failed: {sec_err}")
                raise sec_err


def get_llm_client() -> BaseLLMClient:
    """Returns singleton/configured multi-model LLM client."""
    return MultiModelLLMClient()
