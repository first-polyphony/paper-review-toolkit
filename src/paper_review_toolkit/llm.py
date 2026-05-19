"""LLM client wrapper using Anthropic SDK directly."""

from __future__ import annotations

import json
import os
from typing import Any

import anthropic


class LLMClient:
    """Simple wrapper around the Anthropic SDK for paper review tasks."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-sonnet-4-20250514",
    ):
        """Initialize the client.

        Args:
            api_key: Anthropic API key. Defaults to ANTHROPIC_API_KEY env var.
            model: Model ID to use.
        """
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError(
                "API key required. Set ANTHROPIC_API_KEY env var or pass api_key."
            )
        self.model = model
        self.client = anthropic.Anthropic(api_key=self.api_key)

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
        """
        messages = [{"role": "user", "content": prompt}]

        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system or "",
            messages=messages,
            temperature=temperature,
        )

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
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]

        return json.loads(text.strip())


def get_client(
    api_key: str | None = None,
    model: str = "claude-sonnet-4-20250514",
) -> LLMClient:
    """Factory function to create an LLM client.

    Args:
        api_key: Anthropic API key.
        model: Model ID.

    Returns:
        Configured LLMClient instance.
    """
    return LLMClient(api_key=api_key, model=model)
