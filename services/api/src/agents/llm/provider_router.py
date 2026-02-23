"""
Provider router — selects the correct LLM client by provider name.

Used by enrichment agents to instantiate a client from agents.yaml config.

Supported providers:
  "anthropic"  — Claude via Anthropic SDK (tool_use structured output)
  "openai"     — GPT via OpenAI SDK + Instructor (TOOLS mode)
  "ollama"     — Local models (Llama, Qwen, etc.) via Ollama + Instructor (JSON mode)
  "llama"      — Alias for "ollama"
"""

import logging

from src.agents.llm.base_llm_client import BaseLLMClient

logger = logging.getLogger(__name__)


def get_llm_client(
    provider: str = "anthropic",
    model_name: str | None = None,
    temperature: float = 0.1,
    max_tokens: int = 2000,
    **kwargs,
) -> BaseLLMClient:
    """
    Factory: returns the appropriate LLM client for the given provider.

    Args:
        provider: "anthropic" | "openai" | "ollama" | "llama"
        model_name: Model identifier. Defaults per provider:
                    anthropic → claude-haiku-4-5-20251001
                    openai    → gpt-4o-mini
                    ollama    → llama3.2:3b
        temperature: Sampling temperature
        max_tokens: Max response tokens
        **kwargs: Additional provider-specific args (e.g., base_url for ollama)

    Returns:
        Concrete BaseLLMClient instance (may report is_available=False if
        the provider is unreachable or missing an API key)
    """
    provider = provider.lower().strip()

    if provider == "anthropic":
        from src.agents.llm.anthropic_client import AnthropicLLMClient

        return AnthropicLLMClient(
            model_name=model_name or "claude-haiku-4-5-20251001",
            temperature=temperature,
            max_tokens=max_tokens,
        )

    elif provider == "openai":
        from src.agents.llm.openai_client import OpenAILLMClient

        return OpenAILLMClient(
            model_name=model_name or "gpt-4o-mini",
            temperature=temperature,
            max_tokens=max_tokens,
        )

    elif provider in ("ollama", "llama"):
        from src.agents.llm.ollama_client import OllamaLLMClient

        return OllamaLLMClient(
            model_name=model_name or "llama3.2:3b",
            base_url=kwargs.get("base_url", "http://localhost:11434/v1"),
            temperature=temperature,
            max_tokens=max_tokens,
        )

    else:
        logger.warning(
            f"Unknown LLM provider '{provider}'. Supported: anthropic, openai, ollama, llama. Defaulting to anthropic."
        )
        from src.agents.llm.anthropic_client import AnthropicLLMClient

        return AnthropicLLMClient(
            model_name=model_name or "claude-haiku-4-5-20251001",
            temperature=temperature,
            max_tokens=max_tokens,
        )
