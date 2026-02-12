"""
Field Mapper for generic field extraction from raw event data.

Maps raw source data to intermediate format using configuration.
Supports:
- Dot notation for nested fields: "event.venue.name"
- Array extraction: "artists[*].name" -> list
- Array indexing: "images[0].filename"
- Transformations: template, uppercase, lowercase, regex
"""

import logging
import re
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class FieldMapper:
    """
    Maps raw source data to intermediate format using config.

    Supports flexible field extraction with:
    - Dot notation for nested access
    - Array wildcards for list extraction
    - Array indexing for specific elements
    - Post-extraction transformations
    """

    def __init__(
        self,
        field_mappings: Dict[str, str],
        transformations: Optional[Dict[str, Dict[str, Any]]] = None,
    ):
        """
        Initialize the field mapper.

        Args:
            field_mappings: Dict mapping target field names to source paths.
                Example: {"title": "event.title", "artists": "event.artists[*].name"}
            transformations: Dict mapping field names to transformation configs.
                Example: {"image_url": {"type": "template", "template": "https://example.com/{{filename}}"}}
        """
        self.field_mappings = field_mappings
        self.transformations = transformations or {}

    def map_event(self, raw_event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract fields from raw event data using configured mappings.

        Args:
            raw_event: Raw event data dict from source

        Returns:
            Dict with mapped fields
        """
        result = {}

        for target_field, source_path in self.field_mappings.items():
            try:
                value = self._extract_field(raw_event, source_path)
                result[target_field] = value
            except Exception as e:
                logger.debug(
                    f"Failed to extract {target_field} from {source_path}: {e}"
                )
                result[target_field] = None

        # Apply transformations
        result = self.apply_transformations(result)

        return result

    def _extract_field(
        self,
        data: Any,
        path: str,
    ) -> Any:
        """
        Extract a field using dot notation, array wildcards, or array indexing.

        Supports:
        - "field" - simple field access
        - "parent.child" - nested field access
        - "items[0]" - array index access
        - "items[*].name" - array wildcard (returns list)
        - "items[0].name" - array index then nested access

        Args:
            data: Source data (dict or list)
            path: Field path with optional array notation

        Returns:
            Extracted value (single value or list for wildcards)
        """
        if not path:
            return data

        # Handle array wildcard: items[*].name
        wildcard_match = re.match(r"^([^[]+)\[\*\](.*)$", path)
        if wildcard_match:
            field_name = wildcard_match.group(1)
            remaining_path = wildcard_match.group(2)
            if remaining_path.startswith("."):
                remaining_path = remaining_path[1:]

            # Use _extract_field for nested paths (e.g. "event.artists")
            items = self._extract_field(data, field_name)
            if not isinstance(items, list):
                return []

            if remaining_path:
                return [
                    self._extract_field(item, remaining_path)
                    for item in items
                    if item is not None
                ]
            return items

        # Handle array index: items[0].name or items[0]
        index_match = re.match(r"^([^[]+)\[(\d+)\](.*)$", path)
        if index_match:
            field_name = index_match.group(1)
            index = int(index_match.group(2))
            remaining_path = index_match.group(3)
            if remaining_path.startswith("."):
                remaining_path = remaining_path[1:]

            # Use _extract_field for nested paths (e.g. "event.images")
            items = self._extract_field(data, field_name)
            if not isinstance(items, list) or index >= len(items):
                return None

            item = items[index]
            if remaining_path:
                return self._extract_field(item, remaining_path)
            return item

        # Simple dot notation: parent.child
        parts = path.split(".", 1)
        if len(parts) == 1:
            return self._get_value(data, parts[0])

        # Nested access
        parent_value = self._get_value(data, parts[0])
        if parent_value is None:
            return None
        return self._extract_field(parent_value, parts[1])

    def _get_value(self, data: Any, key: str) -> Any:
        """
        Get value from dict or return None.

        Args:
            data: Source data
            key: Key to access

        Returns:
            Value or None
        """
        if isinstance(data, dict):
            return data.get(key)
        return None

    def apply_transformations(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply configured transformations to extracted data.

        Supported transformation types:
        - template: String interpolation with {{field}} placeholders
        - uppercase: Convert to uppercase
        - lowercase: Convert to lowercase
        - regex: Extract using regex pattern
        - default: Set default value if None/empty
        - join: Join list elements with separator
        - split: Split string into list

        Args:
            data: Extracted data dict

        Returns:
            Transformed data dict
        """
        result = dict(data)

        for field_name, transform_config in self.transformations.items():
            try:
                transform_type = transform_config.get("type")

                # Check conditional execution
                when_field = transform_config.get("when")
                if when_field and not result.get(when_field):
                    continue

                if transform_type == "template":
                    result[field_name] = self._apply_template(
                        transform_config.get("template", ""),
                        result,
                    )

                elif transform_type == "uppercase":
                    source = transform_config.get("source", field_name)
                    value = result.get(source)
                    if isinstance(value, str):
                        result[field_name] = value.upper()

                elif transform_type == "lowercase":
                    source = transform_config.get("source", field_name)
                    value = result.get(source)
                    if isinstance(value, str):
                        result[field_name] = value.lower()

                elif transform_type == "regex":
                    source = transform_config.get("source", field_name)
                    pattern = transform_config.get("pattern", "")
                    group = transform_config.get("group", 0)
                    value = result.get(source)
                    if isinstance(value, str):
                        match = re.search(pattern, value)
                        if match:
                            result[field_name] = match.group(group)

                elif transform_type == "default":
                    if result.get(field_name) is None:
                        result[field_name] = transform_config.get("value")

                elif transform_type == "join":
                    source = transform_config.get("source", field_name)
                    separator = transform_config.get("separator", ", ")
                    value = result.get(source)
                    if isinstance(value, list):
                        result[field_name] = separator.join(str(v) for v in value if v)

                elif transform_type == "split":
                    source = transform_config.get("source", field_name)
                    separator = transform_config.get("separator", ",")
                    value = result.get(source)
                    if isinstance(value, str):
                        result[field_name] = [v.strip() for v in value.split(separator)]

                elif transform_type == "coalesce":
                    # Use first non-None value from list of sources
                    sources = transform_config.get("sources", [])
                    for source in sources:
                        if result.get(source) is not None:
                            result[field_name] = result[source]
                            break

                elif transform_type == "concat":
                    # Concatenate multiple fields
                    sources = transform_config.get("sources", [])
                    separator = transform_config.get("separator", " ")
                    values = [str(result.get(s, "")) for s in sources if result.get(s)]
                    result[field_name] = separator.join(values)

                elif transform_type == "strip_html":
                    # Strip HTML tags and normalize whitespace
                    source = transform_config.get("source", field_name)
                    value = result.get(source)
                    if isinstance(value, str):
                        cleaned = re.sub(r"<[^>]+>", " ", value)
                        cleaned = re.sub(r"\s+", " ", cleaned).strip()
                        result[field_name] = cleaned

            except Exception as e:
                logger.warning(
                    f"Failed to apply transformation {transform_type} to {field_name}: {e}"
                )

        return result

    def _apply_template(self, template: str, data: Dict[str, Any]) -> str:
        """
        Apply string template with {{field}} placeholders.

        Args:
            template: Template string with {{field}} placeholders
            data: Data dict for substitution

        Returns:
            Interpolated string
        """
        result = template

        # Find all {{field}} placeholders
        placeholders = re.findall(r"\{\{(\w+)\}\}", template)

        for placeholder in placeholders:
            value = data.get(placeholder, "")
            if value is None:
                value = ""
            result = result.replace(f"{{{{{placeholder}}}}}", str(value))

        return result


def create_field_mapper_from_config(config: Dict[str, Any]) -> FieldMapper:
    """
    Create a FieldMapper from YAML config section.

    Args:
        config: Dict with "field_mappings" and optional "transformations"

    Returns:
        Configured FieldMapper instance

    Example config:
        field_mappings:
          title: "event.title"
          artists: "event.artists[*].name"
          image_filename: "event.images[0].filename"
        transformations:
          image_url:
            type: "template"
            template: "https://example.com/{{image_filename}}"
            when: "image_filename"
    """
    field_mappings = config.get("field_mappings", {})
    transformations = config.get("transformations", {})

    return FieldMapper(
        field_mappings=field_mappings,
        transformations=transformations,
    )
