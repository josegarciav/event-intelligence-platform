"""
Unit tests for the prompts loader module.

Tests for PromptLoader class.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import pytest

from src.agents.loader import PromptLoader

# =============================================================================
# TEST DATA
# =============================================================================


MOCK_PROMPT_YAML = """
name: "Test Prompt"
description: "A test prompt template"

system_prompt: |
  You are a test assistant.
  Context: {{ taxonomy_context }}

user_prompt: |
  Analyze this event:
  TITLE: {{ title }}
  DESCRIPTION: {{ description }}

  {{ attribute_options_string }}
"""


MOCK_PROMPT_YAML_MINIMAL = """
system_prompt: |
  System instructions here.

user_prompt: |
  User message: {{ title }}
"""


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_taxonomy_retriever():
    """Create a mock TaxonomyRetriever."""
    retriever = MagicMock()
    retriever.get_subcategory_context_for_prompt.return_value = "Subcategory context"
    retriever.get_all_categories_summary.return_value = "All categories summary"
    retriever.get_attribute_options_string.return_value = (
        "- energy_level: low | medium | high"
    )
    return retriever


@pytest.fixture
def loader(mock_taxonomy_retriever):
    """Create PromptLoader with mocked taxonomy."""
    with patch(
        "src.agents.loader.get_taxonomy_retriever",
        return_value=mock_taxonomy_retriever,
    ):
        return PromptLoader()


# =============================================================================
# TEST CLASSES
# =============================================================================


class TestPromptLoaderInit:
    """Tests for PromptLoader initialization."""

    def test_init_sets_root_path(self, loader):
        """Should set root_path to agents directory."""
        assert loader.root_path is not None
        assert isinstance(loader.root_path, Path)

    def test_init_loads_taxonomy_retriever(self, mock_taxonomy_retriever):
        """Should load taxonomy retriever."""
        with patch(
            "src.agents.loader.get_taxonomy_retriever",
            return_value=mock_taxonomy_retriever,
        ):
            loader = PromptLoader()
            assert loader.taxonomy is mock_taxonomy_retriever


class TestPromptLoaderGetPrompt:
    """Tests for PromptLoader.get_prompt method."""

    def test_loads_and_renders_prompt(self, loader):
        """Should load and render prompt template."""
        with patch.object(Path, "exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=MOCK_PROMPT_YAML)):
                result = loader.get_prompt(
                    group="classification",
                    feature="test",
                    variables={"title": "Test Event", "description": "A test event"},
                )

        assert "system" in result
        assert "user" in result
        assert "Test Event" in result["user"]
        assert "A test event" in result["user"]

    def test_injects_taxonomy_context_from_subcategory(self, loader):
        """Should inject taxonomy context when subcategory_id provided."""
        with patch.object(Path, "exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=MOCK_PROMPT_YAML)):
                result = loader.get_prompt(
                    group="enrichment",
                    feature="test",
                    variables={
                        "title": "Test",
                        "description": "Desc",
                        "subcategory_id": "1.4",
                    },
                )

        loader.taxonomy.get_subcategory_context_for_prompt.assert_called_with("1.4")
        assert "Subcategory context" in result["system"]

    def test_injects_all_categories_when_no_subcategory(self, loader):
        """Should inject all categories summary when no subcategory."""
        with patch.object(Path, "exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=MOCK_PROMPT_YAML)):
                loader.get_prompt(
                    group="classification",
                    feature="test",
                    variables={"title": "Test", "description": "Desc"},
                )

        loader.taxonomy.get_all_categories_summary.assert_called()

    def test_injects_attribute_options_string(self, loader):
        """Should inject attribute options string."""
        with patch.object(Path, "exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=MOCK_PROMPT_YAML)):
                loader.get_prompt(
                    group="enrichment",
                    feature="test",
                    variables={"title": "Test", "description": "Desc"},
                )

        loader.taxonomy.get_attribute_options_string.assert_called()

    def test_raises_file_not_found(self, loader):
        """Should raise FileNotFoundError for missing template."""
        with patch.object(Path, "exists", return_value=False):
            with pytest.raises(FileNotFoundError, match="Missing prompt"):
                loader.get_prompt(
                    group="invalid",
                    feature="missing",
                    variables={},
                )

    def test_raises_key_error_for_missing_keys(self, loader):
        """Should raise KeyError when YAML missing required keys."""
        invalid_yaml = """
        name: "Test"
        # Missing system_prompt and user_prompt
        """
        with patch.object(Path, "exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=invalid_yaml)):
                with pytest.raises(KeyError):
                    loader.get_prompt(
                        group="test",
                        feature="test",
                        variables={"title": "Test", "description": "Desc"},
                    )

    def test_preserves_provided_taxonomy_context(self, loader):
        """Should preserve taxonomy_context if already in variables."""
        with patch.object(Path, "exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=MOCK_PROMPT_YAML)):
                result = loader.get_prompt(
                    group="enrichment",
                    feature="test",
                    variables={
                        "title": "Test",
                        "description": "Desc",
                        "taxonomy_context": "Custom context",
                    },
                )

        assert "Custom context" in result["system"]

    def test_renders_jinja_templates(self, loader):
        """Should render Jinja2 templates in agents."""
        template_yaml = """
system_prompt: |
  {% if subcategory_id %}
  Subcategory: {{ subcategory_id }}
  {% endif %}

user_prompt: |
  Title: {{ title }}
        """
        with patch.object(Path, "exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=template_yaml)):
                result = loader.get_prompt(
                    group="test",
                    feature="test",
                    variables={"title": "Test Event", "subcategory_id": "1.4"},
                )

        assert "1.4" in result["system"]
        assert "Test Event" in result["user"]


class TestPromptLoaderGetAllGroupPrompts:
    """Tests for PromptLoader.get_all_group_prompts method."""

    def test_returns_all_three_prompts(self, loader):
        """Should return core, pulse, and logistics prompts."""
        with patch.object(loader, "get_prompt") as mock_get:
            mock_get.return_value = {"system": "sys", "user": "usr"}

            result = loader.get_all_group_prompts(
                variables={"title": "Test", "description": "Desc"}
            )

        assert "core" in result
        assert "pulse" in result
        assert "logistics" in result

    def test_calls_get_prompt_three_times(self, loader):
        """Should call get_prompt for each prompt type."""
        with patch.object(loader, "get_prompt") as mock_get:
            mock_get.return_value = {"system": "sys", "user": "usr"}

            loader.get_all_group_prompts(
                variables={"title": "Test", "description": "Desc"}
            )

        assert mock_get.call_count == 3

    def test_calls_correct_groups_and_features(self, loader):
        """Should call with correct group/feature combinations."""
        with patch.object(loader, "get_prompt") as mock_get:
            mock_get.return_value = {"system": "sys", "user": "usr"}

            loader.get_all_group_prompts(
                variables={"title": "Test", "description": "Desc"}
            )

        # Check calls - get_prompt is called with positional args
        calls = mock_get.call_args_list
        call_args = [(c[0][0], c[0][1]) for c in calls]  # Get first two positional args

        assert ("classification", "core_metadata") in call_args
        assert ("enrichment", "experience_pulse") in call_args
        assert ("enrichment", "logistics") in call_args


class TestPromptLoaderIntegration:
    """Integration tests for PromptLoader with real files."""

    def test_load_real_core_metadata_prompt(self):
        """Should load real core_metadata prompt."""
        # Skip if agents directory doesn't exist
        prompts_dir = Path(__file__).parent.parent.parent.parent / "src" / "agents"
        if not prompts_dir.exists():
            pytest.skip("Agents directory not found")

        with patch("src.agents.loader.get_taxonomy_retriever") as mock_get:
            mock_retriever = MagicMock()
            mock_retriever.get_all_categories_summary.return_value = "Categories"
            mock_retriever.get_attribute_options_string.return_value = "Options"
            mock_get.return_value = mock_retriever

            loader = PromptLoader()

            try:
                result = loader.get_prompt(
                    group="classification",
                    feature="core_metadata",
                    variables={
                        "title": "Techno Night",
                        "description": "Electronic music event",
                    },
                )

                assert "system" in result
                assert "user" in result
                assert "Techno Night" in result["user"]
            except FileNotFoundError:
                pytest.skip("core_metadata.yaml not found")

    def test_load_real_experience_pulse_prompt(self):
        """Should load real experience_pulse prompt."""
        prompts_dir = Path(__file__).parent.parent.parent.parent / "src" / "agents"
        if not prompts_dir.exists():
            pytest.skip("Agents directory not found")

        with patch("src.agents.loader.get_taxonomy_retriever") as mock_get:
            mock_retriever = MagicMock()
            mock_retriever.get_subcategory_context_for_prompt.return_value = "Context"
            mock_retriever.get_attribute_options_string.return_value = "Options"
            mock_get.return_value = mock_retriever

            loader = PromptLoader()

            try:
                result = loader.get_prompt(
                    group="enrichment",
                    feature="experience_pulse",
                    variables={
                        "title": "Jazz Night",
                        "description": "Live jazz performance",
                        "subcategory_id": "1.4",
                    },
                )

                assert "system" in result
                assert "user" in result
            except FileNotFoundError:
                pytest.skip("experience_pulse.yaml not found")
