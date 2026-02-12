"""
Generic API Pipeline for config-driven event ingestion.

This module provides a single BaseAPIPipeline class that handles ALL API sources
(ra.co, fever, meetup, etc.) via YAML configuration. No subclassing needed.

The pipeline uses:
- FieldMapper for extracting fields from raw API responses
- TaxonomyMapper for rule-based taxonomy assignment
- FeatureExtractor for LLM-based field filling
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from src.agents.feature_extractor import (
    FeatureExtractor,
    create_feature_extractor_from_config,
)
from src.ingestion.adapters import FetchResult, SourceType
from src.ingestion.adapters.api_adapter import APIAdapter, APIAdapterConfig
from src.ingestion.base_pipeline import (
    BasePipeline,
    PipelineConfig,
    PipelineExecutionResult,
    PipelineStatus,
)
from src.ingestion.normalization.currency import CurrencyParser
from src.ingestion.normalization.field_mapper import FieldMapper
from src.ingestion.normalization.taxonomy_mapper import TaxonomyMapper
from src.schemas.event import (
    ArtistInfo,
    Coordinates,
    EngagementMetrics,
    EventFormat,
    EventSchema,
    EventType,
    LocationInfo,
    NormalizationCategory,
    NormalizationError,
    OrganizerInfo,
    PriceInfo,
    PrimaryCategory,
    SourceInfo,
    TaxonomyDimension,
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

    # HTML enrichment (compressed_html scraping)
    html_enrichment: Dict[str, Any] = field(default_factory=dict)

    # Detail query configuration (per-event enrichment)
    detail_query: Dict[str, Any] = field(default_factory=dict)


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

        When the entire string is a single placeholder (e.g. "{{area_id}}"),
        the original value type is preserved (int, float, etc.) so that
        GraphQL Int fields receive integers, not strings.

        When the placeholder is embedded in a larger string
        (e.g. "https://example.com/{{id}}"), string conversion is used.

        Args:
            template: Template structure (dict, list, or string)
            params: Parameter values for substitution

        Returns:
            Template with substituted values
        """
        if isinstance(template, str):
            # Fast path: if the entire string is exactly one placeholder,
            # return the raw value to preserve its type (int, float, bool, etc.)
            stripped = template.strip()
            for key, value in params.items():
                placeholder = f"{{{{{key}}}}}"
                if stripped == placeholder:
                    return value

            # General case: string interpolation (always produces a string)
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

    def _extract_total_available(self, response: dict, data: list) -> int:
        """Extract total available using configured total_results_path."""
        path = self.source_config.total_results_path
        if not path:
            return len(data)

        value = response
        for part in path.split("."):
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return len(data)

        if isinstance(value, (int, float)):
            return int(value)
        return len(data)

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


    def fetch_detail(self, event_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch detail data for a single event using the detail query config.

        Args:
            event_id: Source event ID to query

        Returns:
            Raw response dict from the detail query, or None on failure.
        """
        detail_config = self.source_config.detail_query
        if not detail_config or not detail_config.get("enabled"):
            return None

        import requests

        template = detail_config.get("template", "")
        variables = self._substitute_variables(
            detail_config.get("variables", {}),
            {"source_event_id": event_id},
        )

        endpoint = self.source_config.endpoint
        try:
            resp = requests.post(
                endpoint,
                json={"query": template, "variables": variables},
                timeout=self.source_config.timeout_seconds,
            )
            resp.raise_for_status()
            data = resp.json()

            # Navigate to response using response_path
            response_path = detail_config.get("response_path", "data")
            result = data
            for part in response_path.split("."):
                if isinstance(result, dict):
                    result = result.get(part)
                else:
                    return None
            return result if isinstance(result, dict) else None

        except Exception as e:
            logger.warning(f"Detail query failed for event {event_id}: {e}")
            return None


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

        # Create HTML enrichment scraper if enabled
        self.html_enrichment_scraper = None
        if source_config.html_enrichment.get("enabled"):
            try:
                from src.ingestion.adapters.scraper_adapter import (
                    HtmlEnrichmentConfig,
                    HtmlEnrichmentScraper,
                )

                enrichment_cfg = HtmlEnrichmentConfig(
                    enabled=True,
                    engine_type=source_config.html_enrichment.get(
                        "engine_type", "hybrid"
                    ),
                    rate_limit_per_second=source_config.html_enrichment.get(
                        "rate_limit_per_second", 2.0
                    ),
                    timeout_s=source_config.html_enrichment.get("timeout_s", 15.0),
                )
                self.html_enrichment_scraper = HtmlEnrichmentScraper(enrichment_cfg)
            except ImportError:
                logger.warning(
                    "Scrapping service not available; HTML enrichment disabled"
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

    # ========================================================================
    # MULTI-CITY + DATE-WINDOW EXECUTION
    # ========================================================================

    def execute(self, **kwargs) -> PipelineExecutionResult:
        """
        Execute pipeline with multi-city support.

        If config has defaults.areas (dict of city_name: area_id),
        iterates over each city. Otherwise falls back to single-area execution.
        """
        areas = self.source_config.defaults.get("areas", {})
        if not areas:
            return super().execute(**kwargs)

        self.execution_id = self._generate_execution_id()
        self.execution_start_time = datetime.now(timezone.utc)
        self.logger.info(
            f"Starting multi-city execution: {self.execution_id} "
            f"({len(areas)} cities)"
        )

        all_raw_events = []
        fetch_errors = []

        for city_name, area_id in areas.items():
            self.logger.info(f"Fetching events for {city_name} (area_id={area_id})...")
            try:
                raw_events = self._fetch_with_date_splitting(
                    area_id=area_id, city_name=city_name, **kwargs
                )
                self.logger.info(f"  {city_name}: {len(raw_events)} raw events fetched")
                all_raw_events.extend(raw_events)
            except Exception as e:
                self.logger.error(f"  {city_name}: fetch failed: {e}")
                fetch_errors.append({"error": str(e), "city": city_name})

        self.logger.info(f"Total raw events across all cities: {len(all_raw_events)}")

        # Process all events through pipeline stages
        normalized_events = self._process_events_batch(all_raw_events)

        # Add informational normalization note for traceability
        total_raw_fetched = len(all_raw_events)
        for event in normalized_events:
            event.normalization_errors.append(
                NormalizationError(
                    message=f"Info: Batch contained {total_raw_fetched} raw events from API ingestion",
                    category=NormalizationCategory.API_INGESTION,
                )
            )

        # Deduplication
        if self.config.deduplicate and normalized_events:
            from src.ingestion.deduplication import (
                DeduplicationStrategy,
                get_deduplicator,
            )

            deduplicator = get_deduplicator(
                DeduplicationStrategy(self.config.deduplication_strategy)
            )
            before_count = len(normalized_events)
            normalized_events = deduplicator.deduplicate(normalized_events)
            self.logger.info(
                f"Deduplication: {before_count} -> {len(normalized_events)} events"
            )

        status = PipelineStatus.SUCCESS if normalized_events else PipelineStatus.FAILED
        if normalized_events and len(normalized_events) < len(all_raw_events):
            status = PipelineStatus.PARTIAL_SUCCESS

        result = PipelineExecutionResult(
            status=status,
            source_name=self.config.source_name,
            source_type=self.source_type,
            execution_id=self.execution_id,
            started_at=self.execution_start_time,
            ended_at=datetime.now(timezone.utc),
            total_events_processed=len(all_raw_events),
            successful_events=len(normalized_events),
            failed_events=len(all_raw_events) - len(normalized_events),
            events=normalized_events,
            errors=fetch_errors,
            metadata={
                "cities": list(areas.keys()),
                "total_raw_fetched": len(all_raw_events),
            },
        )

        self.logger.info(
            f"Multi-city pipeline completed: "
            f"{result.successful_events}/{result.total_events_processed} successful"
        )
        return result

    def _fetch_with_date_splitting(
        self,
        area_id: int,
        city_name: str,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """
        Fetch events for a single area using an adaptive sliding date window.

        Walks through the full date range in windows that automatically shrink
        when a window is saturated (total_available > fetched) and grow back
        when data density decreases.

        Supports fractional-day windows (down to 6 hours) so even a single
        dense day can be split into sub-day windows, preventing data loss.

        Algorithm:
        1. Start at range_start with an initial 7-day window.
        2. Fetch events for [cursor, cursor + window).
        3. If saturated AND window can shrink: halve the window, retry same cursor.
        4. If saturated at minimum window: accept partial data, log warning, advance.
        5. If not saturated: advance cursor, gradually double window toward initial.

        Args:
            area_id: The area/city ID for the API
            city_name: Human-readable city name (for logging)
            **kwargs: Additional params passed to adapter.fetch()

        Returns:
            List of raw event dicts
        """
        days_ahead = self.source_config.defaults.get("days_ahead", 30)
        range_start = datetime.strptime(
            kwargs.pop("date_from", None)
            or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "%Y-%m-%d",
        )
        range_end = datetime.strptime(
            kwargs.pop("date_to", None)
            or (datetime.now(timezone.utc) + timedelta(days=days_ahead)).strftime(
                "%Y-%m-%d"
            ),
            "%Y-%m-%d",
        )

        # Compute the capacity of a single fetch call (pages * page_size)
        page_size = self.source_config.default_page_size
        max_pages = self.source_config.max_pages
        fetch_capacity = page_size * max_pages

        # Window sizing (in hours for sub-day granularity)
        initial_window_hours = 7 * 24  # 7 days
        min_window_hours = 6  # 6 hours — allows 4 slices per day
        window_hours = initial_window_hours

        all_events: List[Dict[str, Any]] = []
        cursor = range_start

        self.logger.info(
            f"  {city_name}: sliding window fetch "
            f"[{range_start.date()}..{range_end.date()}] "
            f"(capacity={fetch_capacity}/call, window={window_hours}h)"
        )

        while cursor < range_end:
            window_end = min(cursor + timedelta(hours=window_hours), range_end)

            # Snap to date strings for the API (most APIs accept date, not datetime)
            date_from_str = cursor.strftime("%Y-%m-%d")
            date_to_str = window_end.strftime("%Y-%m-%d")

            # Avoid zero-width windows when sub-day and dates collapse
            if date_from_str == date_to_str and window_hours < 24:
                # Sub-day window within same calendar day — use next day as end
                date_to_str = (cursor + timedelta(days=1)).strftime("%Y-%m-%d")

            fetch_result = self.adapter.fetch(
                area_id=area_id,
                date_from=date_from_str,
                date_to=date_to_str,
                **kwargs,
            )

            if fetch_result.success and fetch_result.raw_data:
                fetched = len(fetch_result.raw_data)
                total_available = fetch_result.metadata.get("total_available", fetched)
                saturated = total_available > fetched

                if saturated and window_hours > min_window_hours:
                    # Window too big for this density — halve and retry
                    window_hours = max(window_hours // 2, min_window_hours)
                    self.logger.info(
                        f"  {city_name}: [{date_from_str}..{date_to_str}] "
                        f"{fetched}/{total_available} events "
                        f"(SATURATED — shrinking to {window_hours}h)"
                    )
                    continue

                # Accept the data (either not saturated or at minimum window)
                all_events.extend(fetch_result.raw_data)

                if saturated:
                    self.logger.warning(
                        f"  {city_name}: [{date_from_str}..{date_to_str}] "
                        f"{fetched}/{total_available} events "
                        f"(SATURATED at min window — {total_available - fetched} "
                        f"events may be missing)"
                    )
                else:
                    self.logger.info(
                        f"  {city_name}: [{date_from_str}..{date_to_str}] "
                        f"{fetched}/{total_available} events"
                    )

                # Advance cursor past this window
                cursor = window_end

                # Gradually restore window size toward initial
                if window_hours < initial_window_hours:
                    window_hours = min(window_hours * 2, initial_window_hours)
            else:
                # Fetch failed or empty — advance to avoid infinite loop
                self.logger.warning(
                    f"  {city_name}: [{date_from_str}..{date_to_str}] "
                    f"no results or fetch failed, advancing"
                )
                cursor = window_end

        self.logger.info(
            f"  {city_name}: sliding window complete — "
            f"{len(all_events)} total raw events"
        )
        return all_events

    # ========================================================================
    # PIPELINE STAGES
    # ========================================================================

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

        # Parse price — supports both string (ra.co) and pre-parsed numeric fields (Ticketmaster)
        cost_min = parsed_event.get("cost_min")
        cost_max = parsed_event.get("cost_max")
        cost_currency = parsed_event.get("cost_currency")

        from decimal import Decimal

        min_price: Optional[Decimal] = None
        max_price: Optional[Decimal] = None
        price_raw: Optional[str] = None
        currency: str = str(loc_defaults.get("currency", "EUR"))

        if cost_min is not None or cost_max is not None:
            # Pre-parsed numeric price fields
            min_price = Decimal(str(cost_min)) if cost_min is not None else None
            max_price = Decimal(str(cost_max)) if cost_max is not None else None
            if cost_currency:
                currency = str(cost_currency)
            price_raw = (
                f"{min_price}-{max_price} {currency}" if max_price else str(min_price)
            )
            is_free = min_price == 0 and (max_price is None or max_price == 0)
        else:
            # String price (e.g. "10€", "Free")
            price_str = parsed_event.get("cost") or ""
            parsed_min, parsed_max, parsed_currency = CurrencyParser.parse_price_string(
                str(price_str)
            )
            min_price = Decimal(str(parsed_min)) if parsed_min is not None else None
            max_price = Decimal(str(parsed_max)) if parsed_max is not None else None
            is_free = (min_price is None and max_price is None) or str(
                price_str
            ).lower() in ["free", "0", "gratis"]
            if parsed_currency:
                currency = str(parsed_currency)
            price_raw = str(price_str) if price_str else None

        price = PriceInfo(
            currency=currency,
            is_free=is_free,
            minimum_price=min_price,
            maximum_price=max_price,
            price_raw_text=price_raw,
        )

        # Build organizer
        organizer = OrganizerInfo(
            name=parsed_event.get("organizer_name")
            or parsed_event.get("venue_name")
            or "Unknown",
        )

        # Build source info
        source_name = self.source_config.source_name
        source_url = parsed_event.get("source_url") or ""
        source = SourceInfo(
            source_name=source_name,
            source_event_id=source_event_id,
            source_url=source_url,
            source_updated_at=datetime.now(timezone.utc),
        )

        # Generate platform-wide deterministic UUID for event_id
        # based on source, source_event_id, title, and start_datetime.
        # This allows multiple events per source record while maintaining stability.
        title_for_id = parsed_event.get("title") or "Untitled Event"
        seed = f"{source_name}:{source_event_id}:{title_for_id}:{start_dt.isoformat()}"
        event_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, seed))

        # Build taxonomy dimensions
        taxonomy_objs = [
            TaxonomyDimension(
                primary_category=PrimaryCategory(dim["primary_category"]),
                subcategory=dim.get("subcategory"),
                subcategory_name=dim.get("subcategory_name"),
                values=dim.get("values", []),
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
        extracted_fields = {}
        if self.feature_extractor:
            missing_fields = self.source_config.feature_extraction.get(
                "fill_missing", []
            )
            if missing_fields:
                extracted_fields = self.feature_extractor.fill_missing_fields(
                    parsed_event, missing_fields
                )

                # Apply extracted event_type
                if "event_type" in extracted_fields and not event_type:
                    try:
                        event_type = EventType(extracted_fields["event_type"])
                    except ValueError:
                        pass

        # Get tags from extracted fields or parsed event
        tags = extracted_fields.get("tags") or parsed_event.get("tags", [])

        # Build artists list
        artist_names = parsed_event.get("artists", [])
        artists = [ArtistInfo(name=name) for name in artist_names if name]

        # Build engagement metrics from API fields
        attending = parsed_event.get("attending")
        interested = parsed_event.get("interested_count")
        engagement = None
        if attending is not None or interested is not None:
            try:
                engagement = EngagementMetrics(
                    going_count=int(attending) if attending is not None else None,
                    interested_count=int(interested) if interested is not None else None,
                )
            except (ValueError, TypeError):
                pass

        # Capacity from venue_live (if it's an int)
        venue_live = parsed_event.get("venue_live")
        capacity = None
        if isinstance(venue_live, int) and venue_live > 0:
            capacity = venue_live

        # Image URL with flyer_front fallback
        image_url = parsed_event.get("image_url")
        if not image_url:
            flyer_front = parsed_event.get("flyer_front")
            if flyer_front:
                image_url = flyer_front

        # Build custom_fields (RA-specific metadata)
        custom_fields = {}
        if parsed_event.get("is_ticketed"):
            custom_fields["is_ticketed"] = True
        pick_blurb = parsed_event.get("pick_blurb")
        if pick_blurb:
            custom_fields["pick_blurb"] = pick_blurb
        pick_id = parsed_event.get("pick_id")
        if pick_id:
            custom_fields["pick_id"] = pick_id

        return EventSchema(
            event_id=event_id,
            title=parsed_event.get("title", "Untitled Event"),
            description=parsed_event.get("description"),
            primary_category=PrimaryCategory(primary_cat),
            taxonomy_dimensions=taxonomy_objs,
            start_datetime=start_dt,
            end_datetime=end_dt,
            location=location,
            event_type=event_type or EventType.OTHER,
            format=EventFormat.IN_PERSON,
            price=price,
            organizer=organizer,
            artists=artists,
            image_url=image_url,
            source=source,
            tags=tags,
            engagement=engagement,
            capacity=capacity,
            custom_fields=custom_fields,
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

    def validate_event(
        self, event: EventSchema
    ) -> Tuple[bool, List[NormalizationError]]:
        """Validate event using configured rules."""
        errors: List[NormalizationError] = []
        validation_config = self.source_config.validation

        # Required fields
        required_fields = validation_config.get(
            "required_fields", ["title", "source_event_id"]
        )
        for field_name in required_fields:
            if field_name == "title" and (
                not event.title or event.title == "Untitled Event"
            ):
                errors.append(
                    NormalizationError(
                        message="Title is required",
                        category=NormalizationCategory.MISSING_REQUIRED,
                    )
                )
            elif field_name == "source_event_id" and not event.source.source_event_id:
                errors.append(
                    NormalizationError(
                        message="Source event ID is required",
                        category=NormalizationCategory.MISSING_REQUIRED,
                    )
                )

        # Future events only
        if validation_config.get("future_events_only", True):
            if event.start_datetime < datetime.now(timezone.utc):
                errors.append(
                    NormalizationError(
                        message="Warning: Event start time is in the past",
                        category=NormalizationCategory.DATA_VALIDATION,
                    )
                )

        # Location validation
        if not event.location.city:
            errors.append(
                NormalizationError(
                    message="City is required",
                    category=NormalizationCategory.MISSING_REQUIRED,
                )
            )

        # Price validation
        if event.price.minimum_price and event.price.minimum_price < 0:
            errors.append(
                NormalizationError(
                    message="Minimum price cannot be negative",
                    category=NormalizationCategory.DATA_VALIDATION,
                )
            )

        is_valid = not any(
            e.category == NormalizationCategory.MISSING_REQUIRED for e in errors
        )
        return is_valid, errors

    def enrich_event(self, event: EventSchema) -> EventSchema:
        """Enrich event with additional computed data."""
        # Fetch compressed HTML if enrichment scraper is configured
        if (
            getattr(self, "html_enrichment_scraper", None)
            and event.source.source_url
            and not event.source.compressed_html
        ):
            try:
                compressed = self.html_enrichment_scraper.fetch_compressed_html(
                    event.source.source_url
                )
                if compressed:
                    event.source.compressed_html = compressed
                else:
                    logger.warning(
                        f"HTML enrichment returned None for {event.source.source_url}"
                    )
                    event.normalization_errors.append(
                        NormalizationError(
                            message=f"HTML enrichment returned no content for {event.source.source_url}",
                            category=NormalizationCategory.ENRICHMENT_FAILURE,
                        )
                    )
            except Exception as e:
                logger.warning(
                    f"HTML enrichment failed for {event.source.source_url}: {e}"
                )
                event.normalization_errors.append(
                    NormalizationError(
                        message=f"HTML enrichment error: {e}",
                        category=NormalizationCategory.ENRICHMENT_FAILURE,
                    )
                )

        # Detail query enrichment (coordinates, minimumAge)
        detail_config = self.source_config.detail_query
        if detail_config and detail_config.get("enabled") and event.source.source_event_id:
            try:
                # Rate limit detail calls
                import time

                rate = detail_config.get("rate_limit_per_second", 2.0)
                if rate > 0:
                    time.sleep(1.0 / rate)

                detail_data = self.adapter.fetch_detail(event.source.source_event_id)
                if detail_data:
                    field_mappings = detail_config.get("field_mappings", {})

                    # Extract fields using dot-path navigation
                    def _extract(data, path):
                        for part in path.split("."):
                            if isinstance(data, dict):
                                data = data.get(part)
                            else:
                                return None
                        return data

                    # minimum_age -> age_restriction
                    min_age = _extract(detail_data, field_mappings.get("minimum_age", ""))
                    if min_age is not None and not event.age_restriction:
                        event.age_restriction = str(min_age)

                    # venue coordinates
                    lat = _extract(detail_data, field_mappings.get("venue_latitude", ""))
                    lng = _extract(detail_data, field_mappings.get("venue_longitude", ""))
                    if lat is not None and lng is not None and not event.location.coordinates:
                        try:
                            event.location.coordinates = Coordinates(
                                latitude=float(lat), longitude=float(lng)
                            )
                        except (ValueError, TypeError) as e:
                            logger.warning(f"Invalid coordinates for event {event.source.source_event_id}: {e}")
                else:
                    logger.debug(
                        f"Detail query returned no data for event {event.source.source_event_id}"
                    )
            except Exception as e:
                logger.warning(
                    f"Detail enrichment failed for event {event.source.source_event_id}: {e}"
                )
                event.normalization_errors.append(
                    NormalizationError(
                        message=f"Detail query enrichment error: {e}",
                        category=NormalizationCategory.ENRICHMENT_FAILURE,
                    )
                )

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
    Create a BaseAPIPipeline from YAML config dict.

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
        taxonomy_config=source_config_dict.get("taxonomy_suggestions", {}),
        event_type_rules=source_config_dict.get("event_type_rules", []),
        defaults=source_config_dict.get("defaults", {}),
        validation=source_config_dict.get("validation", {}),
        feature_extraction=source_config_dict.get("enrichment", {}).get(
            "feature_extraction", source_config_dict.get("feature_extraction", {})
        ),
        html_enrichment=source_config_dict.get("enrichment", {}).get(
            "compressed_html", {}
        ),
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
