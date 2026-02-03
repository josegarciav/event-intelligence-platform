"""
Taxonomy Mapper for rule-based taxonomy assignment.

Maps events to Human Experience Taxonomy dimensions using configuration rules.
Supports:
- Title/description keyword matching
- Field value matching
- Default assignments
- Multiple taxonomy dimensions per event
"""

import re
from typing import Any, Dict, List, Optional, Tuple
import logging

from src.ingestion.normalization.taxonomy import (
    get_full_taxonomy_dimension,
    get_subcategory_by_id,
    find_best_activity_match,
)
from src.ingestion.normalization.event_schema import TaxonomyDimension, PrimaryCategory

logger = logging.getLogger(__name__)


class TaxonomyMapper:
    """
    Maps events to Human Experience Taxonomy dimensions using config rules.

    Rules are evaluated in order, and all matching rules contribute
    taxonomy dimensions. This allows events to have multiple dimensions
    (e.g., a music festival can be both "play_and_fun" and "social_connection").

    Rule types:
    - title_contains: Match if title contains any of the keywords
    - description_contains: Match if description contains any of the keywords
    - field_equals: Match if a field equals a specific value
    - field_in: Match if a field value is in a list
    - regex: Match using regex pattern
    - always: Always matches (for default dimensions)
    """

    def __init__(self, taxonomy_config: Dict[str, Any]):
        """
        Initialize the taxonomy mapper.

        Args:
            taxonomy_config: Dict with:
                - default_primary: Default primary category
                - default_subcategory: Default subcategory ID
                - rules: List of rule dicts with match conditions and assignments
        """
        self.default_primary = taxonomy_config.get("default_primary", "play_and_fun")
        self.default_subcategory = taxonomy_config.get("default_subcategory")
        self.rules = taxonomy_config.get("rules", [])

    def map_event(
        self,
        parsed_event: Dict[str, Any],
    ) -> Tuple[str, List[TaxonomyDimension]]:
        """
        Map event to taxonomy dimensions based on rules.

        Args:
            parsed_event: Parsed event dict with title, description, etc.

        Returns:
            Tuple of (primary_category, list of TaxonomyDimension objects)
        """
        dimensions: List[TaxonomyDimension] = []
        primary_category = self.default_primary

        # Evaluate each rule
        for rule in self.rules:
            match_config = rule.get("match", {})
            assign_config = rule.get("assign", {})

            if self._evaluate_match(parsed_event, match_config):
                dimension = self._create_dimension(parsed_event, assign_config)
                if dimension:
                    dimensions.append(dimension)

                    # First matching rule sets the primary category
                    if not dimensions[:-1]:  # First dimension
                        primary_category = assign_config.get(
                            "primary_category", self.default_primary
                        )

        # If no rules matched, use defaults
        if not dimensions and self.default_subcategory:
            dimensions.append(
                TaxonomyDimension(
                    primary_category=PrimaryCategory(self.default_primary),
                    subcategory=self.default_subcategory,
                    values=[],
                    confidence=0.5,
                )
            )

        return primary_category, dimensions

    def _evaluate_match(
        self,
        event: Dict[str, Any],
        match_config: Dict[str, Any],
    ) -> bool:
        """
        Evaluate if event matches the rule conditions.

        Args:
            event: Parsed event dict
            match_config: Dict with match conditions

        Returns:
            True if all conditions match
        """
        # "always" condition
        if match_config.get("always"):
            return True

        # title_contains: list of keywords
        title_keywords = match_config.get("title_contains", [])
        if title_keywords:
            title = (event.get("title") or "").lower()
            if not any(kw.lower() in title for kw in title_keywords):
                return False

        # description_contains: list of keywords
        desc_keywords = match_config.get("description_contains", [])
        if desc_keywords:
            description = (event.get("description") or "").lower()
            if not any(kw.lower() in description for kw in desc_keywords):
                return False

        # field_equals: {field: value}
        field_equals = match_config.get("field_equals", {})
        for field, expected_value in field_equals.items():
            actual_value = event.get(field)
            if actual_value != expected_value:
                return False

        # field_in: {field: [values]}
        field_in = match_config.get("field_in", {})
        for field, allowed_values in field_in.items():
            actual_value = event.get(field)
            if actual_value not in allowed_values:
                return False

        # regex: {field: pattern}
        regex_matches = match_config.get("regex", {})
        for field, pattern in regex_matches.items():
            value = str(event.get(field) or "")
            if not re.search(pattern, value, re.IGNORECASE):
                return False

        # All conditions passed (or no specific conditions)
        return True

    def _create_dimension(
        self,
        event: Dict[str, Any],
        assign_config: Dict[str, Any],
    ) -> Optional[TaxonomyDimension]:
        """
        Create a TaxonomyDimension from assignment config.

        Args:
            event: Parsed event dict
            assign_config: Dict with assignment values

        Returns:
            TaxonomyDimension or None
        """
        primary_category_str = assign_config.get(
            "primary_category", self.default_primary
        )
        subcategory_id = assign_config.get("subcategory", self.default_subcategory)
        values = assign_config.get("values", [])
        confidence = assign_config.get("confidence", 0.5)

        # Validate primary category
        try:
            primary_category = PrimaryCategory(primary_category_str)
        except ValueError:
            logger.warning(f"Invalid primary category: {primary_category_str}")
            return None

        # If no values provided, get from subcategory
        if not values and subcategory_id:
            sub = get_subcategory_by_id(subcategory_id)
            if sub:
                values = sub.get("values", [])

        return TaxonomyDimension(
            primary_category=primary_category,
            subcategory=subcategory_id,
            values=values,
            confidence=confidence,
        )

    def get_full_taxonomy_data(
        self,
        parsed_event: Dict[str, Any],
        include_activity: bool = True,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Get full taxonomy dimension data including activity-level details.

        This returns raw dicts instead of TaxonomyDimension objects,
        with additional fields like activity_name, energy_level, etc.

        Args:
            parsed_event: Parsed event dict
            include_activity: Whether to attempt activity matching

        Returns:
            Tuple of (primary_category, list of full taxonomy dimension dicts)
        """
        primary_category, dimensions = self.map_event(parsed_event)
        full_dimensions = []

        for dim in dimensions:
            # Start with basic TaxonomyDimension data
            full_dim = get_full_taxonomy_dimension(
                primary_category=(
                    dim.primary_category.value
                    if isinstance(dim.primary_category, PrimaryCategory)
                    else dim.primary_category
                ),
                subcategory_id=dim.subcategory or "",
                confidence=dim.confidence,
                values=dim.values if dim.values else None,
            )

            # Try to find matching activity
            if include_activity and dim.subcategory:
                event_context = f"{parsed_event.get('title', '')} {parsed_event.get('description', '')}"
                activity_match = find_best_activity_match(
                    event_context, dim.subcategory
                )
                if activity_match:
                    full_dim["activity_id"] = activity_match.get("activity_id")
                    full_dim["activity_name"] = activity_match.get("name")
                    full_dim["energy_level"] = activity_match.get("energy_level")
                    full_dim["social_intensity"] = activity_match.get(
                        "social_intensity"
                    )
                    full_dim["cognitive_load"] = activity_match.get("cognitive_load")
                    full_dim["physical_involvement"] = activity_match.get(
                        "physical_involvement"
                    )
                    full_dim["environment"] = activity_match.get("environment")
                    full_dim["emotional_output"] = activity_match.get(
                        "emotional_output", []
                    )
                    full_dim["_activity_match_score"] = activity_match.get(
                        "_match_score"
                    )

            full_dimensions.append(full_dim)

        return primary_category, full_dimensions


def create_taxonomy_mapper_from_config(config: Dict[str, Any]) -> TaxonomyMapper:
    """
    Factory function to create TaxonomyMapper from YAML config section.

    Args:
        config: Dict with taxonomy configuration

    Returns:
        Configured TaxonomyMapper instance

    Example config:
        taxonomy:
          default_primary: "play_and_fun"
          default_subcategory: "1.4"
          rules:
            - match: {title_contains: ["festival", "carnival"]}
              assign:
                primary_category: "exploration_and_adventure"
                subcategory: "2.4"
                confidence: 0.65
            - match: {always: true}
              assign:
                primary_category: "play_and_fun"
                subcategory: "1.4"
                values: ["expression", "energy", "flow"]
                confidence: 0.95
    """
    return TaxonomyMapper(config)
