"""
Schema validator for enrichment outputs.

Validates EventSchema fields against data contract constraints and enum sets.
Prevents hallucinated writes from entering the dataset.
"""

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.schemas.event import EventSchema

logger = logging.getLogger(__name__)

# Valid enum values for key fields
_VALID_ENERGY_LEVELS = {"low", "medium", "high"}
_VALID_SOCIAL_INTENSITIES = {"solo", "small_group", "large_group"}
_VALID_COGNITIVE_LOADS = {"low", "medium", "high"}
_VALID_PHYSICAL_INVOLVEMENTS = {"none", "light", "moderate"}
_VALID_ENVIRONMENTS = {"indoor", "outdoor", "digital", "mixed"}
_VALID_RISK_LEVELS = {"none", "very_low", "low", "medium"}
_VALID_AGE_ACCESSIBILITIES = {"all", "teens+", "adults"}
_VALID_REPEATABILITIES = {"high", "medium", "low"}
_VALID_COST_LEVELS = {"free", "low", "medium", "high"}
_VALID_TIME_SCALES = {"short", "long", "recurring"}


class SchemaValidator:
    """
    Validates enrichment outputs against Pulsecity data contracts.

    Used by the orchestrator after each agent run to catch invalid values
    before they propagate downstream.
    """

    def validate_event(self, event: "EventSchema") -> list[str]:
        """
        Validate an enriched event against data contract constraints.

        Returns:
            List of validation error messages (empty = valid)
        """
        errors: list[str] = []

        if event.taxonomy:
            tax = event.taxonomy
            self._check_enum(
                "taxonomy.energy_level", tax.energy_level, _VALID_ENERGY_LEVELS, errors
            )
            self._check_enum(
                "taxonomy.social_intensity",
                tax.social_intensity,
                _VALID_SOCIAL_INTENSITIES,
                errors,
            )
            self._check_enum(
                "taxonomy.cognitive_load",
                tax.cognitive_load,
                _VALID_COGNITIVE_LOADS,
                errors,
            )
            self._check_enum(
                "taxonomy.physical_involvement",
                tax.physical_involvement,
                _VALID_PHYSICAL_INVOLVEMENTS,
                errors,
            )
            self._check_enum(
                "taxonomy.environment", tax.environment, _VALID_ENVIRONMENTS, errors
            )
            self._check_enum(
                "taxonomy.risk_level", tax.risk_level, _VALID_RISK_LEVELS, errors
            )
            self._check_enum(
                "taxonomy.age_accessibility",
                tax.age_accessibility,
                _VALID_AGE_ACCESSIBILITIES,
                errors,
            )
            self._check_enum(
                "taxonomy.repeatability",
                tax.repeatability,
                _VALID_REPEATABILITIES,
                errors,
            )
            self._check_enum(
                "taxonomy.cost_level", tax.cost_level, _VALID_COST_LEVELS, errors
            )
            self._check_enum(
                "taxonomy.time_scale", tax.time_scale, _VALID_TIME_SCALES, errors
            )

            # Validate emotional_output is a list of non-empty strings
            if tax.emotional_output is not None:
                if not isinstance(tax.emotional_output, list):
                    errors.append("taxonomy.emotional_output must be a list")
                elif any(
                    not isinstance(e, str) or not e.strip()
                    for e in tax.emotional_output
                ):
                    errors.append("taxonomy.emotional_output contains invalid entries")

        if errors:
            logger.debug(
                f"Validation errors for event {event.source_event_id}: {errors}"
            )

        return errors

    def validate_batch(self, events: list["EventSchema"]) -> dict[str, list[str]]:
        """
        Validate a batch of events.

        Returns:
            Dict mapping source_event_id → list of validation errors
        """
        results: dict[str, list[str]] = {}
        for event in events:
            event_errors = self.validate_event(event)
            if event_errors:
                results[str(event.source_event_id)] = event_errors
        return results

    @staticmethod
    def _check_enum(
        field_name: str,
        value: Any,
        valid_values: set[str],
        errors: list[str],
    ) -> None:
        if value is not None and value not in valid_values:
            errors.append(f"{field_name}='{value}' not in {sorted(valid_values)}")
