"""
Unit tests for the PromptRegistry module.

Tests for PromptRegistry: manifest loading, template rendering, and
active-version resolution.
"""

from pathlib import Path

import pytest
from src.agents.registry.prompt_registry import PromptRegistry

# =============================================================================
# TEST DATA
# =============================================================================

MOCK_MANIFEST = """
active_version: v1
versions:
  v1:
    description: "First version"
"""

MOCK_TEMPLATE_V1 = """
system_prompt: |
  You are a test assistant.
  Title: {{ title }}

user_prompt: |
  Analyze: {{ description }}
"""

MOCK_TEMPLATE_MINIMAL = """
system_prompt: |
  System instructions.

user_prompt: |
  Process: {{ title }}
"""


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def tmp_prompts_dir(tmp_path: Path) -> Path:
    """Create a temporary prompts directory with a test prompt."""
    prompt_dir = tmp_path / "core_metadata"
    prompt_dir.mkdir()

    (prompt_dir / "manifest.yaml").write_text(MOCK_MANIFEST)
    (prompt_dir / "v1.yaml").write_text(MOCK_TEMPLATE_V1)

    return tmp_path


@pytest.fixture
def registry(tmp_prompts_dir: Path) -> PromptRegistry:
    """Create a PromptRegistry pointed at the temp directory."""
    return PromptRegistry(prompts_dir=tmp_prompts_dir)


# =============================================================================
# TEST CLASSES
# =============================================================================


class TestPromptRegistryInit:
    """Tests for PromptRegistry initialization."""

    def test_init_default_dir(self):
        """Default prompts directory should be set."""
        reg = PromptRegistry()
        assert reg._dir is not None
        assert isinstance(reg._dir, Path)

    def test_init_custom_dir(self, tmp_path: Path):
        """Custom prompts directory should be stored."""
        reg = PromptRegistry(prompts_dir=tmp_path)
        assert reg._dir == tmp_path

    def test_init_empty_caches(self):
        """Manifests and templates should start empty."""
        reg = PromptRegistry()
        assert reg._manifests == {}
        assert reg._templates == {}


class TestGetActiveVersion:
    """Tests for PromptRegistry.get_active_version."""

    def test_returns_active_version_from_manifest(self, registry: PromptRegistry):
        """Should parse active_version from manifest.yaml."""
        version = registry.get_active_version("core_metadata")
        assert version == "v1"

    def test_caches_manifest_on_second_call(self, registry: PromptRegistry):
        """Manifest should be loaded once and cached."""
        _ = registry.get_active_version("core_metadata")
        assert "core_metadata" in registry._manifests
        # Second call should not re-read disk (manifest already in cache)
        _ = registry.get_active_version("core_metadata")
        assert registry._manifests["core_metadata"]["active_version"] == "v1"


class TestRender:
    """Tests for PromptRegistry.render."""

    def test_render_returns_tuple(self, registry: PromptRegistry):
        """render() should return (system_prompt, user_prompt) tuple."""
        system, user = registry.render(
            "core_metadata",
            version="v1",
            variables={"title": "Techno Night", "description": "Electronic music"},
        )
        assert isinstance(system, str)
        assert isinstance(user, str)

    def test_render_injects_variables(self, registry: PromptRegistry):
        """render() should substitute Jinja2 variables."""
        system, user = registry.render(
            "core_metadata",
            version="v1",
            variables={"title": "Jazz Evening", "description": "Live jazz"},
        )
        assert "Jazz Evening" in system
        assert "Live jazz" in user

    def test_render_active_version_resolves(self, registry: PromptRegistry):
        """render() with version='active' should resolve to active_version."""
        system, user = registry.render(
            "core_metadata",
            version="active",
            variables={"title": "Test", "description": "Test desc"},
        )
        assert isinstance(system, str)
        assert isinstance(user, str)

    def test_render_caches_template(self, registry: PromptRegistry):
        """Template should be cached after first render."""
        registry.render(
            "core_metadata",
            version="v1",
            variables={"title": "X", "description": "Y"},
        )
        assert "core_metadata/v1" in registry._templates

    def test_render_missing_prompt_raises(self, tmp_path: Path):
        """render() for a non-existent prompt should raise an error."""
        reg = PromptRegistry(prompts_dir=tmp_path)
        with pytest.raises(Exception):
            reg.render("nonexistent_prompt", version="v1", variables={})
