"""
Feature Extractor for LLM-based taxonomy enrichment.

Uses Instructor with OpenAI for structured LLM outputs to:
1. Classify events into taxonomy categories
2. Extract event type, tags, and other fields
3. Select appropriate attribute values based on event context

The extractor injects filtered taxonomy context into prompts
to ensure accurate classification and attribute selection.
"""

import logging
import os
import re
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from src.ingestion.normalization.taxonomy_retriever import (
    get_taxonomy_retriever,
)
from src.schemas.features import (
    FullTaxonomyEnrichmentOutput,
    EventTypeOutput,
    MusicGenresOutput,
    TagsOutput,
)
from src.ingestion.normalization.extraction_models import (
    PrimaryCategoryExtraction,
    SubcategoryExtraction,
    EventTypeExtraction,
    TaxonomyAttributesExtraction,
    MissingFieldsExtraction,
)

if TYPE_CHECKING:
    from src.schemas.event import TaxonomyDimension

logger = logging.getLogger(__name__)


class FeatureExtractor:
    """
    LLM-based feature extractor for event taxonomy enrichment.

    Uses Instructor with OpenAI for structured output to:
    - Classify events into primary categories and subcategories
    - Match events to specific activities from the taxonomy
    - Select appropriate attribute values (energy_level, social_intensity, etc.)
    - Extract event type, music genres, and tags
    - Fill missing fields based on config

    The extractor supports both LLM-based extraction and rule-based fallbacks
    when the LLM is unavailable.

    Example:
        >>> extractor = FeatureExtractor()
        >>> event = {"title": "Techno Party", "description": "Underground techno night"}
        >>> enriched_dim = extractor.enrich_taxonomy_dimension(basic_dim, event)

        # Extract specific fields
        >>> cat = extractor.extract_primary_category(event)
        >>> print(f"Category: {cat.category_id}")

        # Fill missing fields from config
        >>> fields = extractor.fill_missing_fields(event, ["event_type", "tags"])
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
            provider: LLM provider ("openai" supported via Instructor)
            model_name: Model to use (defaults to "gpt-4o-mini")
            api_key: API key (defaults to OPENAI_API_KEY env var)
            temperature: Temperature for generation (0.0-1.0)
            max_tokens: Maximum tokens in response
        """
        self.provider = provider
        self.model_name = model_name or "gpt-4o-mini"
        self.temperature = temperature
        self.max_tokens = max_tokens

        # Get API key
        if api_key:
            self._api_key = api_key
        else:
            self._api_key = os.getenv("OPENAI_API_KEY")

        # Initialize Instructor client (lazy)
        self._client = None
        self._llm_available = None

        # Initialize taxonomy retriever
        self._taxonomy = get_taxonomy_retriever()

    def _get_client(self):
        """Lazy initialization of Instructor client."""
        if self._client is not None:
            return self._client

        if not self._api_key:
            logger.warning("No API key found for OpenAI")
            self._llm_available = False
            return None

        try:
            import instructor
            from openai import OpenAI

            openai_client = OpenAI(api_key=self._api_key)
            self._client = instructor.from_openai(openai_client)
            self._llm_available = True
            return self._client
        except ImportError as e:
            logger.warning(f"Instructor or OpenAI package not installed: {e}")
            self._llm_available = False
            return None
        except Exception as e:
            logger.warning(f"Failed to initialize Instructor client: {e}")
            self._llm_available = False
            return None

    @property
    def is_llm_available(self) -> bool:
        """Check if LLM is available."""
        if self._llm_available is None:
            self._get_client()
        return self._llm_available or False

    # =========================================================================
    # PRIMARY CATEGORY CLASSIFICATION
    # =========================================================================

    def extract_primary_category(
        self, event_context: Dict[str, Any]
    ) -> PrimaryCategoryExtraction:
        """
        Classify event into one of 10 primary categories.

        Args:
            event_context: Event dict with title, description, etc.

        Returns:
            PrimaryCategoryExtraction with category_id, reasoning, confidence
        """
        if not self.is_llm_available:
            # Fallback to rule-based
            category_id = self._infer_primary_category_rules(event_context)
            return PrimaryCategoryExtraction(
                category_id=category_id,
                reasoning="Rule-based classification",
                confidence=0.5,
            )

        client = self._get_client()
        context = self._format_event_context(event_context)
        categories_context = self._taxonomy.get_all_categories_summary()

        try:
            return client.chat.completions.create(
                model=self.model_name,
                response_model=PrimaryCategoryExtraction,
                messages=[
                    {
                        "role": "system",
                        "content": f"Classify events into primary categories:\n{categories_context}",
                    },
                    {
                        "role": "user",
                        "content": f"Classify this event into ONE primary category:\n{context}",
                    },
                ],
                temperature=self.temperature,
            )
        except Exception as e:
            logger.warning(f"Primary category extraction failed: {e}")
            category_id = self._infer_primary_category_rules(event_context)
            return PrimaryCategoryExtraction(
                category_id=category_id,
                reasoning=f"Fallback due to error: {e}",
                confidence=0.3,
            )

    def _infer_primary_category_rules(self, event_context: Dict[str, Any]) -> str:
        """Rule-based primary category inference."""
        title = (event_context.get("title") or "").lower()
        description = (event_context.get("description") or "").lower()
        text = f"{title} {description}"

        # Category mapping based on keywords
        if any(
            w in text for w in ["concert", "music", "dj", "live", "techno", "house"]
        ):
            return "1"  # PLAY & PURE FUN
        elif any(w in text for w in ["workshop", "class", "learn", "masterclass"]):
            return "2"  # LEARN & DISCOVER
        elif any(w in text for w in ["meetup", "community", "network"]):
            return "3"  # CONNECT & BELONG
        elif any(w in text for w in ["art", "exhibition", "gallery", "museum"]):
            return "4"  # CREATE & EXPRESS
        elif any(w in text for w in ["fitness", "yoga", "sports", "run"]):
            return "5"  # MOVE & THRIVE
        elif any(w in text for w in ["food", "wine", "culinary", "tasting"]):
            return "6"  # TASTE & SAVOR
        elif any(w in text for w in ["nature", "outdoor", "hiking", "garden"]):
            return "7"  # EXPLORE & WANDER
        elif any(w in text for w in ["meditation", "wellness", "spa", "retreat"]):
            return "8"  # REST & RECHARGE
        elif any(w in text for w in ["charity", "volunteer", "cause"]):
            return "9"  # GIVE & IMPACT
        elif any(w in text for w in ["festival", "celebration", "carnival"]):
            return "10"  # CELEBRATE & COMMEMORATE
        else:
            return "1"  # Default to PLAY & PURE FUN

    # =========================================================================
    # SUBCATEGORY CLASSIFICATION
    # =========================================================================

    def extract_subcategory(
        self, event_context: Dict[str, Any], category_id: str
    ) -> SubcategoryExtraction:
        """
        Classify into subcategory within a category using RAG context.

        Args:
            event_context: Event dict with title, description, etc.
            category_id: Primary category ID (e.g., "1")

        Returns:
            SubcategoryExtraction with subcategory_id, name, confidence
        """
        if not self.is_llm_available:
            # Fallback - use first subcategory of category
            return SubcategoryExtraction(
                subcategory_id=f"{category_id}.1",
                subcategory_name="Default subcategory",
                confidence=0.3,
            )

        client = self._get_client()
        context = self._format_event_context(event_context)
        subcategory_context = self._taxonomy.get_category_context_for_prompt(
            category_id
        )

        try:
            return client.chat.completions.create(
                model=self.model_name,
                response_model=SubcategoryExtraction,
                messages=[
                    {
                        "role": "system",
                        "content": f"Select the best subcategory for the event:\n{subcategory_context}",
                    },
                    {
                        "role": "user",
                        "content": f"Classify this event into the most appropriate subcategory:\n{context}",
                    },
                ],
                temperature=self.temperature,
            )
        except Exception as e:
            logger.warning(f"Subcategory extraction failed: {e}")
            return SubcategoryExtraction(
                subcategory_id=f"{category_id}.1",
                subcategory_name="Fallback subcategory",
                confidence=0.3,
            )

    # =========================================================================
    # FILL MISSING FIELDS
    # =========================================================================

    def fill_missing_fields(
        self, event_context: Dict[str, Any], fields: List[str]
    ) -> Dict[str, Any]:
        """
        Extract multiple missing fields in one call.

        This method is called by base_api.py when the config specifies
        a `fill_missing` list of fields to extract.

        Args:
            event_context: Event dict with title, description, etc.
            fields: List of field names to extract (e.g., ["event_type", "tags"])

        Returns:
            Dict with extracted field values (only requested fields)
        """
        if not fields:
            return {}

        if not self.is_llm_available:
            return self._fill_missing_fields_rules(event_context, fields)

        client = self._get_client()
        prompt = self._build_missing_fields_prompt(event_context, fields)

        try:
            result = client.chat.completions.create(
                model=self.model_name,
                response_model=MissingFieldsExtraction,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
            )

            # Return only the requested fields with non-None values
            extracted = result.model_dump()
            return {
                k: v
                for k, v in extracted.items()
                if k in fields and v is not None and v != []
            }

        except Exception as e:
            logger.warning(f"Fill missing fields failed: {e}, using rules")
            return self._fill_missing_fields_rules(event_context, fields)

    def _build_missing_fields_prompt(
        self, event_context: Dict[str, Any], fields: List[str]
    ) -> str:
        """Build prompt for extracting missing fields."""
        event_str = self._format_event_context(event_context)

        field_descriptions = {
            "event_type": "Event type (concert, festival, party, workshop, etc.)",
            "tags": "5-10 relevant search tags",
            "energy_level": "Energy level (low, medium, high)",
            "social_intensity": "Social scale (solo, small_group, large_group)",
            "cognitive_load": "Mental effort (low, medium, high)",
            "physical_involvement": "Physical activity (none, light, moderate)",
            "environment": "Environment (indoor, outdoor, digital, mixed)",
            "emotional_output": "Expected emotional outcomes (list of emotions)",
            "risk_level": "Risk level (none, very_low, low, medium)",
            "age_accessibility": "Age appropriateness (all, teens+, adults)",
            "repeatability": "Repeat frequency (high, medium, low)",
        }

        fields_to_extract = "\n".join(
            f"- {f}: {field_descriptions.get(f, f)}" for f in fields
        )

        return f"""Analyze this event and extract the following fields:

{fields_to_extract}

Event:
{event_str}

Extract the requested fields based on the event information."""

    def _fill_missing_fields_rules(
        self, event_context: Dict[str, Any], fields: List[str]
    ) -> Dict[str, Any]:
        """Rule-based fallback for missing field extraction."""
        result = {}
        title = (event_context.get("title") or "").lower()
        description = (event_context.get("description") or "").lower()
        text = f"{title} {description}"

        if "event_type" in fields:
            result["event_type"] = self._infer_event_type_rules(event_context)

        if "tags" in fields:
            result["tags"] = self._infer_tags_rules(event_context)

        if "energy_level" in fields:
            if any(w in text for w in ["festival", "rave", "party", "techno"]):
                result["energy_level"] = "high"
            elif any(w in text for w in ["workshop", "exhibition", "gallery"]):
                result["energy_level"] = "medium"
            else:
                result["energy_level"] = "medium"

        if "social_intensity" in fields:
            if any(w in text for w in ["festival", "party", "concert"]):
                result["social_intensity"] = "large_group"
            elif any(w in text for w in ["workshop", "meetup"]):
                result["social_intensity"] = "small_group"
            else:
                result["social_intensity"] = "large_group"

        if "environment" in fields:
            if any(w in text for w in ["outdoor", "garden", "park", "beach"]):
                result["environment"] = "outdoor"
            elif any(w in text for w in ["online", "virtual", "stream"]):
                result["environment"] = "digital"
            else:
                result["environment"] = "indoor"

        if "age_accessibility" in fields:
            if any(w in text for w in ["club", "bar", "nightlife", "18+"]):
                result["age_accessibility"] = "adults"
            elif any(w in text for w in ["family", "kids", "all ages"]):
                result["age_accessibility"] = "all"
            else:
                result["age_accessibility"] = "adults"

        return result

    # =========================================================================
    # HIERARCHY PROPAGATION
    # =========================================================================

    def propagate_hierarchy(self, subcategory_id: str) -> Dict[str, Any]:
        """
        Get full hierarchy from subcategory ID.

        When a subcategory is set or changed, this method returns
        the complete hierarchy data including primary_category.

        Args:
            subcategory_id: Subcategory ID (e.g., "1.4")

        Returns:
            Dict with primary_category, subcategory_name, values, etc.
        """
        sub = self._taxonomy.get_subcategory_by_id(subcategory_id)
        if not sub:
            return {}

        category_id = subcategory_id.split(".")[0]
        return {
            "primary_category": self._get_category_value(category_id),
            "subcategory": subcategory_id,
            "subcategory_name": sub.get("name"),
            "subcategory_values": sub.get("values", []),
            "_category_id": category_id,
        }

    def _get_category_value(self, category_id: str) -> str:
        """Map category ID to category enum value."""
        category_map = {
            "1": "play_and_pure_fun",
            "2": "learn_and_discover",
            "3": "connect_and_belong",
            "4": "create_and_express",
            "5": "move_and_thrive",
            "6": "taste_and_savor",
            "7": "explore_and_wander",
            "8": "rest_and_recharge",
            "9": "give_and_impact",
            "10": "celebrate_and_commemorate",
        }
        return category_map.get(category_id, "play_and_pure_fun")

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
        from src.schemas.event import TaxonomyDimension

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
        client = self._get_client()
        if not client:
            return self._enrich_with_rules(event_context)

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

            # Build the prompts
            system_prompt = self._build_enrichment_system_prompt(taxonomy_context)
            user_prompt = self._build_enrichment_user_prompt(event_str)

            # Call LLM with structured output using Instructor
            result = client.chat.completions.create(
                model=self.model_name,
                response_model=FullTaxonomyEnrichmentOutput,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=self.temperature,
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
            client = self._get_client()
            try:
                event_str = self._format_event_context(event_context)
                result = client.chat.completions.create(
                    model=self.model_name,
                    response_model=EventTypeOutput,
                    messages=[
                        {
                            "role": "user",
                            "content": f"""Classify this event into one of these types:
concert, festival, party, workshop, lecture, meetup, sports, exhibition,
conference, nightlife, theater, dance, food_beverage, art_show, other

Event:
{event_str}

Select the single most appropriate event type.""",
                        }
                    ],
                    temperature=self.temperature,
                )
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
            client = self._get_client()
            try:
                event_str = self._format_event_context(event_context)
                result = client.chat.completions.create(
                    model=self.model_name,
                    response_model=MusicGenresOutput,
                    messages=[
                        {
                            "role": "user",
                            "content": f"""Identify the music genres for this event.
If this is not a music event, return an empty list.

Event:
{event_str}

Return a list of relevant music genres (e.g., electronic, techno, house, ambient, jazz, etc.).""",
                        }
                    ],
                    temperature=self.temperature,
                )
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
            client = self._get_client()
            try:
                event_str = self._format_event_context(event_context)
                result = client.chat.completions.create(
                    model=self.model_name,
                    response_model=TagsOutput,
                    messages=[
                        {
                            "role": "user",
                            "content": f"""Generate relevant search tags for this event.
Include genre tags, activity tags, and atmosphere tags.

Event:
{event_str}

Return 5-10 relevant tags for search and filtering.""",
                        }
                    ],
                    temperature=self.temperature,
                )
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
          fill_missing: ["event_type", "tags"]
    """
    return FeatureExtractor(
        provider=config.get("provider", "openai"),
        model_name=config.get("model_name"),
        temperature=config.get("temperature", 0.1),
        max_tokens=config.get("max_tokens", 2000),
    )
