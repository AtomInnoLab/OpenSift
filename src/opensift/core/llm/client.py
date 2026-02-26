"""WisModel Client — wrapper for WisModel API calls.

Communicates with the WisModel API (OpenAI-compatible endpoint) for both
query planning and result verification tasks.
"""

from __future__ import annotations

import json
import logging
import re
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
            f"to WisModel.\n"
            f"  → API key may work for other resources (e.g. ScholarSearch) but is "
            f"forbidden for the WisModel endpoint.\n"
            f"  → Endpoint: {base_url}/chat/completions\n"
            f"  → Model: {model}\n"
            f"  → Inner code: {inner_code}\n"
            f"  Fix options:\n"
            f"    1) Request WisModel access for this API key from the API Hub admin.\n"
            f"    2) Use a different API key that has WisModel permissions."
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
            "WisModel client created: base_url=%s, api_key=%s",
            settings.base_url,
            masked_key,
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
        max_retries: int = 1,
    ) -> dict[str, Any]:
        """Send a chat completion request and parse the JSON response.

        If the LLM returns malformed JSON, attempts automatic repair.
        If repair fails, retries the request up to *max_retries* times with
        ``temperature=0`` to encourage deterministic output.

        Args:
            system_prompt: System message content.
            user_prompt: User message content.
            model: Model name override (defaults to settings).
            temperature: Temperature override.
            max_tokens: Max tokens override.
            max_retries: Number of retry attempts after JSON parse failure.

        Returns:
            Parsed JSON dict from the model response.

        Raises:
            LLMError: If the model call or JSON parsing fails after all retries.
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

        last_error: Exception | None = None
        for attempt in range(1 + max_retries):
            try:
                cur_temp = temperature if attempt == 0 else 0.0
                response = await self._client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=cur_temp,
                    max_tokens=max_tokens,
                    stream=False,
                )

                content = response.choices[0].message.content
                if content is None:
                    raise LLMError("Model returned empty content")

                logger.info(
                    "LLM chat_json response OK: model=%s, usage=%s, content_len=%d, attempt=%d",
                    response.model,
                    response.usage.model_dump() if response.usage else "N/A",
                    len(content),
                    attempt + 1,
                )
                logger.debug("LLM raw response: %s", content[:500])

                content = self._strip_code_fences(content)

                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    repaired = self._repair_json(content)
                    if repaired is not None:
                        logger.warning(
                            "LLM returned malformed JSON (attempt %d), auto-repaired successfully",
                            attempt + 1,
                        )
                        return repaired
                    logger.warning(
                        "LLM returned malformed JSON (attempt %d/%d), repair failed. Content preview: %s",
                        attempt + 1,
                        1 + max_retries,
                        content[:300],
                    )
                    last_error = LLMError("Invalid JSON from LLM after repair attempt")

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

        raise last_error or LLMError("chat_json failed after all retries")

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
            first_newline = text.find("\n")
            if first_newline != -1:
                text = text[first_newline + 1 :]
            if text.endswith("```"):
                text = text[:-3]
        return text.strip()

    @staticmethod
    def _repair_json(text: str) -> dict[str, Any] | None:
        """Attempt to repair common LLM JSON formatting issues.

        Handles:
        - Trailing commas before ``}`` or ``]``
        - Missing commas between values / object entries
        - Unescaped newlines inside string values
        - Truncated JSON (unclosed braces/brackets)
        - Leading/trailing non-JSON text surrounding the object

        Returns the parsed dict on success, or ``None`` if repair fails.
        """
        # Extract the outermost JSON object if surrounded by text
        brace_start = text.find("{")
        if brace_start == -1:
            return None
        text = text[brace_start:]

        # Close any unclosed braces / brackets
        open_b = text.count("{") - text.count("}")
        open_sq = text.count("[") - text.count("]")
        if open_b > 0 or open_sq > 0:
            text = text.rstrip().rstrip(",")
            text += "]" * max(open_sq, 0)
            text += "}" * max(open_b, 0)

        # Remove trailing commas before } or ]
        text = re.sub(r",\s*([}\]])", r"\1", text)

        # Replace unescaped control characters inside strings
        text = text.replace("\t", "\\t")

        # Try parsing after basic fixes
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Missing commas: }" or ]" or ""{  →  insert comma
        text = re.sub(r'("\s*)\n(\s*")', r"\1,\n\2", text)
        text = re.sub(r"(})\s*({)", r"\1,\2", text)
        text = re.sub(r"(])\s*(\[)", r"\1,\2", text)
        text = re.sub(r'(")\s*({)', r"\1,\2", text)
        text = re.sub(r"(})\s*(\")", r"\1,\2", text)

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Replace unescaped literal newlines inside JSON strings
        def _escape_newlines_in_strings(s: str) -> str:
            result: list[str] = []
            in_string = False
            escaped = False
            for ch in s:
                if escaped:
                    result.append(ch)
                    escaped = False
                    continue
                if ch == "\\":
                    escaped = True
                    result.append(ch)
                    continue
                if ch == '"':
                    in_string = not in_string
                if in_string and ch == "\n":
                    result.append("\\n")
                    continue
                result.append(ch)
            return "".join(result)

        text = _escape_newlines_in_strings(text)

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None


class LLMError(Exception):
    """Raised when an LLM call or response parsing fails."""
