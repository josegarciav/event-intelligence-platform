"""
Generic API Pipeline for config-driven event ingestion.

This module provides a single BaseAPIPipeline class that handles ALL API sources
(ra.co, fever, meetup, etc.) via YAML configuration. No subclassing needed.

The pipeline uses:
- FieldMapper for extracting fields from raw API responses
- TaxonomyMapper for rule-based taxonomy assignment
- FeatureExtractor for LLM-based field filling
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
import logging


from src.ingestion.base_pipeline import BasePipeline, PipelineConfig
from src.ingestion.adapters import SourceType, FetchResult
from src.ingestion.adapters.api_adapter import APIAdapter, APIAdapterConfig
from src.ingestion.normalization.event_schema import (
    EventSchema,
    EventType,
    EventFormat,
    LocationInfo,
    PriceInfo,
    OrganizerInfo,
    SourceInfo,
    TaxonomyDimension,
    PrimaryCategory,
)
from src.ingestion.normalization.currency import CurrencyParser
from src.ingestion.normalization.field_mapper import (
    FieldMapper,
)
from src.ingestion.normalization.taxonomy_mapper import (
    TaxonomyMapper,
)
from src.ingestion.normalization.feature_extractor import (
    FeatureExtractor,
    create_feature_extractor_from_config,
)

logger = logging.getLogger(__name__)


@dataclass
class APISourceConfig:
    """
    Complete configuration for any API source.

    This config captures everything needed to:
    - Connect to the API
    - Build queries
    - Parse responses
    - Map fields
    - Assign taxonomy
    - Validate events
    """

    # Source identification
    source_name: str
    enabled: bool = True

    # Connection settings
    endpoint: str = ""
    protocol: str = "graphql"  # "graphql" | "rest"
    timeout_seconds: int = 30
    max_retries: int = 3
    rate_limit_per_second: float = 1.0

    # Query configuration
    query_template: Optional[str] = None
    query_variables: Dict[str, Any] = field(default_factory=dict)
    query_params: Dict[str, Any] = field(default_factory=dict)
    response_path: str = "data"
    total_results_path: Optional[str] = None

    # Pagination
    pagination_type: str = "page_number"  # "page_number" | "cursor" | "offset"
    max_pages: int = 10
    default_page_size: int = 50

    # Field mapping
    field_mappings: Dict[str, str] = field(default_factory=dict)
    transformations: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # Taxonomy configuration
    taxonomy_config: Dict[str, Any] = field(default_factory=dict)

    # Event type rules
    event_type_rules: List[Dict[str, Any]] = field(default_factory=list)

    # Defaults
    defaults: Dict[str, Any] = field(default_factory=dict)

    # Validation
    validation: Dict[str, Any] = field(default_factory=dict)

    # Feature extraction
    feature_extraction: Dict[str, Any] = field(default_factory=dict)


class ConfigDrivenAPIAdapter(APIAdapter):
    """
    API Adapter that uses configuration for query building and response parsing.

    Handles both GraphQL and REST APIs with configurable:
    - Query templates with variable substitution
    - Response path extraction
    - Pagination strategies
    """

    def __init__(
        self,
        api_config: APIAdapterConfig,
        source_config: APISourceConfig,
    ):
        """
        Initialize the config-driven adapter.

        Args:
            api_config: Base API adapter configuration
            source_config: Full source configuration
        """
        self.source_config = source_config
        super().__init__(
            api_config,
            query_builder=self._build_query,
            response_parser=self._parse_response,
        )

    def _build_query(self, **kwargs) -> Dict[str, Any]:
        """
        Build query from config template.

        Supports variable substitution like {{variable_name}} in the template.
        """
        # Merge defaults with provided kwargs
        params = {**self.source_config.defaults, **kwargs}

        # Set date defaults if not provided
        if "date_from" not in params:
            params["date_from"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if "date_to" not in params:
            days_ahead = params.get("days_ahead", 30)
            params["date_to"] = (
                datetime.now(timezone.utc) + timedelta(days=days_ahead)
            ).strftime("%Y-%m-%d")

        if self.source_config.protocol == "graphql":
            # Build GraphQL query
            query_template = self.source_config.query_template or ""

            # Build variables with substitution
            variables = self._substitute_variables(
                self.source_config.query_variables,
                params,
            )

            return {
                "query": query_template,
                "variables": variables,
            }
        else:
            # Build REST query params
            return self._substitute_variables(
                self.source_config.query_params,
                params,
            )

    def _substitute_variables(
        self,
        template: Any,
        params: Dict[str, Any],
    ) -> Any:
        """
        Recursively substitute {{variable}} placeholders in template.

        Args:
            template: Template structure (dict, list, or string)
            params: Parameter values for substitution

        Returns:
            Template with substituted values
        """
        if isinstance(template, str):
            # Find and replace {{variable}} patterns
            result = template
            for key, value in params.items():
                placeholder = f"{{{{{key}}}}}"
                if placeholder in result:
                    result = result.replace(placeholder, str(value))
            return result

        elif isinstance(template, dict):
            return {
                k: self._substitute_variables(v, params) for k, v in template.items()
            }

        elif isinstance(template, list):
            return [self._substitute_variables(item, params) for item in template]

        return template

    def _parse_response(self, response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parse API response using configured response_path.

        Supports dot notation: "data.eventListings.data"
        """
        if "errors" in response:
            logger.error(f"API errors: {response['errors']}")
            return []

        try:
            # Navigate to data using response_path
            data = response
            path_parts = self.source_config.response_path.split(".")

            for part in path_parts:
                if isinstance(data, dict):
                    data = data.get(part, {})
                else:
                    return []

            if isinstance(data, list):
                return data
            return [data] if data else []

        except Exception as e:
            logger.error(f"Failed to parse response: {e}")
            return []

    def fetch(self, **kwargs) -> FetchResult:
        """
        Fetch data with pagination support.

        Handles page-based, cursor-based, and offset-based pagination.
        """
        all_data = []
        page = kwargs.pop("page", 1)
        max_pages = kwargs.pop("max_pages", self.source_config.max_pages)
        page_size = kwargs.get("page_size", self.source_config.default_page_size)
        errors = []
        total_results = 0

        fetch_started = datetime.now(timezone.utc)

        while page <= max_pages:
            logger.info(f"Fetching page {page}/{max_pages}...")

            # Add pagination params
            page_params = {**kwargs, "page": page, "page_size": page_size}

            # Fetch single page using parent class
            result = super().fetch(**page_params)

            if not result.success or not result.raw_data:
                if result.errors:
                    errors.extend(result.errors)
                break

            all_data.extend(result.raw_data)

            # Get total results from metadata
            if result.metadata.get("total_available"):
                total_results = result.metadata["total_available"]

            # Check if we've fetched all available events
            if len(result.raw_data) < page_size:
                logger.info(
                    f"Received {len(result.raw_data)} events (less than page_size), stopping pagination"
                )
                break

            # Check if we've reached total available
            if total_results > 0 and len(all_data) >= total_results:
                logger.info(f"Fetched all {total_results} available events")
                break

            page += 1

        logger.info(
            f"Pagination complete: fetched {len(all_data)} total events across {page} pages"
        )

        return FetchResult(
            success=len(all_data) > 0,
            source_type=SourceType.API,
            raw_data=all_data,
            total_fetched=len(all_data),
            errors=errors,
            metadata={
                "pages_fetched": page,
                "total_available": total_results,
                "max_pages": max_pages,
            },
            fetch_started_at=fetch_started,
            fetch_ended_at=datetime.now(timezone.utc),
        )


class BaseAPIPipeline(BasePipeline):
    """
    Generic API pipeline for ALL sources.

    No subclassing needed - everything is config-driven.
    Uses FieldMapper, TaxonomyMapper, and FeatureExtractor internally.

    This single class replaces source-specific pipelines like RaCoPipeline.
    """

    def __init__(
        self,
        pipeline_config: PipelineConfig,
        source_config: APISourceConfig,
    ):
        """
        Initialize the generic API pipeline.

        Args:
            pipeline_config: Pipeline-level configuration
            source_config: Source-specific configuration from YAML
        """
        self.source_config = source_config

        # Create mapper instances
        self.field_mapper = FieldMapper(
            field_mappings=source_config.field_mappings,
            transformations=source_config.transformations,
        )
        self.taxonomy_mapper = TaxonomyMapper(source_config.taxonomy_config)

        # Create feature extractor if enabled
        self.feature_extractor: Optional[FeatureExtractor] = None
        if source_config.feature_extraction.get("enabled"):
            self.feature_extractor = create_feature_extractor_from_config(
                source_config.feature_extraction
            )

        # Create adapter with config-driven query builder
        adapter = self._create_adapter()
        super().__init__(pipeline_config, adapter)

    def _create_adapter(self) -> ConfigDrivenAPIAdapter:
        """Create the API adapter from configuration."""
        api_config = APIAdapterConfig(
            source_id=self.source_config.source_name,
            source_type=SourceType.API,
            request_timeout=self.source_config.timeout_seconds,
            max_retries=self.source_config.max_retries,
            rate_limit_per_second=self.source_config.rate_limit_per_second,
            graphql_endpoint=(
                self.source_config.endpoint
                if self.source_config.protocol == "graphql"
                else None
            ),
            base_url=(
                self.source_config.endpoint
                if self.source_config.protocol == "rest"
                else ""
            ),
        )

        return ConfigDrivenAPIAdapter(api_config, self.source_config)

    def parse_raw_event(self, raw_event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse raw API event using FieldMapper.

        Args:
            raw_event: Raw event from API response

        Returns:
            Parsed event with standardized field names
        """
        return self.field_mapper.map_event(raw_event)

    def map_to_taxonomy(
        self,
        parsed_event: Dict[str, Any],
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Map event to taxonomy using TaxonomyMapper.

        Args:
            parsed_event: Parsed event dict

        Returns:
            Tuple of (primary_category, taxonomy_dimensions as dicts)
        """
        primary_cat, dimensions = self.taxonomy_mapper.map_event(parsed_event)

        # Convert TaxonomyDimension objects to dicts for normalize_to_schema
        dims_as_dicts = [
            {
                "primary_category": (
                    dim.primary_category.value
                    if hasattr(dim.primary_category, "value")
                    else dim.primary_category
                ),
                "subcategory": dim.subcategory,
                "values": dim.values,
                "confidence": dim.confidence,
            }
            for dim in dimensions
        ]

        return primary_cat, dims_as_dicts

    def normalize_to_schema(
        self,
        parsed_event: Dict[str, Any],
        primary_cat: str,
        taxonomy_dims: List[Dict[str, Any]],
    ) -> EventSchema:
        """
        Normalize parsed event to EventSchema.

        Uses configuration for defaults and FeatureExtractor for missing fields.
        """
        source_event_id = str(parsed_event.get("source_event_id", ""))
        event_id = f"{self.source_config.source_name}_{source_event_id}"

        # Parse dates
        start_dt = self._parse_datetime(
            parsed_event.get("start_time") or parsed_event.get("date")
        )
        end_dt = self._parse_datetime(parsed_event.get("end_time"))

        # Get location defaults
        loc_defaults = self.source_config.defaults.get("location", {})

        # Build location
        location = LocationInfo(
            venue_name=parsed_event.get("venue_name"),
            street_address=parsed_event.get("venue_address"),
            city=parsed_event.get("city") or loc_defaults.get("city", "Unknown"),
            country_code=(
                parsed_event.get("country_code")
                or loc_defaults.get("country_code", "US")
            ).upper(),
            timezone=loc_defaults.get("timezone"),
        )

        # Parse price
        price_str = parsed_event.get("cost") or ""
        min_price, max_price, currency = CurrencyParser.parse_price_string(
            str(price_str)
        )

        is_free = (min_price is None and max_price is None) or str(
            price_str
        ).lower() in ["free", "0", "gratis"]

        price = PriceInfo(
            currency=currency or "EUR",
            is_free=is_free,
            minimum_price=min_price,
            maximum_price=max_price,
            price_raw_text=str(price_str) if price_str else None,
        )

        # Build organizer
        organizer = OrganizerInfo(
            name=parsed_event.get("organizer_name")
            or parsed_event.get("venue_name")
            or "Unknown",
        )

        # Build source info
        source_url = parsed_event.get("source_url") or ""
        source = SourceInfo(
            source_name=self.source_config.source_name,
            source_event_id=source_event_id,
            source_url=source_url,
            last_updated_from_source=datetime.now(timezone.utc),
        )

        # Build taxonomy dimensions
        taxonomy_objs = [
            TaxonomyDimension(
                primary_category=PrimaryCategory(dim["primary_category"]),
                subcategory=dim.get("subcategory"),
                subcategory_name=dim.get("subcategory_name"),
                values=dim.get("values", []),
                confidence=dim.get("confidence", 0.5),
            )
            for dim in taxonomy_dims
        ]

        # Enrich taxonomy dimensions with activity-level fields using FeatureExtractor
        if self.feature_extractor:
            enriched_dims = []
            for dim in taxonomy_objs:
                try:
                    enriched = self.feature_extractor.enrich_taxonomy_dimension(
                        dim, parsed_event
                    )
                    enriched_dims.append(enriched)
                except Exception as e:
                    logger.warning(f"Failed to enrich taxonomy dimension: {e}")
                    enriched_dims.append(dim)
            taxonomy_objs = enriched_dims

        # Determine event type from rules
        event_type = self._determine_event_type(parsed_event)

        # Use feature extractor for missing fields
        if self.feature_extractor:
            missing_fields = self.source_config.feature_extraction.get(
                "fill_missing", []
            )
            if missing_fields:
                extracted = self.feature_extractor.extract_missing_fields(
                    parsed_event, missing_fields
                )
                if "event_type" in extracted and not event_type:
                    event_type = EventType(extracted["event_type"])

        return EventSchema(
            event_id=event_id,
            title=parsed_event.get("title", "Untitled Event"),
            description=parsed_event.get("description"),
            primary_category=primary_cat,
            taxonomy_dimensions=taxonomy_objs,
            start_datetime=start_dt,
            end_datetime=end_dt,
            location=location,
            event_type=event_type or EventType.OTHER,
            format=EventFormat.IN_PERSON,
            price=price,
            organizer=organizer,
            image_url=parsed_event.get("image_url"),
            source=source,
            tags=parsed_event.get("tags", []),
            custom_fields={
                "artists": parsed_event.get("artists", []),
            },
        )

    def _determine_event_type(
        self, parsed_event: Dict[str, Any]
    ) -> Optional[EventType]:
        """Determine event type from configured rules."""
        title = (parsed_event.get("title") or "").lower()

        for rule in self.source_config.event_type_rules:
            match_config = rule.get("match", {})
            event_type_str = rule.get("type")

            # Check title_contains
            keywords = match_config.get("title_contains", [])
            if keywords and any(kw.lower() in title for kw in keywords):
                try:
                    return EventType(event_type_str)
                except ValueError:
                    continue

            # Check default
            if rule.get("default"):
                try:
                    return EventType(event_type_str)
                except ValueError:
                    pass

        return None

    def _parse_datetime(self, dt_value: Any) -> datetime:
        """Parse datetime from various formats."""
        if not dt_value:
            return datetime.now(timezone.utc)

        if isinstance(dt_value, datetime):
            return dt_value

        if isinstance(dt_value, str):
            # Handle ISO format with T separator
            try:
                if "T" in dt_value:
                    # Remove milliseconds and timezone
                    clean = dt_value.split(".")[0]
                    if clean.endswith("Z"):
                        clean = clean[:-1]
                    return datetime.fromisoformat(clean).replace(tzinfo=timezone.utc)
                return datetime.fromisoformat(dt_value).replace(tzinfo=timezone.utc)
            except ValueError:
                pass

            # Try common formats
            for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"]:
                try:
                    return datetime.strptime(dt_value, fmt).replace(tzinfo=timezone.utc)
                except ValueError:
                    continue

        logger.warning(f"Could not parse datetime: {dt_value}")
        return datetime.now(timezone.utc)

    def validate_event(self, event: EventSchema) -> Tuple[bool, List[str]]:
        """Validate event using configured rules."""
        errors = []
        validation_config = self.source_config.validation

        # Required fields
        required_fields = validation_config.get(
            "required_fields", ["title", "source_event_id"]
        )
        for field_name in required_fields:
            if field_name == "title" and (
                not event.title or event.title == "Untitled Event"
            ):
                errors.append("Title is required")
            elif field_name == "source_event_id" and not event.source.source_event_id:
                errors.append("Source event ID is required")

        # Future events only
        if validation_config.get("future_events_only", True):
            if event.start_datetime < datetime.now(timezone.utc):
                errors.append("Warning: Event start time is in the past")

        # Location validation
        if not event.location.city:
            errors.append("City is required")

        # Price validation
        if event.price.minimum_price and event.price.minimum_price < 0:
            errors.append("Minimum price cannot be negative")

        is_valid = not any("Error:" in e for e in errors)
        return is_valid, errors

    def enrich_event(self, event: EventSchema) -> EventSchema:
        """Enrich event with additional computed data."""
        # Calculate duration
        if event.end_datetime and event.start_datetime:
            duration = (event.end_datetime - event.start_datetime).total_seconds() / 60
            event.duration_minutes = int(duration)

        # Set timezone based on city if not set
        if not event.location.timezone:
            city_timezones = {
                "barcelona": "Europe/Madrid",
                "madrid": "Europe/Madrid",
                "london": "Europe/London",
                "berlin": "Europe/Berlin",
                "amsterdam": "Europe/Amsterdam",
                "paris": "Europe/Paris",
                "new york": "America/New_York",
                "los angeles": "America/Los_Angeles",
            }
            city_lower = (event.location.city or "").lower()
            if city_lower in city_timezones:
                event.location.timezone = city_timezones[city_lower]

        # Use default timezone from config if still not set
        if not event.location.timezone:
            loc_defaults = self.source_config.defaults.get("location", {})
            event.location.timezone = loc_defaults.get("timezone")

        return event


def create_api_pipeline_from_config(
    source_name: str,
    source_config_dict: Dict[str, Any],
    pipeline_config: Optional[PipelineConfig] = None,
) -> BaseAPIPipeline:
    """
    Factory function to create a BaseAPIPipeline from YAML config dict.

    Args:
        source_name: Name of the source (e.g., "ra_co")
        source_config_dict: Dict from YAML config for this source
        pipeline_config: Optional PipelineConfig (created from source_config if not provided)

    Returns:
        Configured BaseAPIPipeline instance
    """
    # Build APISourceConfig from dict
    connection = source_config_dict.get("connection", {})
    query_config = source_config_dict.get("query", {})
    pagination = source_config_dict.get("pagination", {})

    source_config = APISourceConfig(
        source_name=source_name,
        enabled=source_config_dict.get("enabled", True),
        endpoint=connection.get("endpoint")
        or source_config_dict.get("graphql_endpoint", ""),
        protocol=connection.get("protocol", "graphql"),
        timeout_seconds=connection.get(
            "timeout_seconds", source_config_dict.get("request_timeout", 30)
        ),
        max_retries=source_config_dict.get("max_retries", 3),
        rate_limit_per_second=source_config_dict.get("rate_limit_per_second", 1.0),
        query_template=query_config.get("template"),
        query_variables=query_config.get("variables", {}),
        query_params=query_config.get("params", {}),
        response_path=query_config.get("response_path", "data"),
        total_results_path=query_config.get("total_results_path"),
        pagination_type=pagination.get("type", "page_number"),
        max_pages=pagination.get("max_pages", 10),
        default_page_size=pagination.get(
            "default_page_size", source_config_dict.get("batch_size", 50)
        ),
        field_mappings=source_config_dict.get("field_mappings", {}),
        transformations=source_config_dict.get("transformations", {}),
        taxonomy_config=source_config_dict.get("taxonomy", {}),
        event_type_rules=source_config_dict.get("event_type_rules", []),
        defaults=source_config_dict.get("defaults", {}),
        validation=source_config_dict.get("validation", {}),
        feature_extraction=source_config_dict.get("feature_extraction", {}),
    )

    # Create pipeline config if not provided
    if pipeline_config is None:
        pipeline_config = PipelineConfig(
            source_name=source_name,
            source_type=SourceType.API,
            request_timeout=source_config.timeout_seconds,
            max_retries=source_config.max_retries,
            batch_size=source_config.default_page_size,
            rate_limit_per_second=source_config.rate_limit_per_second,
        )

    return BaseAPIPipeline(pipeline_config, source_config)
