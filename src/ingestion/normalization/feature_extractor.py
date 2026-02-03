"""
Feature Extractor for LLM-based field filling.

Uses LLM to fill missing fields based on event context.
Can infer:
- Primary category and subcategory
- Activity matches
- Taxonomy attributes (energy_level, social_intensity, etc.)
- Event type
- Tags
"""

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.ingestion.normalization.event_schema import TaxonomyDimension

logger = logging.getLogger(__name__)


class FeatureExtractor:
    """
    Uses LLM to fill missing fields based on event context.

    Supports:
    - OpenAI API (GPT-3.5, GPT-4)
    - Anthropic API (Claude)

    The extractor analyzes event title, description, and other available
    fields to infer missing information.
    """

    def __init__(
        self,
        model_name: str = "gpt-3.5-turbo",
        api_key: Optional[str] = None,
        provider: str = "openai",
        temperature: float = 0.3,
        max_tokens: int = 1000,
    ):
        """
        Initialize the feature extractor.

        Args:
            model_name: Model to use (e.g., "gpt-3.5-turbo", "gpt-4", "claude-3-haiku")
            api_key: API key (defaults to env var OPENAI_API_KEY or ANTHROPIC_API_KEY)
            provider: "openai" or "anthropic"
            temperature: Temperature for generation (0.0-1.0)
            max_tokens: Maximum tokens in response
        """
        self.model_name = model_name
        self.provider = provider
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

        self._client = None

    def _get_client(self):
        """Get or create API client."""
        if self._client is not None:
            return self._client

        if not self.api_key:
            logger.warning(f"No API key found for {self.provider}")
            return None

        if self.provider == "openai":
            try:
                from openai import OpenAI

                self._client = OpenAI(api_key=self.api_key)
            except ImportError:
                logger.warning("openai package not installed")
                return None
        elif self.provider == "anthropic":
            try:
                import anthropic

                self._client = anthropic.Anthropic(api_key=self.api_key)
            except ImportError:
                logger.warning("anthropic package not installed")
                return None

        return self._client

    def extract_missing_fields(
        self,
        event: Dict[str, Any],
        missing_fields: List[str],
    ) -> Dict[str, Any]:
        """
        Use LLM to infer missing fields from event context.

        Args:
            event: Event dict with available fields
            missing_fields: List of field names to fill

        Returns:
            Dict with inferred values for missing fields

        Supported fields:
        - primary_category
        - subcategory
        - event_type
        - tags
        - activity_id (requires subcategory context)
        - energy_level, social_intensity, cognitive_load, etc.
        """
        client = self._get_client()
        if not client:
            return self._fallback_extraction(event, missing_fields)

        # Build context from event
        context = self._build_event_context(event)

        # Build prompt
        prompt = self._build_extraction_prompt(context, missing_fields)

        try:
            response = self._call_llm(prompt)
            return self._parse_extraction_response(response, missing_fields)
        except Exception as e:
            logger.error(f"LLM extraction failed: {e}")
            return self._fallback_extraction(event, missing_fields)

    def match_activity(
        self,
        event_title: str,
        event_description: str,
        subcategory_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Find best activity match from taxonomy using semantic similarity.

        Uses LLM to understand event context and match against
        available activities in the subcategory.

        Args:
            event_title: Event title
            event_description: Event description
            subcategory_id: Subcategory ID to search within

        Returns:
            Dict with activity_id and match_confidence, or None
        """
        from src.ingestion.normalization.taxonomy import get_activities_for_subcategory

        activities = get_activities_for_subcategory(subcategory_id)
        if not activities:
            return None

        client = self._get_client()
        if not client:
            # Fall back to keyword matching
            from src.ingestion.normalization.taxonomy import find_best_activity_match

            return find_best_activity_match(
                f"{event_title} {event_description}", subcategory_id
            )

        # Build activity list for prompt
        activity_list = "\n".join(
            f"- {a['activity_id']}: {a.get('name', 'Unknown')}" for a in activities
        )

        prompt = f"""Given this event:
Title: {event_title}
Description: {event_description}

Match it to the most appropriate activity from this list:
{activity_list}

Respond with JSON:
{{"activity_id": "uuid-of-best-match", "confidence": 0.0-1.0, "reasoning": "brief explanation"}}

If no good match exists, respond with:
{{"activity_id": null, "confidence": 0.0, "reasoning": "no suitable match"}}"""

        try:
            response = self._call_llm(prompt)
            result = json.loads(response)
            if result.get("activity_id"):
                # Find the full activity data
                for activity in activities:
                    if activity.get("activity_id") == result["activity_id"]:
                        return {
                            **activity,
                            "_match_confidence": result.get("confidence", 0.5),
                            "_match_reasoning": result.get("reasoning"),
                        }
            return None
        except Exception as e:
            logger.error(f"Activity matching failed: {e}")
            return None

    def infer_taxonomy_attributes(
        self,
        event: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Infer taxonomy attributes from event context.

        Uses LLM to analyze event and determine:
        - energy_level: low | medium | high
        - social_intensity: solo | small_group | large_group
        - cognitive_load: low | medium | high
        - physical_involvement: none | light | moderate
        - cost_level: free | low | medium | high
        - time_scale: short | long | recurring
        - environment: indoor | outdoor | digital | mixed
        - risk_level: none | very_low | low | medium
        - age_accessibility: all | teens+ | adults

        Args:
            event: Event dict with title, description, price, etc.

        Returns:
            Dict with inferred attribute values
        """
        client = self._get_client()
        context = self._build_event_context(event)

        # Price-based cost level inference (doesn't need LLM)
        cost_level = self._infer_cost_level(event)

        # Duration-based time scale inference (doesn't need LLM)
        time_scale = self._infer_time_scale(event)

        if not client:
            # Return rule-based defaults
            return {
                "energy_level": "medium",
                "social_intensity": "large_group",
                "cognitive_load": "low",
                "physical_involvement": "light",
                "cost_level": cost_level,
                "time_scale": time_scale,
                "environment": "indoor",
                "risk_level": "very_low",
                "age_accessibility": "adults",
            }

        prompt = f"""Analyze this event and infer its attributes:

{context}

Respond with JSON containing these attributes:
- energy_level: "low" | "medium" | "high"
- social_intensity: "solo" | "small_group" | "large_group"
- cognitive_load: "low" | "medium" | "high"
- physical_involvement: "none" | "light" | "moderate"
- environment: "indoor" | "outdoor" | "digital" | "mixed"
- risk_level: "none" | "very_low" | "low" | "medium"
- age_accessibility: "all" | "teens+" | "adults"

Only include fields you can reasonably infer. Example:
{{"energy_level": "high", "social_intensity": "large_group", "environment": "indoor"}}"""

        try:
            response = self._call_llm(prompt)
            result = json.loads(response)

            # Add rule-based inferences
            result["cost_level"] = cost_level
            result["time_scale"] = time_scale

            return result
        except Exception as e:
            logger.error(f"Attribute inference failed: {e}")
            return {
                "cost_level": cost_level,
                "time_scale": time_scale,
            }

    def _build_event_context(self, event: Dict[str, Any]) -> str:
        """Build context string from event data."""
        lines = []

        if event.get("title"):
            lines.append(f"Title: {event['title']}")

        if event.get("description"):
            # Truncate long descriptions
            desc = event["description"][:500]
            lines.append(f"Description: {desc}")

        if event.get("venue_name"):
            lines.append(f"Venue: {event['venue_name']}")

        if event.get("city"):
            lines.append(f"City: {event['city']}")

        if event.get("artists"):
            artists = event["artists"]
            if isinstance(artists, list):
                artists = ", ".join(str(a) for a in artists[:5])
            lines.append(f"Artists: {artists}")

        if event.get("cost") or event.get("price"):
            price = event.get("cost") or event.get("price")
            lines.append(f"Price: {price}")

        return "\n".join(lines)

    def _build_extraction_prompt(
        self,
        context: str,
        missing_fields: List[str],
    ) -> str:
        """Build extraction prompt for missing fields."""
        field_descriptions = {
            "primary_category": "Primary experience category from: play_and_fun, exploration_and_adventure, creation_and_expression, learning_and_intellectual, social_connection, body_and_movement, challenge_and_achievement, relaxation_and_escapism, identity_and_meaning, contribution_and_impact",
            "subcategory": "Subcategory ID (e.g., '1.4' for Music & Rhythm Play)",
            "event_type": "Event type from: concert, festival, party, workshop, lecture, meetup, sports, exhibition, conference, nightlife, theater, dance, food_beverage, art_show, other",
            "tags": "List of relevant tags for search/filtering",
        }

        fields_info = "\n".join(
            f"- {f}: {field_descriptions.get(f, 'Infer appropriate value')}"
            for f in missing_fields
        )

        return f"""Analyze this event and extract the following fields:

{context}

Fields to extract:
{fields_info}

Respond with JSON containing only the requested fields:
{{"field_name": "value", ...}}

For list fields like tags, use an array: ["tag1", "tag2", ...]"""

    def _call_llm(self, prompt: str) -> str:
        """Call the LLM and return response text."""
        client = self._get_client()
        if not client:
            raise ValueError("No LLM client available")

        if self.provider == "openai":
            response = client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            return response.choices[0].message.content

        elif self.provider == "anthropic":
            response = client.messages.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            return response.content[0].text

        raise ValueError(f"Unknown provider: {self.provider}")

    def _parse_extraction_response(
        self,
        response: str,
        missing_fields: List[str],
    ) -> Dict[str, Any]:
        """Parse LLM response for extracted fields."""
        # Try to extract JSON from response
        try:
            # Find JSON in response (may be surrounded by text)
            json_match = response
            if "```json" in response:
                json_match = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                json_match = response.split("```")[1].split("```")[0]

            result = json.loads(json_match.strip())

            # Filter to only requested fields
            return {k: v for k, v in result.items() if k in missing_fields}
        except (json.JSONDecodeError, IndexError) as e:
            logger.warning(f"Failed to parse LLM response: {e}")
            return {}

    def _fallback_extraction(
        self,
        event: Dict[str, Any],
        missing_fields: List[str],
    ) -> Dict[str, Any]:
        """
        Fallback extraction using rule-based logic.

        Used when LLM is not available.
        """
        result = {}
        title = (event.get("title") or "").lower()

        if "primary_category" in missing_fields:
            # Simple keyword-based inference
            if any(w in title for w in ["festival", "outdoor", "travel"]):
                result["primary_category"] = "exploration_and_adventure"
            elif any(w in title for w in ["workshop", "class", "learn"]):
                result["primary_category"] = "learning_and_intellectual"
            elif any(w in title for w in ["yoga", "gym", "run", "fitness"]):
                result["primary_category"] = "body_and_movement"
            else:
                result["primary_category"] = "play_and_fun"

        if "event_type" in missing_fields:
            if "festival" in title:
                result["event_type"] = "festival"
            elif any(w in title for w in ["party", "fiesta"]):
                result["event_type"] = "party"
            elif any(w in title for w in ["concert", "live"]):
                result["event_type"] = "concert"
            elif any(w in title for w in ["workshop", "masterclass"]):
                result["event_type"] = "workshop"
            else:
                result["event_type"] = "nightlife"

        if "tags" in missing_fields:
            tags = []
            if "music" in title or "dj" in title:
                tags.append("music")
            if "electronic" in title or "techno" in title:
                tags.append("electronic")
            if "party" in title:
                tags.append("party")
            result["tags"] = tags if tags else ["event"]

        return result

    def _infer_cost_level(self, event: Dict[str, Any]) -> str:
        """Infer cost level from price data."""
        # Try to get minimum price
        price = None
        if event.get("minimum_price"):
            price = event["minimum_price"]
        elif event.get("cost"):
            cost_str = str(event["cost"])
            # Extract first number
            match = re.search(r"[\d.]+", cost_str)
            if match:
                try:
                    price = float(match.group())
                except ValueError:
                    pass

        if event.get("is_free") or (price is not None and price == 0):
            return "free"
        elif price is None:
            return "medium"  # Default when unknown
        elif price <= 15:
            return "low"
        elif price <= 50:
            return "medium"
        else:
            return "high"

    def _infer_time_scale(self, event: Dict[str, Any]) -> str:
        """Infer time scale from duration or event type."""
        duration = event.get("duration_minutes")

        if duration:
            if duration <= 120:
                return "short"
            elif duration <= 480:
                return "long"
            else:
                return "recurring"

        # Infer from title
        title = (event.get("title") or "").lower()
        if "festival" in title:
            return "long"
        if "workshop" in title:
            return "short"

        return "long"  # Default for events

    def enrich_taxonomy_dimension(
        self,
        dimension: "TaxonomyDimension",
        event_context: Dict[str, Any],
    ) -> "TaxonomyDimension":
        """
        Enrich a TaxonomyDimension with activity-level fields.

        Given primary_category and subcategory, populate activity-level fields
        using LLM-based selection from template options or rule-based fallbacks.

        Args:
            dimension: TaxonomyDimension with at least primary_category and subcategory
            event_context: Event dict with title, description, venue, price, duration, etc.

        Returns:
            New TaxonomyDimension with activity-level fields populated

        Process:
        1. Get activities for subcategory from taxonomy
        2. Match best activity using LLM (or keyword matching)
        3. Use LLM to SELECT appropriate option from templates based on context
        4. Fallback to rule-based defaults if LLM unavailable
        """
        from src.ingestion.normalization.taxonomy import (
            get_activities_for_subcategory,
            get_subcategory_by_id,
            find_best_activity_match,
        )
        from src.ingestion.normalization.event_schema import TaxonomyDimension

        # Start with existing dimension data
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
            sub = get_subcategory_by_id(dimension.subcategory)
            if sub:
                enriched_data["subcategory_name"] = sub.get("name")
                if not enriched_data["values"]:
                    enriched_data["values"] = sub.get("values", [])

        # Try to find matching activity if not already set
        if dimension.subcategory and not dimension.activity_id:
            event_text = f"{event_context.get('title', '')} {event_context.get('description', '')}"

            # Try LLM-based matching first
            client = self._get_client()
            if client:
                activity_match = self.match_activity(
                    event_context.get("title", ""),
                    event_context.get("description", ""),
                    dimension.subcategory,
                )
            else:
                # Fallback to keyword matching
                activity_match = find_best_activity_match(event_text, dimension.subcategory)

            if activity_match:
                enriched_data["activity_id"] = activity_match.get("activity_id")
                enriched_data["activity_name"] = activity_match.get("name")

        # Define attribute options (from taxonomy templates)
        attribute_options = {
            "energy_level": ["low", "medium", "high"],
            "social_intensity": ["solo", "small_group", "large_group"],
            "cognitive_load": ["low", "medium", "high"],
            "physical_involvement": ["none", "light", "moderate"],
            "environment": ["indoor", "outdoor", "digital", "mixed"],
            "risk_level": ["none", "very_low", "low", "medium"],
            "age_accessibility": ["all", "teens+", "adults"],
            "repeatability": ["high", "medium", "low"],
        }

        # Select attribute values using LLM or fallback
        selected_attributes = self._select_attribute_values(
            event_context, attribute_options
        )

        # Merge selected attributes into enriched data
        for attr, value in selected_attributes.items():
            enriched_data[attr] = value

        # Always use rule-based for cost_level and time_scale
        enriched_data["cost_level"] = self._infer_cost_level(event_context)
        enriched_data["time_scale"] = self._infer_time_scale(event_context)

        # Create and return new TaxonomyDimension
        return TaxonomyDimension(**enriched_data)

    def _select_attribute_values(
        self,
        event_context: Dict[str, Any],
        attribute_options: Dict[str, List[str]],
    ) -> Dict[str, str]:
        """
        Select best option for each attribute based on event context.

        Uses LLM if available, otherwise uses rule-based defaults.

        Args:
            event_context: Event dict with title, description, etc.
            attribute_options: Dict mapping attribute name to list of valid options

        Returns:
            Dict with selected value for each attribute
        """
        client = self._get_client()

        if client:
            return self._select_attribute_values_llm(event_context, attribute_options)
        else:
            return self._select_attribute_values_fallback(event_context, attribute_options)

    def _select_attribute_values_llm(
        self,
        event_context: Dict[str, Any],
        attribute_options: Dict[str, List[str]],
    ) -> Dict[str, str]:
        """
        Use LLM to select best option for each attribute based on event context.

        Args:
            event_context: Event dict with title, description, venue, price, etc.
            attribute_options: Dict mapping attribute name to list of valid options
                e.g., {"energy_level": ["low", "medium", "high"]}

        Returns:
            Dict with selected value for each attribute
        """
        context_str = self._build_event_context(event_context)

        # Build options description
        options_str = "\n".join(
            f"- {attr}: {' | '.join(options)}"
            for attr, options in attribute_options.items()
        )

        prompt = f"""Analyze this event and select the most appropriate option for each attribute:

{context_str}

For each attribute below, select ONE option that best fits the event:
{options_str}

Respond with JSON containing your selections:
{{"energy_level": "selected_option", "social_intensity": "selected_option", ...}}

Guidelines:
- energy_level: Consider the activity type, music style (if applicable), time of day
- social_intensity: Consider venue size, event type, whether it's a group activity
- cognitive_load: Consider if it requires active thinking/learning vs passive enjoyment
- physical_involvement: Consider dancing, standing, walking, etc.
- environment: Consider indoor venues vs outdoor festivals vs online events
- risk_level: Consider physical activity level, venue type, activities involved
- age_accessibility: Consider alcohol presence, venue type, content nature
- repeatability: Consider if this is a unique experience vs something people do regularly"""

        try:
            response = self._call_llm(prompt)
            result = json.loads(response.strip())

            # Validate selections are from allowed options
            validated = {}
            for attr, options in attribute_options.items():
                selected = result.get(attr)
                if selected in options:
                    validated[attr] = selected
                else:
                    # Use middle option as default
                    validated[attr] = options[len(options) // 2]

            return validated

        except Exception as e:
            logger.error(f"LLM attribute selection failed: {e}")
            return self._select_attribute_values_fallback(event_context, attribute_options)

    def _select_attribute_values_fallback(
        self,
        event_context: Dict[str, Any],
        attribute_options: Dict[str, List[str]],
    ) -> Dict[str, str]:
        """
        Rule-based fallback for attribute selection when LLM is unavailable.

        Args:
            event_context: Event dict with title, description, etc.
            attribute_options: Dict mapping attribute name to list of valid options

        Returns:
            Dict with selected value for each attribute
        """
        title = (event_context.get("title") or "").lower()
        result = {}

        # Energy level based on keywords
        if any(w in title for w in ["festival", "party", "rave", "club"]):
            result["energy_level"] = "high"
        elif any(w in title for w in ["workshop", "talk", "exhibition"]):
            result["energy_level"] = "medium"
        elif any(w in title for w in ["meditation", "yoga", "chill"]):
            result["energy_level"] = "low"
        else:
            result["energy_level"] = "medium"

        # Social intensity based on event type
        if any(w in title for w in ["festival", "party", "concert"]):
            result["social_intensity"] = "large_group"
        elif any(w in title for w in ["workshop", "class", "meetup"]):
            result["social_intensity"] = "small_group"
        else:
            result["social_intensity"] = "large_group"  # Default for events

        # Cognitive load
        if any(w in title for w in ["workshop", "class", "lecture", "learn"]):
            result["cognitive_load"] = "medium"
        else:
            result["cognitive_load"] = "low"

        # Physical involvement
        if any(w in title for w in ["dance", "yoga", "sports", "run"]):
            result["physical_involvement"] = "moderate"
        elif any(w in title for w in ["concert", "festival", "party"]):
            result["physical_involvement"] = "light"
        else:
            result["physical_involvement"] = "none"

        # Environment
        if any(w in title for w in ["outdoor", "garden", "park", "beach"]):
            result["environment"] = "outdoor"
        elif any(w in title for w in ["online", "virtual", "stream"]):
            result["environment"] = "digital"
        else:
            result["environment"] = "indoor"

        # Risk level
        result["risk_level"] = "very_low"  # Most events are low risk

        # Age accessibility
        if any(w in title for w in ["club", "bar", "nightlife"]):
            result["age_accessibility"] = "adults"
        else:
            result["age_accessibility"] = "all"

        # Repeatability
        if any(w in title for w in ["festival", "carnival", "annual"]):
            result["repeatability"] = "low"  # Unique experiences
        else:
            result["repeatability"] = "medium"

        return result


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
          model_name: "gpt-3.5-turbo"
          fill_missing: ["event_type", "tags", "activity_id"]
    """
    return FeatureExtractor(
        model_name=config.get("model_name", "gpt-3.5-turbo"),
        provider=config.get("provider", "openai"),
        temperature=config.get("temperature", 0.3),
        max_tokens=config.get("max_tokens", 1000),
    )
