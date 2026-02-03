"""
Taxonomy Retriever for RAG-based feature extraction.

Loads the Human Experience Taxonomy and provides filtered context
for LLM-based feature extraction.
"""

import json
import logging
from functools import lru_cache
from typing import Any, Dict, List, Optional

from src.configs.config import Config

logger = logging.getLogger(__name__)

TAXONOMY_PATH = Config.get_taxonomy_path()


@lru_cache(maxsize=1)
def _load_taxonomy() -> Dict[str, Any]:
    """Load and cache the full taxonomy."""
    with open(TAXONOMY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


class TaxonomyRetriever:
    """
    Retrieves and filters taxonomy context for LLM prompts.

    Provides methods to:
    - Get full taxonomy
    - Filter by category ID
    - Filter by subcategory ID
    - Get activity options for a subcategory
    - Format taxonomy as context string for prompts
    """

    def __init__(self):
        """Initialize the taxonomy retriever."""
        self._taxonomy = _load_taxonomy()
        self._category_index = self._build_category_index()
        self._subcategory_index = self._build_subcategory_index()

    def _build_category_index(self) -> Dict[str, Dict[str, Any]]:
        """Build index mapping category_id -> category data."""
        index = {}
        for cat in self._taxonomy.get("categories", []):
            cat_id = cat.get("category_id")
            if cat_id:
                index[cat_id] = cat
        return index

    def _build_subcategory_index(self) -> Dict[str, Dict[str, Any]]:
        """Build index mapping subcategory_id -> subcategory data with parent info."""
        index = {}
        for cat in self._taxonomy.get("categories", []):
            cat_id = cat.get("category_id")
            cat_name = cat.get("category")
            for sub in cat.get("subcategories", []):
                sub_id = sub.get("id")
                if sub_id:
                    index[sub_id] = {
                        **sub,
                        "_category_id": cat_id,
                        "_category_name": cat_name,
                    }
        return index

    def get_full_taxonomy(self) -> Dict[str, Any]:
        """Get the full taxonomy."""
        return self._taxonomy

    def get_category_by_id(self, category_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a category by its ID.

        Args:
            category_id: Category ID (e.g., "1", "2", etc.)

        Returns:
            Category dict or None if not found
        """
        return self._category_index.get(category_id)

    def get_subcategory_by_id(self, subcategory_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a subcategory by its ID.

        Args:
            subcategory_id: Subcategory ID (e.g., "1.4", "2.1", etc.)

        Returns:
            Subcategory dict with parent category info, or None if not found
        """
        return self._subcategory_index.get(subcategory_id)

    def get_activities_for_subcategory(
        self, subcategory_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get all activities for a subcategory.

        Args:
            subcategory_id: Subcategory ID (e.g., "1.4")

        Returns:
            List of activity dicts
        """
        sub = self.get_subcategory_by_id(subcategory_id)
        if sub:
            return sub.get("activities", [])
        return []

    def get_category_context_for_prompt(self, category_id: str) -> str:
        """
        Get formatted taxonomy context for a specific category.

        This is injected into LLM prompts to provide context about
        available subcategories and activities.

        Args:
            category_id: Category ID (e.g., "1")

        Returns:
            Formatted string with category context
        """
        cat = self.get_category_by_id(category_id)
        if not cat:
            return f"Category {category_id} not found."

        lines = [
            f"# Category: {cat.get('category')} (ID: {category_id})",
            f"Description: {cat.get('description', 'N/A')}",
            "",
            "## Subcategories:",
        ]

        for sub in cat.get("subcategories", []):
            sub_id = sub.get("id")
            sub_name = sub.get("name")
            sub_values = sub.get("values", [])

            lines.append(f"\n### {sub_id}: {sub_name}")
            lines.append(f"Values: {', '.join(sub_values)}")

            activities = sub.get("activities", [])
            if activities:
                lines.append(f"Activities ({len(activities)} total):")
                for act in activities[:5]:  # Limit to 5 examples
                    lines.append(f"  - {act.get('name')}")
                if len(activities) > 5:
                    lines.append(f"  ... and {len(activities) - 5} more")

        return "\n".join(lines)

    def get_subcategory_context_for_prompt(self, subcategory_id: str) -> str:
        """
        Get formatted taxonomy context for a specific subcategory.

        Includes full activity details for attribute selection.

        Args:
            subcategory_id: Subcategory ID (e.g., "1.4")

        Returns:
            Formatted string with subcategory context
        """
        sub = self.get_subcategory_by_id(subcategory_id)
        if not sub:
            return f"Subcategory {subcategory_id} not found."

        lines = [
            f"# Subcategory: {sub.get('name')} (ID: {subcategory_id})",
            f"Category: {sub.get('_category_name')} (ID: {sub.get('_category_id')})",
            f"Values: {', '.join(sub.get('values', []))}",
            "",
            "## Available Activities:",
        ]

        for act in sub.get("activities", []):
            lines.append(f"\n### {act.get('name')}")
            lines.append(f"Activity ID: {act.get('activity_id')}")

            # Show attribute options (these are templates like "low | medium | high")
            lines.append("Attribute Options:")
            for attr in [
                "energy_level",
                "social_intensity",
                "cognitive_load",
                "physical_involvement",
                "cost_level",
                "time_scale",
                "environment",
                "risk_level",
                "age_accessibility",
                "repeatability",
            ]:
                val = act.get(attr)
                if val:
                    lines.append(f"  - {attr}: {val}")

            emotional = act.get("emotional_output", [])
            if emotional:
                lines.append(f"  - emotional_output: {', '.join(emotional)}")

        return "\n".join(lines)

    def get_attribute_options(self) -> Dict[str, List[str]]:
        """
        Get all possible options for each taxonomy attribute.

        Returns:
            Dict mapping attribute name to list of valid options
        """
        return {
            "energy_level": ["low", "medium", "high"],
            "social_intensity": ["solo", "small_group", "large_group"],
            "cognitive_load": ["low", "medium", "high"],
            "physical_involvement": ["none", "light", "moderate"],
            "cost_level": ["free", "low", "medium", "high"],
            "time_scale": ["short", "long", "recurring"],
            "environment": ["indoor", "outdoor", "digital", "mixed"],
            "risk_level": ["none", "very_low", "low", "medium"],
            "age_accessibility": ["all", "teens+", "adults"],
            "repeatability": ["high", "medium", "low"],
        }

    def get_attribute_options_string(self) -> str:
        """
        Get attribute options formatted for prompts.

        Returns:
            Formatted string with all attribute options
        """
        options = self.get_attribute_options()
        lines = ["## Attribute Options (select ONE for each):"]
        for attr, vals in options.items():
            lines.append(f"- {attr}: {' | '.join(vals)}")
        return "\n".join(lines)

    def find_best_matching_activity(
        self,
        subcategory_id: str,
        event_title: str,
        event_description: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Find the best matching activity for an event using keyword matching.

        This is a simple heuristic fallback when LLM is unavailable.

        Args:
            subcategory_id: Subcategory to search within
            event_title: Event title
            event_description: Event description (optional)

        Returns:
            Best matching activity dict or None
        """
        activities = self.get_activities_for_subcategory(subcategory_id)
        if not activities:
            return None

        search_text = f"{event_title} {event_description or ''}".lower()
        search_words = set(search_text.split())

        best_match = None
        best_score = 0.0

        for activity in activities:
            activity_name = activity.get("name", "").lower()
            activity_words = set(activity_name.split())

            # Calculate overlap score
            if activity_words:
                if activity_name in search_text:
                    score = 1.0
                else:
                    overlap = len(search_words & activity_words)
                    score = overlap / len(activity_words)

                if score > best_score:
                    best_score = score
                    best_match = activity

        return best_match if best_score > 0.2 else None


# Singleton instance
_retriever: Optional[TaxonomyRetriever] = None


def get_taxonomy_retriever() -> TaxonomyRetriever:
    """Get the singleton TaxonomyRetriever instance."""
    global _retriever
    if _retriever is None:
        _retriever = TaxonomyRetriever()
    return _retriever
