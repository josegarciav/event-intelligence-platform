"""
Unit tests for agents core utilities.

Covers:
  - agents/base/task.py         — AgentTask / AgentResult dataclasses
  - agents/base/output_models.py — Pydantic extraction schemas
  - agents/base/base_agent.py   — BaseAgent helper methods (_chunk, context builders)
  - agents/validation/confidence.py — confidence scoring and flagging
  - agents/llm/provider_router.py   — LLM client factory routing
"""

import json

import pytest

# =============================================================================
# AGENTS/BASE/TASK.PY
# =============================================================================


class TestAgentTask:
    """Tests for AgentTask dataclass."""

    def test_creation_with_required_fields(self):
        """Should create an AgentTask with required fields and sensible defaults."""
        from src.agents.base.task import AgentTask

        task = AgentTask(
            agent_name="test_agent",
            events=[],
            target_fields=["event_type", "tags"],
        )

        assert task.agent_name == "test_agent"
        assert task.events == []
        assert task.target_fields == ["event_type", "tags"]
        assert task.prompt_version == "active"
        assert task.priority == 1
        assert task.retry_limit == 2
        assert task.metadata == {}

    def test_custom_values(self):
        """Should accept custom priority, version, and metadata."""
        from src.agents.base.task import AgentTask

        task = AgentTask(
            agent_name="classifier",
            events=[],
            target_fields=["taxonomy"],
            prompt_version="v2",
            priority=3,
            retry_limit=1,
            metadata={"source": "ticketmaster"},
        )

        assert task.prompt_version == "v2"
        assert task.priority == 3
        assert task.retry_limit == 1
        assert task.metadata["source"] == "ticketmaster"


class TestAgentResult:
    """Tests for AgentResult dataclass."""

    def test_creation_with_required_fields(self):
        """Should create an AgentResult with required fields and empty defaults."""
        from src.agents.base.task import AgentResult

        result = AgentResult(
            agent_name="feature_alignment",
            prompt_name="feature_alignment",
            prompt_version="v1",
            events=[],
        )

        assert result.agent_name == "feature_alignment"
        assert result.prompt_name == "feature_alignment"
        assert result.prompt_version == "v1"
        assert result.events == []
        assert result.confidence_scores == {}
        assert result.token_usage == {}
        assert result.errors == []
        assert result.duration_seconds == 0.0

    def test_with_errors_and_token_usage(self):
        """Should store errors, token usage, and duration."""
        from src.agents.base.task import AgentResult

        result = AgentResult(
            agent_name="deduplication",
            prompt_name="deduplication",
            prompt_version="skipped",
            events=[],
            errors=["LLM unavailable"],
            token_usage={"prompt_tokens": 100, "completion_tokens": 50, "total": 150},
            duration_seconds=1.23,
        )

        assert result.errors == ["LLM unavailable"]
        assert result.token_usage["total"] == 150
        assert result.duration_seconds == 1.23


# =============================================================================
# AGENTS/BASE/OUTPUT_MODELS.PY
# =============================================================================


class TestPrimaryCategoryExtraction:
    """Tests for PrimaryCategoryExtraction validator."""

    def test_valid_category_id_passes(self):
        """Should accept a valid category ID from the taxonomy."""
        from src.agents.base.output_models import PrimaryCategoryExtraction

        model = PrimaryCategoryExtraction(
            category_id="1",
            reasoning="Music event",
            confidence=0.9,
        )
        assert model.category_id == "1"

    def test_invalid_category_id_coerced_to_zero(self):
        """Unknown category IDs should be coerced to '0' (Other)."""
        from src.agents.base.output_models import PrimaryCategoryExtraction

        model = PrimaryCategoryExtraction(
            category_id="999",
            reasoning="Unknown",
            confidence=0.5,
        )
        assert model.category_id == "0"

    def test_zero_is_valid_other(self):
        """Category '0' (Other) should be accepted as-is."""
        from src.agents.base.output_models import PrimaryCategoryExtraction

        model = PrimaryCategoryExtraction(
            category_id="0",
            reasoning="Doesn't fit any category",
            confidence=0.3,
        )
        assert model.category_id == "0"


class TestOutputModelDefaults:
    """Tests for output model default values."""

    def test_missing_fields_extraction_defaults(self):
        """MissingFieldsExtraction should default to None/empty."""
        from src.agents.base.output_models import MissingFieldsExtraction

        model = MissingFieldsExtraction()
        assert model.event_type is None
        assert model.event_format is None
        assert model.tags == []

    def test_data_quality_audit_defaults(self):
        """DataQualityAudit should accept a score and default lists to empty."""
        from src.agents.base.output_models import DataQualityAudit

        audit = DataQualityAudit(quality_score=0.85)
        assert audit.quality_score == 0.85
        assert audit.missing_fields == []
        assert audit.normalization_errors == []
        assert audit.recommendations == []

    def test_batch_wrappers_default_to_empty_lists(self):
        """All batch wrapper models should default items to an empty list."""
        from src.agents.base.output_models import (
            ActivitySelectionBatch,
            DataQualityAuditBatch,
            MissingFieldsExtractionBatch,
            TaxonomyAttributesExtractionBatch,
        )

        assert MissingFieldsExtractionBatch().items == []
        assert TaxonomyAttributesExtractionBatch().items == []
        assert DataQualityAuditBatch().items == []
        assert ActivitySelectionBatch().items == []

    def test_taxonomy_attributes_extraction_literal_defaults(self):
        """TaxonomyAttributesExtraction should have correct literal field defaults."""
        from src.agents.base.output_models import TaxonomyAttributesExtraction

        tax = TaxonomyAttributesExtraction()
        assert tax.energy_level == "medium"
        assert tax.social_intensity == "large_group"
        assert tax.cognitive_load == "low"
        assert tax.physical_involvement == "light"
        assert tax.repeatability == "medium"
        assert tax.primary_category is None
        assert tax.subcategory is None
        assert tax.unconstrained_primary_category is None

    def test_activity_selection_item(self):
        """ActivitySelectionItem should store source_event_id and activity_name."""
        from src.agents.base.output_models import ActivitySelectionItem

        item = ActivitySelectionItem(
            source_event_id="evt-123",
            activity_name="Live jazz concert",
        )
        assert item.source_event_id == "evt-123"
        assert item.activity_name == "Live jazz concert"

    def test_subcategory_extraction(self):
        """SubcategoryExtraction should accept id and name fields."""
        from src.agents.base.output_models import SubcategoryExtraction

        sub = SubcategoryExtraction(
            subcategory_id="1.4", subcategory_name="Electronic Music"
        )
        assert sub.subcategory_id == "1.4"
        assert sub.subcategory_name == "Electronic Music"
        assert sub.confidence == 0.7  # default


# =============================================================================
# AGENTS/BASE/BASE_AGENT.PY — helper methods
# =============================================================================


@pytest.fixture
def concrete_agent():
    """Concrete BaseAgent subclass for testing non-abstract helpers."""
    from src.agents.base.base_agent import BaseAgent
    from src.agents.base.task import AgentResult, AgentTask

    class _TestAgent(BaseAgent):
        name = "test"
        prompt_name = "test"

        async def run(self, task: AgentTask) -> AgentResult:
            return AgentResult(
                agent_name=self.name,
                prompt_name=self.prompt_name,
                prompt_version="v1",
                events=task.events,
            )

    return _TestAgent()


class TestBaseAgentChunk:
    """Tests for BaseAgent._chunk static helper."""

    def test_even_split(self, concrete_agent):
        """Should split a list into equal-sized chunks."""
        chunks = list(concrete_agent._chunk([1, 2, 3, 4], 2))
        assert chunks == [[1, 2], [3, 4]]

    def test_remainder_in_last_chunk(self, concrete_agent):
        """Last chunk should contain remaining items when list doesn't divide evenly."""
        chunks = list(concrete_agent._chunk([1, 2, 3, 4, 5], 2))
        assert chunks == [[1, 2], [3, 4], [5]]

    def test_empty_list(self, concrete_agent):
        """Empty input should produce no chunks."""
        assert list(concrete_agent._chunk([], 3)) == []

    def test_chunk_larger_than_list(self, concrete_agent):
        """Single chunk when size exceeds list length."""
        chunks = list(concrete_agent._chunk([1, 2], 10))
        assert chunks == [[1, 2]]


class TestBaseAgentContextBuilders:
    """Tests for BaseAgent._build_event_context and _build_batch_context."""

    def test_build_event_context_minimal(self, concrete_agent, create_event):
        """Should include title, city, and country from a basic event."""
        event = create_event(title="Jazz Night", venue_name="Club XYZ")
        ctx = concrete_agent._build_event_context(event)

        assert ctx["title"] == "Jazz Night"
        assert ctx["city"] == "Barcelona"
        assert ctx["country_code"] == "ES"

    def test_build_event_context_with_description(self, concrete_agent, create_event):
        """Description should be included and truncated at 800 chars."""
        long_desc = "A" * 900
        event = create_event(description=long_desc)
        ctx = concrete_agent._build_event_context(event)

        assert "description" in ctx
        assert len(ctx["description"]) == 800

    def test_build_event_context_no_extra_fields_when_absent(
        self, concrete_agent, create_event
    ):
        """Fields with no data should not appear in context dict."""
        event = create_event()
        ctx = concrete_agent._build_event_context(event)

        assert "artists" not in ctx
        assert "price_raw" not in ctx

    def test_build_batch_context_structure(self, concrete_agent, create_event):
        """Batch context should include event_count and valid events_json."""
        events = [create_event(title=f"Event {i}") for i in range(3)]
        ctx = concrete_agent._build_batch_context(events)

        assert ctx["event_count"] == 3
        items = json.loads(ctx["events_json"])
        assert len(items) == 3
        assert all("source_event_id" in item for item in items)
        assert items[0]["title"] == "Event 0"

    def test_build_batch_context_empty(self, concrete_agent):
        """Empty event list should produce zero count and empty JSON array."""
        ctx = concrete_agent._build_batch_context([])
        assert ctx["event_count"] == 0
        assert json.loads(ctx["events_json"]) == []


# =============================================================================
# AGENTS/VALIDATION/CONFIDENCE.PY
# =============================================================================


class TestComputeConfidenceScore:
    """Tests for compute_confidence_score."""

    def test_bare_event_scores_low(self, create_event):
        """Event with no enrichment fields should score below 0.5."""
        from src.agents.validation.confidence import compute_confidence_score

        event = create_event()
        score = compute_confidence_score(event)
        assert 0.0 <= score <= 0.5

    def test_high_agent_scores_raise_overall(self, create_event):
        """Providing high agent scores should increase the overall confidence."""
        from src.agents.validation.confidence import compute_confidence_score

        event = create_event()
        base_score = compute_confidence_score(event)
        boosted = compute_confidence_score(
            event, agent_scores={"feature_alignment": 0.95, "taxonomy": 0.90}
        )
        assert boosted > base_score

    def test_score_always_in_unit_interval(self, create_event):
        """Score must always be in [0.0, 1.0]."""
        from src.agents.validation.confidence import compute_confidence_score

        event = create_event()
        score = compute_confidence_score(event, agent_scores={"a": 1.0})
        assert 0.0 <= score <= 1.0

    def test_no_agent_scores_uses_field_score(self, create_event):
        """Without agent scores the result should still be a valid float."""
        from src.agents.validation.confidence import compute_confidence_score

        event = create_event()
        score = compute_confidence_score(event, agent_scores=None)
        assert isinstance(score, float)


class TestFlagLowConfidence:
    """Tests for flag_low_confidence."""

    def test_threshold_one_flags_all(self, create_event):
        """All events should be flagged when threshold is 1.0."""
        from src.agents.validation.confidence import flag_low_confidence

        events = [create_event(title=f"Event {i}") for i in range(3)]
        flagged = flag_low_confidence(events, threshold=1.0)
        assert len(flagged) == 3

    def test_threshold_zero_flags_none(self, create_event):
        """No events should be flagged when threshold is 0.0."""
        from src.agents.validation.confidence import flag_low_confidence

        events = [create_event(title=f"Event {i}") for i in range(3)]
        flagged = flag_low_confidence(events, threshold=0.0)
        assert len(flagged) == 0

    def test_returns_event_score_tuples(self, create_event):
        """Each flagged item should be a (EventSchema, float) tuple."""
        from src.agents.validation.confidence import flag_low_confidence

        events = [create_event()]
        flagged = flag_low_confidence(events, threshold=1.0)

        event, score = flagged[0]
        assert hasattr(event, "title")
        assert isinstance(score, float)

    def test_with_agent_scores_mapping(self, create_event):
        """Agent scores keyed by source_event_id should be applied per event."""
        from src.agents.validation.confidence import flag_low_confidence

        event = create_event()
        event_id = str(event.source.source_event_id)
        flagged = flag_low_confidence(
            [event],
            threshold=1.0,
            agent_scores={event_id: {"feature_alignment": 0.9}},
        )
        assert len(flagged) == 1


# =============================================================================
# AGENTS/LLM/PROVIDER_ROUTER.PY
# =============================================================================


class TestGetLLMClient:
    """Tests for the get_llm_client provider factory."""

    def test_anthropic_returns_correct_client(self):
        """'anthropic' provider should return AnthropicLLMClient."""
        from src.agents.llm.anthropic_client import AnthropicLLMClient
        from src.agents.llm.provider_router import get_llm_client

        client = get_llm_client(provider="anthropic")
        assert isinstance(client, AnthropicLLMClient)

    def test_openai_returns_correct_client(self):
        """'openai' provider should return OpenAILLMClient."""
        from src.agents.llm.openai_client import OpenAILLMClient
        from src.agents.llm.provider_router import get_llm_client

        client = get_llm_client(provider="openai")
        assert isinstance(client, OpenAILLMClient)

    def test_ollama_returns_correct_client(self):
        """'ollama' provider should return OllamaLLMClient."""
        from src.agents.llm.ollama_client import OllamaLLMClient
        from src.agents.llm.provider_router import get_llm_client

        client = get_llm_client(provider="ollama")
        assert isinstance(client, OllamaLLMClient)

    def test_llama_is_alias_for_ollama(self):
        """'llama' should be an alias for 'ollama', returning OllamaLLMClient."""
        from src.agents.llm.ollama_client import OllamaLLMClient
        from src.agents.llm.provider_router import get_llm_client

        client = get_llm_client(provider="llama")
        assert isinstance(client, OllamaLLMClient)

    def test_unknown_provider_falls_back_to_anthropic(self):
        """Unknown provider name should default to AnthropicLLMClient."""
        from src.agents.llm.anthropic_client import AnthropicLLMClient
        from src.agents.llm.provider_router import get_llm_client

        client = get_llm_client(provider="unknown_xyz")
        assert isinstance(client, AnthropicLLMClient)

    def test_custom_model_name_forwarded(self):
        """Custom model_name should be stored on the returned client."""
        from src.agents.llm.provider_router import get_llm_client

        client = get_llm_client(provider="ollama", model_name="llama3.2:1b")
        assert client.model_name == "llama3.2:1b"

    def test_provider_case_insensitive(self):
        """Provider string should be lowercased before matching."""
        from src.agents.llm.anthropic_client import AnthropicLLMClient
        from src.agents.llm.provider_router import get_llm_client

        client = get_llm_client(provider="Anthropic")
        assert isinstance(client, AnthropicLLMClient)
