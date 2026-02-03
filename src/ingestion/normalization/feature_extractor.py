"""
Feature Extractor for LLM-based taxonomy enrichment.

Uses LangChain with RAG (Retrieval Augmented Generation) to:
1. Classify events into taxonomy categories
2. Match activities from the taxonomy
3. Select appropriate attribute values based on event context

The extractor injects filtered taxonomy context into prompts
to ensure accurate classification and attribute selection.
"""

import logging
import re
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from src.ingestion.normalization.llm_client import (
    LangChainLLMClient,
    create_llm_client,
)
from src.ingestion.normalization.taxonomy_retriever import (
    get_taxonomy_retriever,
)
from src.ingestion.normalization.feature_models import (
    FullTaxonomyEnrichmentOutput,
    EventTypeOutput,
    MusicGenresOutput,
    TagsOutput,
)

if TYPE_CHECKING:
    from src.ingestion.normalization.event_schema import TaxonomyDimension

logger = logging.getLogger(__name__)


class FeatureExtractor:
    """
    LLM-based feature extractor for event taxonomy enrichment.

    Uses LangChain with structured output to:
    - Classify events into primary categories and subcategories
    - Match events to specific activities from the taxonomy
    - Select appropriate attribute values (energy_level, social_intensity, etc.)
    - Extract event type, music genres, and tags

    The extractor supports both LLM-based extraction and rule-based fallbacks
    when the LLM is unavailable.

    Example:
        >>> extractor = FeatureExtractor()
        >>> event = {"title": "Techno Party", "description": "Underground techno night"}
        >>> enriched_dim = extractor.enrich_taxonomy_dimension(basic_dim, event)
    """

    def __init__(
        self,
        provider: str = "openai",
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 2000,
    ):
        """
        Initialize the feature extractor.

        Args:
            provider: LLM provider ("openai" or "anthropic")
            model_name: Model to use (defaults based on provider)
            api_key: API key (defaults to env var)
            temperature: Temperature for generation (0.0-1.0)
            max_tokens: Maximum tokens in response
        """
        self.provider = provider
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens

        # Initialize LLM client (with fallback to rules)
        self._llm_client = create_llm_client(
            provider=provider,
            model_name=model_name,
            api_key=api_key,
            temperature=temperature,
            fallback_to_rules=True,
        )

        # Initialize taxonomy retriever
        self._taxonomy = get_taxonomy_retriever()

    @property
    def is_llm_available(self) -> bool:
        """Check if LLM is available."""
        return isinstance(self._llm_client, LangChainLLMClient)

    # =========================================================================
    # MAIN ENRICHMENT METHOD
    # =========================================================================

    def enrich_taxonomy_dimension(
        self,
        dimension: "TaxonomyDimension",
        event_context: Dict[str, Any],
    ) -> "TaxonomyDimension":
        """
        Enrich a TaxonomyDimension with activity-level fields.

        Given primary_category and subcategory, populate:
        - subcategory_name (if not set)
        - activity_id, activity_name (best matching activity)
        - energy_level, social_intensity, cognitive_load, physical_involvement
        - cost_level, time_scale, environment, emotional_output
        - risk_level, age_accessibility, repeatability

        Args:
            dimension: TaxonomyDimension with at least primary_category
            event_context: Event dict with title, description, cost, duration, etc.

        Returns:
            New TaxonomyDimension with all fields populated
        """
        from src.ingestion.normalization.event_schema import TaxonomyDimension

        # Build enriched data starting with existing values
        enriched_data = {
            "primary_category": dimension.primary_category,
            "subcategory": dimension.subcategory,
            "subcategory_name": dimension.subcategory_name,
            "values": dimension.values.copy() if dimension.values else [],
            "confidence": dimension.confidence,
            "activity_id": dimension.activity_id,
            "activity_name": dimension.activity_name,
            "emotional_output": (
                dimension.emotional_output.copy() if dimension.emotional_output else []
            ),
        }

        # Get subcategory details if not already populated
        if dimension.subcategory and not dimension.subcategory_name:
            sub = self._taxonomy.get_subcategory_by_id(dimension.subcategory)
            if sub:
                enriched_data["subcategory_name"] = sub.get("name")
                if not enriched_data["values"]:
                    enriched_data["values"] = sub.get("values", [])

        # Get category ID for context filtering
        category_id = None
        if dimension.subcategory:
            category_id = dimension.subcategory.split(".")[0]

        # Use LLM or fallback for attribute enrichment
        if self.is_llm_available:
            attributes = self._enrich_with_llm(
                event_context, dimension.subcategory, category_id
            )
        else:
            attributes = self._enrich_with_rules(event_context)

        # Merge attributes into enriched data
        for key, value in attributes.items():
            if value is not None:
                enriched_data[key] = value

        # Always use rule-based for cost_level and time_scale (more reliable)
        enriched_data["cost_level"] = self._infer_cost_level(event_context)
        enriched_data["time_scale"] = self._infer_time_scale(event_context)

        return TaxonomyDimension(**enriched_data)

    # =========================================================================
    # LLM-BASED ENRICHMENT
    # =========================================================================

    def _enrich_with_llm(
        self,
        event_context: Dict[str, Any],
        subcategory_id: Optional[str],
        category_id: Optional[str],
    ) -> Dict[str, Any]:
        """
        Use LLM to enrich taxonomy attributes.

        Injects filtered taxonomy context into the prompt.
        """
        try:
            # Build context string
            event_str = self._format_event_context(event_context)

            # Get taxonomy context filtered by category
            if subcategory_id:
                taxonomy_context = self._taxonomy.get_subcategory_context_for_prompt(
                    subcategory_id
                )
            elif category_id:
                taxonomy_context = self._taxonomy.get_category_context_for_prompt(
                    category_id
                )
            else:
                taxonomy_context = self._taxonomy.get_attribute_options_string()

            # Build the prompt
            system_prompt = self._build_enrichment_system_prompt(taxonomy_context)
            user_prompt = self._build_enrichment_user_prompt(event_str)

            # Call LLM with structured output
            result = self._llm_client.invoke_with_context(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                output_schema=FullTaxonomyEnrichmentOutput,
            )

            return result.model_dump()

        except Exception as e:
            logger.warning(f"LLM enrichment failed: {e}, falling back to rules")
            return self._enrich_with_rules(event_context)

    def _build_enrichment_system_prompt(self, taxonomy_context: str) -> str:
        """Build system prompt for taxonomy enrichment."""
        return f"""You are an expert event classifier for the Human Experience Taxonomy.

Your task is to analyze event information and select the most appropriate attributes
from the taxonomy based on the event's characteristics.

## Taxonomy Context (filtered for this category):
{taxonomy_context}

## Attribute Selection Guidelines:

**energy_level**: Consider the activity type, music style, time of day
- "low": Calm, relaxed events (exhibitions, talks, ambient music)
- "medium": Moderate engagement (workshops, casual meetups)
- "high": Intense, active events (raves, festivals, dance parties)

**social_intensity**: Consider venue size, event format, typical attendance
- "solo": Individual experiences (some exhibitions, digital events)
- "small_group": Intimate gatherings (workshops, small venue events, 2-10 people)
- "large_group": Mass gatherings (festivals, large club events, 10+ people)

**cognitive_load**: Consider learning/focus requirements
- "low": Passive enjoyment (concerts, parties)
- "medium": Some active engagement (workshops, interactive events)
- "high": Deep focus/learning (masterclasses, technical workshops)

**physical_involvement**: Consider dancing, movement, activity level
- "none": Seated/stationary (lectures, screenings)
- "light": Standing, some movement (exhibitions, casual events)
- "moderate": Active movement (dancing, sports, festivals)

**environment**: Consider venue type
- "indoor": Clubs, theaters, galleries
- "outdoor": Festivals, park events, rooftops
- "digital": Online/streaming events
- "mixed": Hybrid or multi-venue events

**age_accessibility**: Consider venue restrictions, content
- "all": Family-friendly
- "teens+": 13+ appropriate
- "adults": 18+/21+ venues (clubs, bars)

**repeatability**: How often people typically attend similar events
- "high": Weekly/regular (club nights, meetups)
- "medium": Monthly (special events, concerts)
- "low": Rare/unique (festivals, special performances)

**risk_level**: Physical or other risks
- "none": No risk
- "very_low": Minimal (most indoor events)
- "low": Some crowd/activity risk
- "medium": Active sports, adventure activities

Respond with a JSON object matching the requested schema."""

    def _build_enrichment_user_prompt(self, event_str: str) -> str:
        """Build user prompt for taxonomy enrichment."""
        return f"""Analyze this event and select the most appropriate taxonomy attributes:

{event_str}

Select ONE value for each attribute based on the event characteristics.
If an activity from the taxonomy matches this event, include its ID and name.
Also suggest relevant emotional outputs (e.g., "joy", "excitement", "connection", "energy")."""

    # =========================================================================
    # RULE-BASED FALLBACK ENRICHMENT
    # =========================================================================

    def _enrich_with_rules(self, event_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Rule-based fallback for attribute selection when LLM is unavailable.
        """
        title = (event_context.get("title") or "").lower()
        description = (event_context.get("description") or "").lower()
        text = f"{title} {description}"

        result = {}

        # Energy level
        if any(
            w in text
            for w in ["festival", "rave", "party", "club", "techno", "house", "night"]
        ):
            result["energy_level"] = "high"
        elif any(w in text for w in ["workshop", "talk", "exhibition", "gallery"]):
            result["energy_level"] = "medium"
        elif any(w in text for w in ["meditation", "yoga", "chill", "ambient"]):
            result["energy_level"] = "low"
        else:
            result["energy_level"] = "medium"

        # Social intensity
        if any(w in text for w in ["festival", "party", "concert", "club"]):
            result["social_intensity"] = "large_group"
        elif any(w in text for w in ["workshop", "class", "meetup", "intimate"]):
            result["social_intensity"] = "small_group"
        else:
            result["social_intensity"] = "large_group"

        # Cognitive load
        if any(w in text for w in ["workshop", "class", "lecture", "learn", "course"]):
            result["cognitive_load"] = "medium"
        elif any(w in text for w in ["masterclass", "seminar", "training"]):
            result["cognitive_load"] = "high"
        else:
            result["cognitive_load"] = "low"

        # Physical involvement
        if any(w in text for w in ["dance", "yoga", "sports", "run", "fitness"]):
            result["physical_involvement"] = "moderate"
        elif any(w in text for w in ["concert", "festival", "party", "club"]):
            result["physical_involvement"] = "light"
        else:
            result["physical_involvement"] = "none"

        # Environment
        if any(w in text for w in ["outdoor", "garden", "park", "beach", "rooftop"]):
            result["environment"] = "outdoor"
        elif any(w in text for w in ["online", "virtual", "stream", "digital"]):
            result["environment"] = "digital"
        elif any(w in text for w in ["hybrid", "mixed"]):
            result["environment"] = "mixed"
        else:
            result["environment"] = "indoor"

        # Risk level
        result["risk_level"] = "very_low"

        # Age accessibility
        if any(w in text for w in ["club", "bar", "nightlife", "18+", "21+"]):
            result["age_accessibility"] = "adults"
        elif any(w in text for w in ["family", "kids", "children", "all ages"]):
            result["age_accessibility"] = "all"
        else:
            result["age_accessibility"] = "adults"  # Default for music events

        # Repeatability
        if any(w in text for w in ["festival", "carnival", "annual", "special"]):
            result["repeatability"] = "low"
        elif any(w in text for w in ["weekly", "regular", "every"]):
            result["repeatability"] = "high"
        else:
            result["repeatability"] = "medium"

        # Emotional output
        result["emotional_output"] = self._infer_emotional_output(text)

        return result

    def _infer_emotional_output(self, text: str) -> List[str]:
        """Infer emotional outputs from event text."""
        emotions = []

        emotion_keywords = {
            "joy": ["party", "fun", "celebration", "happy"],
            "excitement": ["festival", "live", "concert", "rave"],
            "connection": ["meetup", "community", "together", "social"],
            "energy": ["dance", "techno", "electronic", "club"],
            "relaxation": ["chill", "ambient", "lounge", "relax"],
            "inspiration": ["art", "exhibition", "creative", "gallery"],
            "growth": ["workshop", "learn", "skill", "course"],
            "belonging": ["community", "collective", "tribe"],
        }

        for emotion, keywords in emotion_keywords.items():
            if any(kw in text for kw in keywords):
                emotions.append(emotion)

        return emotions if emotions else ["enjoyment"]

    # =========================================================================
    # SPECIFIC FEATURE EXTRACTION METHODS
    # =========================================================================

    def extract_event_type(self, event_context: Dict[str, Any]) -> Optional[str]:
        """
        Extract event type from event context.

        Args:
            event_context: Event dict with title, description

        Returns:
            Event type string or None
        """
        if self.is_llm_available:
            try:
                event_str = self._format_event_context(event_context)
                prompt = f"""Classify this event into one of these types:
concert, festival, party, workshop, lecture, meetup, sports, exhibition,
conference, nightlife, theater, dance, food_beverage, art_show, other

Event:
{event_str}

Select the single most appropriate event type."""

                result = self._llm_client.invoke_structured(prompt, EventTypeOutput)
                return result.event_type
            except Exception as e:
                logger.warning(f"Event type extraction failed: {e}")

        # Fallback
        return self._infer_event_type_rules(event_context)

    def _infer_event_type_rules(self, event_context: Dict[str, Any]) -> str:
        """Rule-based event type inference."""
        title = (event_context.get("title") or "").lower()

        if "festival" in title:
            return "festival"
        elif any(w in title for w in ["party", "fiesta"]):
            return "party"
        elif any(w in title for w in ["concert", "live"]):
            return "concert"
        elif any(w in title for w in ["workshop", "masterclass"]):
            return "workshop"
        elif "exhibition" in title:
            return "exhibition"
        elif "conference" in title:
            return "conference"
        else:
            return "nightlife"

    def extract_music_genres(self, event_context: Dict[str, Any]) -> List[str]:
        """
        Extract music genres from event context.

        Args:
            event_context: Event dict with title, description, artists

        Returns:
            List of music genres
        """
        if self.is_llm_available:
            try:
                event_str = self._format_event_context(event_context)
                prompt = f"""Identify the music genres for this event.
If this is not a music event, return an empty list.

Event:
{event_str}

Return a list of relevant music genres (e.g., electronic, techno, house, ambient, jazz, etc.)."""

                result = self._llm_client.invoke_structured(prompt, MusicGenresOutput)
                return result.genres
            except Exception as e:
                logger.warning(f"Genre extraction failed: {e}")

        # Fallback
        return self._infer_genres_rules(event_context)

    def _infer_genres_rules(self, event_context: Dict[str, Any]) -> List[str]:
        """Rule-based genre inference."""
        text = f"{event_context.get('title', '')} {event_context.get('description', '')}".lower()
        genres = []

        genre_keywords = {
            "techno": ["techno"],
            "house": ["house"],
            "electronic": ["electronic", "edm", "electro"],
            "ambient": ["ambient", "chill"],
            "trance": ["trance"],
            "drum_and_bass": ["drum and bass", "dnb", "d&b"],
            "hip_hop": ["hip hop", "hip-hop", "rap"],
            "jazz": ["jazz"],
            "rock": ["rock"],
        }

        for genre, keywords in genre_keywords.items():
            if any(kw in text for kw in keywords):
                genres.append(genre)

        return genres if genres else ["electronic"]  # Default for ra.co events

    def extract_tags(self, event_context: Dict[str, Any]) -> List[str]:
        """
        Generate tags for an event.

        Args:
            event_context: Event dict with title, description

        Returns:
            List of tags
        """
        if self.is_llm_available:
            try:
                event_str = self._format_event_context(event_context)
                prompt = f"""Generate relevant search tags for this event.
Include genre tags, activity tags, and atmosphere tags.

Event:
{event_str}

Return 5-10 relevant tags for search and filtering."""

                result = self._llm_client.invoke_structured(prompt, TagsOutput)
                return result.tags
            except Exception as e:
                logger.warning(f"Tag extraction failed: {e}")

        # Fallback
        return self._infer_tags_rules(event_context)

    def _infer_tags_rules(self, event_context: Dict[str, Any]) -> List[str]:
        """Rule-based tag generation."""
        tags = []
        title = (event_context.get("title") or "").lower()

        tag_keywords = {
            "music": ["music", "dj", "live"],
            "electronic": ["electronic", "techno", "house"],
            "party": ["party", "fiesta"],
            "nightlife": ["club", "night"],
            "festival": ["festival"],
            "workshop": ["workshop", "class"],
            "art": ["art", "exhibition", "gallery"],
        }

        for tag, keywords in tag_keywords.items():
            if any(kw in title for kw in keywords):
                tags.append(tag)

        return tags if tags else ["event"]

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def _format_event_context(self, event_context: Dict[str, Any]) -> str:
        """Format event context as string for prompts."""
        lines = []

        if event_context.get("title"):
            lines.append(f"Title: {event_context['title']}")

        if event_context.get("description"):
            desc = event_context["description"][:500]
            lines.append(f"Description: {desc}")

        if event_context.get("venue_name"):
            lines.append(f"Venue: {event_context['venue_name']}")

        if event_context.get("city"):
            lines.append(f"City: {event_context['city']}")

        if event_context.get("artists"):
            artists = event_context["artists"]
            if isinstance(artists, list):
                artists = ", ".join(str(a) for a in artists[:5])
            lines.append(f"Artists: {artists}")

        if event_context.get("cost") or event_context.get("price"):
            price = event_context.get("cost") or event_context.get("price")
            lines.append(f"Price: {price}")

        if event_context.get("duration_minutes"):
            lines.append(f"Duration: {event_context['duration_minutes']} minutes")

        return "\n".join(lines)

    def _infer_cost_level(self, event_context: Dict[str, Any]) -> str:
        """Infer cost level from price data."""
        price = None

        if event_context.get("minimum_price"):
            price = event_context["minimum_price"]
        elif event_context.get("cost"):
            cost_str = str(event_context["cost"])
            match = re.search(r"[\d.]+", cost_str)
            if match:
                try:
                    price = float(match.group())
                except ValueError:
                    pass

        if event_context.get("is_free") or (price is not None and price == 0):
            return "free"
        elif price is None:
            return "medium"
        elif price <= 15:
            return "low"
        elif price <= 50:
            return "medium"
        else:
            return "high"

    def _infer_time_scale(self, event_context: Dict[str, Any]) -> str:
        """Infer time scale from duration."""
        duration = event_context.get("duration_minutes")

        if duration:
            if duration <= 120:
                return "short"
            elif duration <= 480:
                return "long"
            else:
                return "recurring"

        title = (event_context.get("title") or "").lower()
        if "festival" in title:
            return "long"
        if "workshop" in title:
            return "short"

        return "long"


# =============================================================================
# FACTORY FUNCTION
# =============================================================================


def create_feature_extractor_from_config(
    config: Dict[str, Any],
) -> FeatureExtractor:
    """
    Factory function to create FeatureExtractor from config.

    Args:
        config: Dict with feature extraction settings

    Returns:
        Configured FeatureExtractor instance

    Example config:
        feature_extraction:
          enabled: true
          provider: "openai"
          model_name: "gpt-4o-mini"
    """
    return FeatureExtractor(
        provider=config.get("provider", "openai"),
        model_name=config.get("model_name"),
        temperature=config.get("temperature", 0.1),
        max_tokens=config.get("max_tokens", 2000),
    )
