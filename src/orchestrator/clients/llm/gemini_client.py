"""Google Gemini LLM client supporting Gemini Flash models."""

from typing import Optional
from src.orchestrator.clients.llm.base import BaseLLMClient
from src.orchestrator.config.settings import settings
from src.orchestrator.core.logging import logger

try:
    from google import genai
    from google.genai import types
    GEMINI_SDK_AVAILABLE = True
except ImportError:
    GEMINI_SDK_AVAILABLE = False


class GeminiClient(BaseLLMClient):
    """Client for Google Gemini (defaults to Gemini 3.8 / 2.5 Flash)."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model = model or settings.GEMINI_MODEL
        self._client = None

        if GEMINI_SDK_AVAILABLE and self.api_key:
            try:
                self._client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.warning(f"Could not initialize Google GenAI client: {e}")

    def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """Generates natural language response using Gemini Flash."""
        temp = temperature if temperature is not None else settings.GEMINI_TEMPERATURE

        if self._client:
            try:
                config = types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=temp,
                )
                response = self._client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=config,
                )
                return response.text or ""
            except Exception as e:
                logger.error(f"Gemini API invocation error: {e}")
                raise

        # Mock / Fallback simulator for offline development
        logger.info(f"[Mock Gemini] Simulating response for prompt: {prompt[:60]}...")
        return prompt
