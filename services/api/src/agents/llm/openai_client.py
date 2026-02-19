"""
OpenAI client using Instructor for structured output.

Uses gpt-4o-mini by default (configurable via agents.yaml).
"""

import logging
from typing import TypeVar

from pydantic import BaseModel

from src.agents.llm.base_llm_client import BaseLLMClient
from src.configs.settings import get_settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class OpenAILLMClient(BaseLLMClient):
    """
    OpenAI client using Instructor for constrained structured output.

    Lazy initialization — only loads SDK if an API key is available.
    """

    provider = "openai"

    def __init__(
        self,
        model_name: str = "gpt-4o-mini",
        api_key: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 2000,
    ):
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens

        settings = get_settings()
        self._api_key: str | None = api_key or (
            settings.OPENAI_API_KEY.get_secret_value()
            if settings.OPENAI_API_KEY
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
            import instructor
            from openai import AsyncOpenAI

            self._client = instructor.from_openai(
                AsyncOpenAI(api_key=self._api_key),
                mode=instructor.Mode.TOOLS,
            )
            return self._client
        except ImportError:
            logger.warning("instructor or openai package not installed")
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
        # Use raw openai for plain text
        from openai import AsyncOpenAI

        raw = AsyncOpenAI(api_key=self._api_key)
        resp = await raw.chat.completions.create(
            model=self.model_name,
            temperature=temperature if temperature is not None else self.temperature,
            max_tokens=max_tokens or self.max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        if resp.usage:
            self._last_usage = {
                "prompt_tokens": resp.usage.prompt_tokens,
                "completion_tokens": resp.usage.completion_tokens,
                "total": resp.usage.total_tokens,
            }
        return resp.choices[0].message.content or ""

    async def complete_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        output_schema: type[T],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> T:
        client = self._get_client()
        if not client:
            return output_schema()
        try:
            result, completion = await client.chat.completions.create_with_completion(
                model=self.model_name,
                response_model=output_schema,
                temperature=(
                    temperature if temperature is not None else self.temperature
                ),
                max_tokens=max_tokens or self.max_tokens,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            if completion.usage:
                self._last_usage = {
                    "prompt_tokens": completion.usage.prompt_tokens,
                    "completion_tokens": completion.usage.completion_tokens,
                    "total": completion.usage.total_tokens,
                }
            return result
        except Exception as e:
            logger.warning(f"OpenAILLMClient structured output failed: {e}")
            return output_schema()

    def get_token_usage(self) -> dict[str, int]:
        return self._last_usage
