"""
Base LLM Client for feature extraction.

Provides a unified interface for LLM calls using LangChain.
Supports OpenAI and Anthropic providers with structured output.
"""

import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Optional, Type, TypeVar

from pydantic import BaseModel

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class BaseLLMClient(ABC):
    """Abstract base class for LLM clients."""

    @abstractmethod
    def invoke(self, prompt: str, **kwargs) -> str:
        """Invoke the LLM with a prompt and return raw text response."""
        pass

    @abstractmethod
    def invoke_structured(
        self,
        prompt: str,
        output_schema: Type[T],
        **kwargs,
    ) -> T:
        """Invoke the LLM and return structured output matching the schema."""
        pass


class LangChainLLMClient(BaseLLMClient):
    """
    LLM Client using LangChain for structured output.

    Supports:
    - OpenAI (GPT-3.5, GPT-4)
    - Anthropic (Claude)

    Uses with_structured_output for Pydantic model enforcement.
    """

    def __init__(
        self,
        provider: str = "openai",
        model_name: str = "gpt-4o-mini",
        api_key: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 2000,
    ):
        """
        Initialize the LangChain LLM client.

        Args:
            provider: "openai" or "anthropic"
            model_name: Model identifier (e.g., "gpt-4o-mini", "claude-3-haiku-20240307")
            api_key: API key (defaults to env var)
            temperature: Temperature for generation (0.0-1.0)
            max_tokens: Maximum tokens in response
        """
        self.provider = provider
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens

        # Get API key
        if api_key:
            self.api_key = api_key
        elif provider == "openai":
            self.api_key = os.getenv("OPENAI_API_KEY")
        elif provider == "anthropic":
            self.api_key = os.getenv("ANTHROPIC_API_KEY")
        else:
            self.api_key = None

        self._llm = None
        self._initialized = False

    def _get_llm(self):
        """Lazy initialization of LLM."""
        if self._llm is not None:
            return self._llm

        if not self.api_key:
            logger.warning(f"No API key found for {self.provider}")
            return None

        try:
            if self.provider == "openai":
                from langchain_openai import ChatOpenAI

                self._llm = ChatOpenAI(
                    model=self.model_name,
                    api_key=self.api_key,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                )
            elif self.provider == "anthropic":
                from langchain_anthropic import ChatAnthropic

                self._llm = ChatAnthropic(
                    model=self.model_name,
                    api_key=self.api_key,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                )
            else:
                raise ValueError(f"Unknown provider: {self.provider}")

            self._initialized = True
            return self._llm

        except ImportError as e:
            logger.warning(f"LangChain package not installed: {e}")
            return None

    @property
    def is_available(self) -> bool:
        """Check if LLM is available."""
        return self._get_llm() is not None

    def invoke(self, prompt: str, **kwargs) -> str:
        """
        Invoke the LLM with a prompt and return raw text response.

        Args:
            prompt: The prompt text
            **kwargs: Additional arguments

        Returns:
            Raw text response from LLM
        """
        llm = self._get_llm()
        if not llm:
            raise RuntimeError("LLM not available - check API key and provider")

        from langchain_core.messages import HumanMessage

        response = llm.invoke([HumanMessage(content=prompt)])
        return response.content

    def invoke_structured(
        self,
        prompt: str,
        output_schema: Type[T],
        **kwargs,
    ) -> T:
        """
        Invoke the LLM and return structured output matching the Pydantic schema.

        Uses LangChain's with_structured_output for reliable parsing.

        Args:
            prompt: The prompt text
            output_schema: Pydantic model class for output structure
            **kwargs: Additional arguments

        Returns:
            Instance of output_schema populated with LLM response
        """
        llm = self._get_llm()
        if not llm:
            raise RuntimeError("LLM not available - check API key and provider")

        from langchain_core.messages import HumanMessage

        # Use structured output for reliable parsing
        structured_llm = llm.with_structured_output(output_schema)
        response = structured_llm.invoke([HumanMessage(content=prompt)])
        return response

    def invoke_with_context(
        self,
        system_prompt: str,
        user_prompt: str,
        output_schema: Optional[Type[T]] = None,
        **kwargs,
    ) -> Any:
        """
        Invoke LLM with system and user prompts.

        Args:
            system_prompt: System/context prompt
            user_prompt: User query
            output_schema: Optional Pydantic model for structured output
            **kwargs: Additional arguments

        Returns:
            Structured output if schema provided, else raw text
        """
        llm = self._get_llm()
        if not llm:
            raise RuntimeError("LLM not available - check API key and provider")

        from langchain_core.messages import HumanMessage, SystemMessage

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]

        if output_schema:
            structured_llm = llm.with_structured_output(output_schema)
            return structured_llm.invoke(messages)
        else:
            response = llm.invoke(messages)
            return response.content


class FallbackLLMClient(BaseLLMClient):
    """
    Fallback client that uses rule-based logic when LLM is unavailable.

    Provides deterministic defaults based on simple heuristics.
    """

    def invoke(self, prompt: str, **kwargs) -> str:
        """Return empty string - use invoke_structured for actual logic."""
        return ""

    def invoke_structured(
        self,
        prompt: str,
        output_schema: Type[T],
        **kwargs,
    ) -> T:
        """
        Return a default instance of the schema.

        This is overridden by FeatureExtractor with rule-based logic.
        """
        # Return default instance
        return output_schema()


def create_llm_client(
    provider: str = "openai",
    model_name: Optional[str] = None,
    api_key: Optional[str] = None,
    temperature: float = 0.1,
    fallback_to_rules: bool = True,
) -> BaseLLMClient:
    """
    Factory function to create an LLM client.

    Args:
        provider: "openai" or "anthropic"
        model_name: Model to use (defaults based on provider)
        api_key: API key (defaults to env var)
        temperature: Temperature for generation
        fallback_to_rules: Return FallbackLLMClient if LLM unavailable

    Returns:
        LLM client instance
    """
    # Default models per provider
    if model_name is None:
        model_name = {
            "openai": "gpt-4o-mini",
            "anthropic": "claude-3-haiku-20240307",
        }.get(provider, "gpt-4o-mini")

    client = LangChainLLMClient(
        provider=provider,
        model_name=model_name,
        api_key=api_key,
        temperature=temperature,
    )

    if client.is_available:
        return client
    elif fallback_to_rules:
        logger.info("LLM unavailable, using rule-based fallback")
        return FallbackLLMClient()
    else:
        raise RuntimeError(f"LLM client not available for provider: {provider}")
