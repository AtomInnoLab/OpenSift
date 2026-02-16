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


def _diagnose_api_error(e: Any, base_url: str, model: str) -> str:
    """Produce a human-readable diagnosis for common API status errors."""
    code = e.status_code
    body = getattr(e, "body", None) or {}
    inner_code = body.get("error", {}).get("code", "") if isinstance(body, dict) else ""

    if code == 401:
        return (
            f"Authentication failed (HTTP 401): API key is invalid or missing.\n"
            f"  → Check OPENSIFT_AI__API_KEY in your .env file.\n"
            f"  → Endpoint: {base_url}"
        )
    if code == 403:
        return (
            f"Permission denied (HTTP 403): API key is valid but does NOT have access "
            f"to this resource / model.\n"
            f"  → API key works for other resources (e.g. ScholarSearch) but is "
            f"forbidden for the LLM endpoint.\n"
            f"  → Endpoint: {base_url}/chat/completions\n"
            f"  → Model: {model}\n"
            f"  → Inner code: {inner_code}\n"
            f"  Fix options:\n"
            f"    1) Request WisModel access for this API key from the API Hub admin.\n"
            f"    2) Use a different API key that has WisModel permissions.\n"
            f"    3) Switch to an alternative LLM provider by editing .env:\n"
            f"       OPENSIFT_AI__PROVIDER=openai\n"
            f"       OPENSIFT_AI__API_KEY=sk-your-openai-key\n"
            f"       OPENSIFT_AI__BASE_URL=https://api.openai.com/v1\n"
            f"       OPENSIFT_AI__MODEL_PLANNER=gpt-4o-mini\n"
            f"       OPENSIFT_AI__MODEL_VERIFIER=gpt-4o-mini\n"
            f"    4) Use a local LLM (Ollama / vLLM) — see opensift-config.example.yaml"
        )
    if code == 404:
        return (
            f"Not found (HTTP 404): The model or endpoint does not exist.\n"
            f"  → Endpoint: {base_url}/chat/completions\n"
            f"  → Model: {model}\n"
            f"  → Check that OPENSIFT_AI__BASE_URL and OPENSIFT_AI__MODEL_PLANNER are correct."
        )
    if code == 429:
        return (
            f"Rate limited (HTTP 429): Too many requests.\n"
            f"  → Wait and retry, or reduce concurrency.\n"
            f"  → Endpoint: {base_url}"
        )
    return f"API error (HTTP {code}): {e}\n  → Endpoint: {base_url}/chat/completions\n  → Model: {model}"


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
        masked_key = settings.api_key[:8] + "..." + settings.api_key[-4:] if len(settings.api_key) > 12 else "***"
        logger.info(
            "LLM client created: base_url=%s, api_key=%s, provider=%s",
            settings.base_url,
            masked_key,
            settings.provider,
        )

    async def verify_connection(self, model: str | None = None) -> bool:
        """Send a lightweight test request to verify API connectivity and auth.

        Returns True if the connection is valid, False otherwise.
        Logs detailed diagnostics on failure.
        """
        model = model or self._settings.model_planner
        full_url = f"{self._settings.base_url}/chat/completions"
        logger.info("Verifying LLM connectivity: url=%s, model=%s", full_url, model)

        try:
            response = await self._client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1,
                stream=False,
            )
            logger.info(
                "LLM connectivity OK: model=%s, response_model=%s",
                model,
                response.model,
            )
            return True
        except Exception as e:
            from openai import APIStatusError

            if isinstance(e, APIStatusError):
                diagnosis = _diagnose_api_error(e, self._settings.base_url, model)
                logger.error("LLM connectivity check FAILED:\n%s", diagnosis)
            else:
                logger.error(
                    "LLM connectivity check FAILED: url=%s, model=%s, error_type=%s, error=%s",
                    full_url,
                    model,
                    type(e).__name__,
                    e,
                )
            return False

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

        full_url = f"{self._settings.base_url}/chat/completions"
        logger.info(
            "LLM chat_json request: url=%s, model=%s, temperature=%s, max_tokens=%s, "
            "system_prompt_len=%d, user_prompt_len=%d",
            full_url,
            model,
            temperature,
            max_tokens,
            len(system_prompt),
            len(user_prompt),
        )

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

            logger.info(
                "LLM chat_json response OK: model=%s, usage=%s, content_len=%d",
                response.model,
                response.usage.model_dump() if response.usage else "N/A",
                len(content),
            )
            logger.debug("LLM raw response: %s", content[:500])

            # Strip markdown code fences if present
            content = self._strip_code_fences(content)

            return json.loads(content)

        except json.JSONDecodeError as e:
            logger.error("Failed to parse LLM JSON response: %s", e)
            raise LLMError(f"Invalid JSON from LLM: {e}") from e
        except LLMError:
            raise
        except Exception as e:
            from openai import APIStatusError

            if isinstance(e, APIStatusError):
                diagnosis = _diagnose_api_error(e, self._settings.base_url, model)
                logger.error("LLM API error:\n%s", diagnosis)
                raise LLMError(f"LLM API error (HTTP {e.status_code}): {diagnosis}") from e
            logger.error(
                "LLM call FAILED: url=%s, model=%s, error_type=%s, error=%s",
                full_url,
                model,
                type(e).__name__,
                e,
            )
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

        full_url = f"{self._settings.base_url}/chat/completions"
        logger.info(
            "LLM chat_raw request: url=%s, model=%s, temperature=%s, max_tokens=%s, "
            "system_prompt_len=%d, user_prompt_len=%d",
            full_url,
            model,
            temperature,
            max_tokens,
            len(system_prompt),
            len(user_prompt),
        )

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

            logger.info(
                "LLM chat_raw response OK: model=%s, usage=%s, content_len=%d",
                response.model,
                response.usage.model_dump() if response.usage else "N/A",
                len(content),
            )

            return content

        except LLMError:
            raise
        except Exception as e:
            from openai import APIStatusError

            if isinstance(e, APIStatusError):
                diagnosis = _diagnose_api_error(e, self._settings.base_url, model)
                logger.error("LLM API error:\n%s", diagnosis)
                raise LLMError(f"LLM API error (HTTP {e.status_code}): {diagnosis}") from e
            logger.error(
                "LLM call FAILED: url=%s, model=%s, error_type=%s, error=%s",
                full_url,
                model,
                type(e).__name__,
                e,
            )
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
