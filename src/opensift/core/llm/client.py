"""LLM Client — OpenAI-compatible wrapper for model calls.

Supports any OpenAI-compatible API endpoint (OpenAI, WisModel, vLLM, Ollama, etc.)
with both streaming and non-streaming modes.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from openai import AsyncOpenAI

if TYPE_CHECKING:
    from opensift.config.settings import AISettings

logger = logging.getLogger(__name__)


class LLMClient:
    """Async LLM client wrapping the OpenAI-compatible API.

    Handles model calls for both criteria generation (planner) and
    paper validation (verifier). Automatically parses JSON responses.

    Args:
        settings: AI configuration with api_key, base_url, model names, etc.
    """

    def __init__(self, settings: AISettings) -> None:
        self._settings = settings
        self._client = AsyncOpenAI(
            api_key=settings.api_key,
            base_url=settings.base_url,
        )

    async def chat_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        """Send a chat completion request and parse the JSON response.

        Args:
            system_prompt: System message content.
            user_prompt: User message content.
            model: Model name override (defaults to settings).
            temperature: Temperature override.
            max_tokens: Max tokens override.

        Returns:
            Parsed JSON dict from the model response.

        Raises:
            LLMError: If the model call or JSON parsing fails.
        """
        model = model or self._settings.model_planner
        temperature = temperature if temperature is not None else self._settings.temperature
        max_tokens = max_tokens or self._settings.max_tokens

        try:
            response = await self._client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                stream=False,
            )

            content = response.choices[0].message.content
            if content is None:
                raise LLMError("Model returned empty content")

            logger.debug("LLM raw response: %s", content[:500])

            # Strip markdown code fences if present
            content = self._strip_code_fences(content)

            return json.loads(content)

        except json.JSONDecodeError as e:
            logger.error("Failed to parse LLM JSON response: %s", e)
            raise LLMError(f"Invalid JSON from LLM: {e}") from e
        except Exception as e:
            if isinstance(e, LLMError):
                raise
            logger.error("LLM call failed: %s", e)
            raise LLMError(f"LLM call failed: {e}") from e

    async def chat_raw(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Send a chat completion request and return raw text response.

        Args:
            system_prompt: System message content.
            user_prompt: User message content.
            model: Model name override.
            temperature: Temperature override.
            max_tokens: Max tokens override.

        Returns:
            Raw text content from the model.

        Raises:
            LLMError: If the model call fails.
        """
        model = model or self._settings.model_planner
        temperature = temperature if temperature is not None else self._settings.temperature
        max_tokens = max_tokens or self._settings.max_tokens

        try:
            response = await self._client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                stream=False,
            )

            content = response.choices[0].message.content
            if content is None:
                raise LLMError("Model returned empty content")

            return content

        except Exception as e:
            if isinstance(e, LLMError):
                raise
            logger.error("LLM call failed: %s", e)
            raise LLMError(f"LLM call failed: {e}") from e

    @staticmethod
    def _strip_code_fences(text: str) -> str:
        """Remove markdown code fences from LLM output.

        Handles patterns like ```json ... ``` or ``` ... ```
        """
        text = text.strip()
        if text.startswith("```"):
            # Remove opening fence (possibly with language tag)
            first_newline = text.find("\n")
            if first_newline != -1:
                text = text[first_newline + 1 :]
            # Remove closing fence
            if text.endswith("```"):
                text = text[:-3]
        return text.strip()


class LLMError(Exception):
    """Raised when an LLM call or response parsing fails."""
