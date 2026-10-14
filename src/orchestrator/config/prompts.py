"""Centralized Prompt Registry Manager for LLM templates.

Loads prompt templates from local prompts.json registry with future extensibility
for dynamic retrieval from an Observability Hub / Prompt Management Service.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from src.orchestrator.core.logging import logger


class PromptManager:
    """Manages prompt template loading, caching, and dynamic keyword formatting."""

    _default_instance: Optional["PromptManager"] = None

    def __init__(self, file_path: Optional[Path] = None):
        self.file_path = file_path or (Path(__file__).parent / "prompts.json")
        self._prompts_cache: Dict[str, Any] = {}
        self._load_prompts()

    def _load_prompts(self) -> None:
        """Loads prompt definitions from the JSON registry."""
        if self.file_path.exists():
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._prompts_cache = data.get("prompts", {})
                    logger.debug(f"[PromptManager] Loaded {len(self._prompts_cache)} prompt templates from {self.file_path.name}")
            except Exception as e:
                logger.error(f"[PromptManager] Failed loading prompt registry from {self.file_path}: {e}")
        else:
            logger.warning(f"[PromptManager] Registry file not found at {self.file_path}")

    def get_prompt(self, prompt_key: str) -> Dict[str, str]:
        """Retrieves raw prompt metadata, system instruction, and template string."""
        prompt_data = self._prompts_cache.get(prompt_key)
        if not prompt_data:
            raise KeyError(f"Prompt '{prompt_key}' not found in prompts registry.")
        return prompt_data

    def format_prompt(self, prompt_key: str, **kwargs: Any) -> Tuple[str, str]:
        """
        Formats the user template with provided keyword arguments.

        Returns:
            Tuple of (formatted_user_prompt, system_instruction)
        """
        prompt_data = self.get_prompt(prompt_key)
        template = prompt_data.get("template", "")
        system_instruction = prompt_data.get("system_instruction", "")

        try:
            formatted_prompt = template.format(**kwargs)
        except KeyError as e:
            logger.warning(f"[PromptManager] Missing placeholder key {e} when formatting '{prompt_key}'")
            formatted_prompt = template

        return formatted_prompt, system_instruction

    @classmethod
    def get_instance(cls) -> "PromptManager":
        """Singleton accessor for PromptManager."""
        if cls._default_instance is None:
            cls._default_instance = cls()
        return cls._default_instance


prompt_manager = PromptManager.get_instance()
