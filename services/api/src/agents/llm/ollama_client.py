"""
Ollama LLM client — runs Meta Llama (and other models) locally via Ollama.

Ollama exposes an OpenAI-compatible REST API at http://localhost:11434/v1,
so this client reuses the OpenAI SDK + Instructor with a custom base_url.

Setup:
  1. Install Ollama: https://ollama.com
  2. Pull a model: ollama pull llama3.2:3b
  3. Ollama starts automatically on port 11434

Recommended models (lightweight → capable):
  llama3.2:1b   — 1B params, very fast, CPU-friendly
  llama3.2:3b   — 3B params, good balance (DEFAULT)
  llama3.1:8b   — 8B params, best quality local
  qwen2.5:3b    — strong at structured output tasks

Structured output:
  Uses instructor.Mode.JSON — more reliable than TOOLS mode for local models.
  JSON mode injects a system instruction to return valid JSON matching the schema.

No API key required — Ollama runs entirely locally.
"""

import logging
from typing import TypeVar

from pydantic import BaseModel

from src.agents.llm.base_llm_client import BaseLLMClient

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

_DEFAULT_MODEL = "llama3.2:3b"
_OLLAMA_API_KEY = "ollama"  # Ollama requires any non-empty string

# Module-level availability cache: (base_url, model_name) → bool
# Shared across all OllamaLLMClient instances so the /api/tags ping
# is made once per (endpoint, model) pair per process, not once per agent.
_availability_cache: dict[tuple[str, str], bool] = {}


def _default_ollama_base_url() -> str:
    """Read OLLAMA_BASE_URL from Settings (falls back to localhost default)."""
    try:
        from src.configs.settings import get_settings

        return get_settings().OLLAMA_BASE_URL
    except Exception:
        return "http://localhost:11434/v1"


class OllamaLLMClient(BaseLLMClient):
    """
    Llama (and other models) via Ollama's OpenAI-compatible API.

    Uses Instructor in JSON mode for structured output extraction.
    Lazy initialization — the client is only created on first use.

    No API key is required. Ollama must be running locally.
    """

    provider = "ollama"

    def __init__(
        self,
        model_name: str = _DEFAULT_MODEL,
        base_url: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 2000,
    ):
        """Initialize the OllamaLLMClient with model and connection settings."""
        self.model_name = model_name
        self.base_url = base_url if base_url is not None else _default_ollama_base_url()
        self.temperature = temperature
        self.max_tokens = max_tokens

        self._instructor_client = None
        self._raw_client = None
        self._last_usage: dict[str, int] = self._empty_usage()
        self._available: bool | None = None

    @property
    def is_available(self) -> bool:
        """Check if Ollama is reachable and the model is installed."""
        if self._available is not None:
            return self._available
        self._available = self._check_ollama()
        return self._available

    def _check_ollama(self) -> bool:
        """Ping Ollama once per (base_url, model_name) pair; subsequent calls use cache."""
        cache_key = (self.base_url, self.model_name)
        if cache_key in _availability_cache:
            return _availability_cache[cache_key]

        result = self._probe_ollama()
        _availability_cache[cache_key] = result
        return result

    def _probe_ollama(self) -> bool:
        """Single HTTP probe — only called on cache miss."""
        try:
            import httpx

            resp = httpx.get(f"{self.base_url.rstrip('/v1')}/api/tags", timeout=3.0)
            if resp.status_code == 200:
                tags = resp.json()
                model_names = [m.get("name", "") for m in tags.get("models", [])]
                base_model = self.model_name.split(":")[0]
                installed = any(base_model in m for m in model_names)
                if not installed:
                    logger.warning(
                        f"OllamaLLMClient: model '{self.model_name}' not found in Ollama. "
                        f"Install with: ollama pull {self.model_name}"
                    )
                    return False
                return True
            return False
        except Exception:
            logger.warning(
                "OllamaLLMClient: Ollama not reachable at %s. Start Ollama: https://ollama.com",
                self.base_url,
            )
            return False

    def _get_instructor_client(self):
        if self._instructor_client is not None:
            return self._instructor_client
        try:
            import instructor
            from openai import AsyncOpenAI

            raw = AsyncOpenAI(
                base_url=self.base_url,
                api_key=_OLLAMA_API_KEY,
            )
            # JSON mode is more reliable than TOOLS for local models
            self._instructor_client = instructor.from_openai(
                raw, mode=instructor.Mode.JSON
            )
            self._raw_client = raw
            return self._instructor_client
        except ImportError:
            logger.warning("instructor or openai package not installed")
            return None

    def _get_raw_client(self):
        """Return the raw AsyncOpenAI client (for plain text completion)."""
        if self._raw_client is not None:
            return self._raw_client
        self._get_instructor_client()
        return self._raw_client

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Send a plain-text completion request to the Ollama model."""
        client = self._get_raw_client()
        if not client:
            return ""
        try:
            resp = await client.chat.completions.create(
                model=self.model_name,
                temperature=(
                    temperature if temperature is not None else self.temperature
                ),
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
        except Exception as e:
            logger.warning(f"OllamaLLMClient.complete failed: {e}")
            return ""

    async def complete_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        output_schema: type[T],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> T:
        """
        Structured output via Instructor JSON mode.

        Injects the Pydantic schema description into the system prompt so the
        model knows exactly what JSON structure to return.
        """
        client = self._get_instructor_client()
        if not client:
            raise RuntimeError(
                "instructor and openai packages are required for structured output. "
                "Install with: pip install instructor openai"
            )

        # Enrich system prompt with schema hint for better JSON adherence
        schema_hint = _build_schema_hint(output_schema)
        enriched_system = f"{system_prompt}\n\n{schema_hint}"

        try:
            result, completion = await client.chat.completions.create_with_completion(
                model=self.model_name,
                response_model=output_schema,
                temperature=(
                    temperature if temperature is not None else self.temperature
                ),
                max_tokens=max_tokens or self.max_tokens,
                messages=[
                    {"role": "system", "content": enriched_system},
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
            logger.warning(f"OllamaLLMClient structured output failed: {e}")
            return output_schema()

    def get_token_usage(self) -> dict[str, int]:
        """Return the token usage from the most recent LLM call."""
        return self._last_usage


def _build_schema_hint(schema: type[BaseModel]) -> str:
    """
    Build a compact schema description to inject into the system prompt.

    Helps local models understand the expected JSON structure.
    """
    try:
        json_schema = schema.model_json_schema()
        props = json_schema.get("properties", {})
        required = json_schema.get("required", [])

        lines = ["You MUST respond with a valid JSON object matching this schema:"]
        for field_name, field_info in props.items():
            field_type = field_info.get("type", "any")
            description = field_info.get("description", "")
            enum_vals = field_info.get("enum") or field_info.get("allOf", [{}])[0].get(
                "enum"
            )
            req = "required" if field_name in required else "optional"

            if enum_vals:
                lines.append(f'  "{field_name}": one of {enum_vals}  # {req}')
            elif description:
                lines.append(f'  "{field_name}": {field_type}  # {description} ({req})')
            else:
                lines.append(f'  "{field_name}": {field_type}  # {req}')

        lines.append("Return ONLY the JSON object, no markdown, no explanation.")
        return "\n".join(lines)
    except Exception:
        return "Respond with a valid JSON object matching the requested schema."
