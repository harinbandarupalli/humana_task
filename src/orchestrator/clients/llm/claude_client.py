"""Anthropic Claude LLM client supporting Claude 3.7 / 3.5 Sonnet."""

from typing import Optional
from src.orchestrator.clients.llm.base import BaseLLMClient
from src.orchestrator.config.settings import settings
from src.orchestrator.core.logging import logger

try:
    import anthropic
    ANTHROPIC_SDK_AVAILABLE = True
except ImportError:
    ANTHROPIC_SDK_AVAILABLE = False


class ClaudeClient(BaseLLMClient):
    """Client for Anthropic Claude models."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.ANTHROPIC_API_KEY
        self.model = model or settings.CLAUDE_MODEL
        self._client = None

        if ANTHROPIC_SDK_AVAILABLE and self.api_key:
            try:
                self._client = anthropic.Anthropic(api_key=self.api_key)
            except Exception as e:
                logger.warning(f"Could not initialize Anthropic client: {e}")

    def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """Generates natural language response using Anthropic Claude."""
        temp = temperature if temperature is not None else settings.CLAUDE_TEMPERATURE

        if self._client:
            try:
                kwargs = {
                    "model": self.model,
                    "max_tokens": 1024,
                    "temperature": temp,
                    "messages": [{"role": "user", "content": prompt}],
                }
                if system_instruction:
                    kwargs["system"] = system_instruction

                response = self._client.messages.create(**kwargs)
                return response.content[0].text if response.content else ""
            except Exception as e:
                logger.error(f"Claude API invocation error: {e}")
                raise

        # Mock / Fallback simulator for offline development
        logger.info(f"[Mock Claude] Simulating response for prompt: {prompt[:60]}...")
        return prompt
