"""
Abstract LLM client interface.

All provider implementations (OpenAI, Anthropic) extend BaseLLMClient.
The interface is async-first and returns structured Pydantic outputs.
"""

import logging
from abc import ABC, abstractmethod
from typing import TypeVar

from pydantic import BaseModel

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class BaseLLMClient(ABC):
    """
    Abstract async LLM client.

    Providers implement complete() for raw text and complete_structured()
    for Pydantic-constrained structured output.
    """

    provider: str = "base"

    @abstractmethod
    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 2000,
    ) -> str:
        """Raw text completion."""
        ...

    @abstractmethod
    async def complete_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        output_schema: type[T],
        temperature: float = 0.1,
        max_tokens: int = 2000,
    ) -> T:
        """Structured output completion — returns validated Pydantic model."""
        ...

    @abstractmethod
    def get_token_usage(self) -> dict[str, int]:
        """Returns {'prompt_tokens': N, 'completion_tokens': N, 'total': N} for last call."""
        ...

    @property
    def is_available(self) -> bool:
        """Returns True if the client has a valid API key and can make calls."""
        return False

    def _empty_usage(self) -> dict[str, int]:
        return {"prompt_tokens": 0, "completion_tokens": 0, "total": 0}
