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
from typing import Any, Dict, List, Optional

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
