"""LLM client wrapper using Anthropic SDK directly."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import anthropic

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-sonnet-4-20250514"


class LLMClient:
    """Async wrapper around the Anthropic SDK for paper review tasks."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ):
        """Initialize the client.

        Args:
            api_key: Anthropic API key. Defaults to ANTHROPIC_API_KEY env var.
            model: Model ID to use. Defaults to PAPER_REVIEW_MODEL env var or claude-sonnet-4.
        """
        resolved_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not resolved_key:
            raise ValueError(
                "API key required. Set ANTHROPIC_API_KEY env var or pass api_key."
            )
        self.model = model or os.environ.get("PAPER_REVIEW_MODEL", DEFAULT_MODEL)
        self._client = anthropic.AsyncAnthropic(api_key=resolved_key)

    async def complete(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.3,
    ) -> str:
        """Generate a completion.

        Args:
            prompt: User message content.
            system: System prompt.
            max_tokens: Maximum tokens to generate.
            temperature: Sampling temperature.

        Returns:
            Generated text.

        Raises:
            anthropic.APIError: On API errors.
            ValueError: On empty response.
        """
        messages = [{"role": "user", "content": prompt}]

        try:
            response = await self._client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system or "",
                messages=messages,
                temperature=temperature,
            )
        except anthropic.APIConnectionError as e:
            logger.error("API connection failed: %s", e, exc_info=True)
            raise
        except anthropic.AuthenticationError as e:
            logger.error("API authentication failed: %s", e, exc_info=True)
            raise

        if not response.content or not response.content[0].text:
            raise ValueError("Empty response from API")

        return response.content[0].text

    async def complete_json(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.3,
    ) -> dict[str, Any]:
        """Generate a completion and parse as JSON.

        Args:
            prompt: User message content.
            system: System prompt.
            max_tokens: Maximum tokens to generate.
            temperature: Sampling temperature.

        Returns:
            Parsed JSON dict.

        Raises:
            ValueError: On invalid JSON response.
        """
        text = await self.complete(
            prompt=prompt,
            system=system,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        text = text.strip()

        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]

        if text.endswith("```"):
            text = text[:-3]

        text = text.strip()
        if not text:
            raise ValueError("Empty JSON response after stripping markdown")

        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.error("JSON parse error: %s\nResponse was: %s", e, text[:500], exc_info=True)
            raise ValueError(f"Invalid JSON in API response: {e}") from e


def get_client(
    api_key: str | None = None,
    model: str | None = None,
) -> LLMClient:
    """Factory function to create an LLM client.

    Args:
        api_key: Anthropic API key.
        model: Model ID.

    Returns:
        Configured LLMClient instance.
    """
    return LLMClient(api_key=api_key, model=model)
