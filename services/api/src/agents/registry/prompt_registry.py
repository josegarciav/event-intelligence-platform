"""
File-based prompt versioning registry.

Prompts live in src/agents/prompts/{name}/:
  manifest.yaml   — active_version + per-version metadata
  v1.yaml         — prompt content (system_prompt + user_prompt, Jinja2 templates)

Usage:
    registry = PromptRegistry()
    system, user = registry.render("core_metadata", variables={"title": "Techno Night"})
    system, user = registry.render("core_metadata", version="v1", variables={...})
"""

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


class PromptRegistry:
    """
    Loads prompt manifests + renders Jinja2 templates for enrichment agents.

    Thread-safe: manifests are loaded once and cached.
    """

    def __init__(self, prompts_dir: Path | None = None):
        self._dir = prompts_dir or _PROMPTS_DIR
        self._manifests: dict[str, dict[str, Any]] = {}
        self._templates: dict[str, dict[str, Any]] = {}  # key = "name/version"

    def _load_manifest(self, prompt_name: str) -> dict[str, Any]:
        if prompt_name in self._manifests:
            return self._manifests[prompt_name]

        manifest_path = self._dir / prompt_name / "manifest.yaml"
        if not manifest_path.exists():
            raise FileNotFoundError(f"Prompt manifest not found: {manifest_path}")

        with manifest_path.open() as f:
            manifest = yaml.safe_load(f)

        self._manifests[prompt_name] = manifest
        return manifest

    def _resolve_version(self, prompt_name: str, version: str) -> str:
        """Resolve 'active' to the concrete version string from manifest."""
        if version != "active":
            return version
        manifest = self._load_manifest(prompt_name)
        return manifest.get("active_version", "v1")

    def _load_template(self, prompt_name: str, version: str) -> dict[str, Any]:
        cache_key = f"{prompt_name}/{version}"
        if cache_key in self._templates:
            return self._templates[cache_key]

        template_path = self._dir / prompt_name / f"{version}.yaml"
        if not template_path.exists():
            raise FileNotFoundError(f"Prompt template not found: {template_path}")

        with template_path.open() as f:
            template = yaml.safe_load(f)

        self._templates[cache_key] = template
        return template

    def render(
        self,
        prompt_name: str,
        version: str = "active",
        variables: dict[str, Any] | None = None,
        agent_name: str | None = None,
        event_id: str | None = None,
    ) -> tuple[str, str]:
        """
        Render a prompt template with the given variables.

        Args:
            prompt_name: Prompt identifier (e.g., "core_metadata")
            version: "active" or explicit version (e.g., "v1")
            variables: Template variables for Jinja2 substitution
            agent_name: For audit logging
            event_id: For audit logging

        Returns:
            Tuple of (system_prompt, user_prompt) as rendered strings
        """
        try:
            from jinja2 import Template, Undefined

            class SilentUndefined(Undefined):
                def __str__(self) -> str:
                    return f"[{self._undefined_name}]"

        except ImportError:
            # Fallback: simple str.replace substitution
            Template = None  # type: ignore[assignment]
            SilentUndefined = None  # type: ignore[assignment]

        resolved_version = self._resolve_version(prompt_name, version)
        template_data = self._load_template(prompt_name, resolved_version)

        variables = variables or {}
        system_raw = template_data.get("system_prompt", "")
        user_raw = template_data.get("user_prompt", "")

        if Template is not None:
            system_rendered = Template(system_raw, undefined=SilentUndefined).render(
                **variables
            )
            user_rendered = Template(user_raw, undefined=SilentUndefined).render(
                **variables
            )
        else:
            # Simple substitution fallback
            system_rendered = system_raw
            user_rendered = user_raw
            for k, v in variables.items():
                system_rendered = system_rendered.replace(f"{{{{ {k} }}}}", str(v))
                user_rendered = user_rendered.replace(f"{{{{ {k} }}}}", str(v))

        if agent_name or event_id:
            logger.debug(
                "PromptRegistry.render",
                extra={
                    "agent_name": agent_name,
                    "prompt_name": prompt_name,
                    "prompt_version": resolved_version,
                    "event_id": event_id,
                },
            )

        return system_rendered, user_rendered

    def get_active_version(self, prompt_name: str) -> str:
        """Return the active version string for a prompt."""
        return self._resolve_version(prompt_name, "active")

    def list_prompts(self) -> list[str]:
        """Return all prompt names found in the prompts directory."""
        if not self._dir.exists():
            return []
        return [
            p.name
            for p in self._dir.iterdir()
            if p.is_dir() and (p / "manifest.yaml").exists()
        ]


# Singleton
_registry: PromptRegistry | None = None


def get_prompt_registry() -> PromptRegistry:
    global _registry
    if _registry is None:
        _registry = PromptRegistry()
    return _registry
