"""
Anthropic Claude client using the Anthropic SDK with structured output.

Uses claude-haiku-4-5-20251001 by default (configurable via agents.yaml).
"""

import logging
from typing import TypeVar

from pydantic import BaseModel

from src.agents.llm.base_llm_client import BaseLLMClient
from src.configs.settings import get_settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class AnthropicLLMClient(BaseLLMClient):
    """
    Anthropic Claude client for enrichment agents.

    Uses the Anthropic SDK directly with tool_use for structured output.
    Lazy initialization — only loads SDK if an API key is available.
    """

    provider = "anthropic"

    def __init__(
        self,
        model_name: str = "claude-haiku-4-5-20251001",
        api_key: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 2000,
    ):
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens

        settings = get_settings()
        self._api_key: str | None = api_key or (
            settings.ANTHROPIC_API_KEY.get_secret_value()
            if settings.ANTHROPIC_API_KEY
            else None
        )
        self._client = None
        self._last_usage: dict[str, int] = self._empty_usage()

    @property
    def is_available(self) -> bool:
        return bool(self._api_key)

    def _get_client(self):
        if self._client is not None:
            return self._client
        if not self._api_key:
            return None
        try:
            import anthropic

            self._client = anthropic.AsyncAnthropic(api_key=self._api_key)
            return self._client
        except ImportError:
            logger.warning("anthropic package not installed — pip install anthropic")
            return None

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        client = self._get_client()
        if not client:
            return ""
        resp = await client.messages.create(
            model=self.model_name,
            max_tokens=max_tokens or self.max_tokens,
            temperature=temperature if temperature is not None else self.temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        self._last_usage = {
            "prompt_tokens": resp.usage.input_tokens,
            "completion_tokens": resp.usage.output_tokens,
            "total": resp.usage.input_tokens + resp.usage.output_tokens,
        }
        return resp.content[0].text if resp.content else ""

    async def complete_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        output_schema: type[T],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> T:
        """
        Structured output via Anthropic tool_use pattern.

        Injects the Pydantic schema as a tool definition and parses tool_use block.
        Falls back to defaults on error.
        """
        client = self._get_client()
        if not client:
            return output_schema()

        schema = output_schema.model_json_schema()
        tool_def = {
            "name": "structured_output",
            "description": f"Return structured output matching {output_schema.__name__}",
            "input_schema": schema,
        }

        try:
            resp = await client.messages.create(
                model=self.model_name,
                max_tokens=max_tokens or self.max_tokens,
                temperature=(
                    temperature if temperature is not None else self.temperature
                ),
                system=system_prompt,
                tools=[tool_def],
                tool_choice={"type": "tool", "name": "structured_output"},
                messages=[{"role": "user", "content": user_prompt}],
            )
            self._last_usage = {
                "prompt_tokens": resp.usage.input_tokens,
                "completion_tokens": resp.usage.output_tokens,
                "total": resp.usage.input_tokens + resp.usage.output_tokens,
            }
            # Extract tool_use block
            for block in resp.content:
                if block.type == "tool_use":
                    return output_schema.model_validate(block.input)
            return output_schema()
        except Exception as e:
            logger.warning(f"AnthropicLLMClient structured output failed: {e}")
            return output_schema()

    def get_token_usage(self) -> dict[str, int]:
        return self._last_usage
