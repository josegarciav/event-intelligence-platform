"""Pydantic models defining the V1 config contract.

Design goals:
- strict enough to prevent silent failures
- flexible enough for incremental adoption
- supports single-source configs and multi-source config files (arrays)
- keeps warnings separate from errors (via helper checks)

Requires: pydantic>=2
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

# ----------------------------
# Enums
# ----------------------------


class EngineType(str, Enum):
    """Supported engine types."""

    http = "http"
    browser = "browser"
    hybrid = "hybrid"


class LinkExtractMethod(str, Enum):
    """Supported link extraction methods."""

    regex = "regex"
    css = "css"
    xpath = "xpath"
    js = "js"


class RobotsPolicy(str, Enum):
    """Policy for handling robots.txt."""

    respect = "respect"
    ignore = "ignore"
    unknown = "unknown"


class DataRightsStatus(str, Enum):
    """Data rights classification for a source."""

    allowed = "allowed"
    restricted = "restricted"
    unknown = "unknown"


class PollingStrategy(str, Enum):
    """Strategy for polling frequency adjustment."""

    fixed = "fixed"
    backoff = "backoff"
    adaptive = "adaptive"


class ActionType(str, Enum):
    """Supported browser action types."""

    scroll = "scroll"
    click = "click"
    wait_for = "wait_for"
    close_popup = "close_popup"
    type = "type"
    hover = "hover"


# ----------------------------
# Sub-models
# ----------------------------


class ScheduleConfig(BaseModel):
    """Configure schedule for a scraping source."""

    frequency: str | None = Field(
        default=None, description="Human-friendly frequency like '15m', '2h', 'daily'."
    )
    timezone: str | None = Field(default=None, description="IANA timezone, e.g., Europe/Madrid")
    priority: int = Field(default=5, ge=1, le=10)
    polling_strategy: PollingStrategy = Field(default=PollingStrategy.fixed)

    window: dict[str, Any] | None = Field(
        default=None,
        description="Optional run window constraints (team-defined shape).",
    )


class PagingConfig(BaseModel):
    """Configure pagination behavior for entrypoints."""

    mode: str = Field(default="page", description="page | offset | cursor | custom")
    start: int | None = None
    end: int | None = None
    step: int | None = None
    pages: int | None = None
    page_param: str | None = None


class EntryPoint(BaseModel):
    """Define an entry point URL with optional paging and parameters."""

    url: str = Field(..., description="Entrypoint URL template. May include {page} etc.")
    paging: PagingConfig | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    headers: dict[str, Any] = Field(default_factory=dict)
    cookies: dict[str, Any] = Field(default_factory=dict)


class RateLimitPolicy(BaseModel):
    """Configure rate limiting for requests."""

    rps: float | None = Field(default=None, ge=0.0)
    burst: int | None = Field(default=None, ge=1)
    min_delay_s: float | None = Field(default=None, ge=0.0)
    jitter_s: float | None = Field(default=None, ge=0.0)


class RetryPolicy(BaseModel):
    """Configure retry behavior for failed requests."""

    max_retries: int = Field(default=3, ge=0, le=20)
    backoff: str = Field(default="exp", description="exp | fixed | none")
    retry_on_status: list[int] = Field(default_factory=lambda: [429, 500, 502, 503, 504])


class CaptchaConfig(BaseModel):
    """Configure captcha handling expectations."""

    expected: str = Field(default="possible", description="none|possible|likely")
    handler: str = Field(default="skip", description="manual|service|skip")


class EngineConfig(BaseModel):
    """Configure the scraping engine."""

    type: EngineType = Field(default=EngineType.http)
    browser: str | None = Field(default=None, description="seleniumbase|playwright")
    headless: bool = True

    timeout_s: float = Field(default=15.0, ge=1.0)
    verify_ssl: bool = True

    user_agent: str | None = None
    proxy_pool: str | None = None

    rate_limit_policy: RateLimitPolicy = Field(default_factory=RateLimitPolicy)
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)
    captcha: CaptchaConfig | None = None


class BrowserAction(BaseModel):
    """Define a browser action to execute during rendering."""

    type: ActionType
    selector: str | None = None
    timeout_s: float | None = Field(default=None, ge=0.0)

    # extra params for actions (scroll distances, repeat, text, etc.)
    params: dict[str, Any] = Field(default_factory=dict)


class LinkExtractConfig(BaseModel):
    """Configure link extraction from listing pages."""

    method: LinkExtractMethod = Field(default=LinkExtractMethod.regex)
    pattern: str | None = Field(default=None, description="For regex method")
    selector: str | None = Field(default=None, description="For css/xpath/js method")
    identifier: str | None = Field(
        default=None, description="Optional filter substring for extracted links"
    )


class DiscoveryConfig(BaseModel):
    """Configure link discovery for a source."""

    link_extract: LinkExtractConfig = Field(default_factory=LinkExtractConfig)
    dedupe: dict[str, Any] = Field(default_factory=dict)


class StorageTarget(BaseModel):
    """Configure a single storage output target."""

    enabled: bool = True
    format: str = Field(default="parquet", description="parquet|jsonl|csv|db")
    compression: str | None = Field(default="snappy")
    path: str | None = None  # if None, library decides default layout


class StorageConfig(BaseModel):
    """Configure storage targets for pipeline output."""

    raw_pages: StorageTarget = Field(
        default_factory=lambda: StorageTarget(enabled=True, format="parquet")
    )
    raw_items: StorageTarget = Field(
        default_factory=lambda: StorageTarget(enabled=False, format="parquet")
    )
    items: StorageTarget = Field(
        default_factory=lambda: StorageTarget(enabled=True, format="parquet")
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


class AntiBotConfig(BaseModel):
    """Configure anti-bot handling policies."""

    robots_policy: RobotsPolicy = Field(default=RobotsPolicy.unknown)
    data_rights_status: DataRightsStatus = Field(default=DataRightsStatus.unknown)
    recaptcha: bool | None = None


# ----------------------------
# Source (top-level unit)
# ----------------------------


class SourceConfig(BaseModel):
    """Top-level source configuration model."""

    config_version: str = Field(default="1.0")
    source_id: str = Field(..., min_length=1)

    enabled: bool = True
    owner: str | None = None
    kind: str | None = None
    tags: list[str] = Field(default_factory=list)

    schedule: ScheduleConfig | None = None
    entrypoints: list[EntryPoint] = Field(default_factory=list)

    engine: EngineConfig = Field(default_factory=EngineConfig)
    anti_bot: AntiBotConfig | None = None

    actions: list[BrowserAction] = Field(default_factory=list)
    discovery: DiscoveryConfig | None = None
    storage: StorageConfig = Field(default_factory=StorageConfig)

    # allow per-source extension fields without breaking parsing
    extensions: dict[str, Any] = Field(default_factory=dict)

    @field_validator("source_id")
    @classmethod
    def _validate_source_id(cls, v: str) -> str:
        v = v.strip()
        if " " in v:
            raise ValueError("source_id must not contain spaces")
        return v

    @model_validator(mode="after")
    def _post_checks(self) -> SourceConfig:
        # Basic consistency checks
        if self.engine.type == EngineType.browser and not self.engine.browser:
            # Not an error: we can default later; warn in loader
            pass

        # Link extractor requirements
        if self.discovery and self.discovery.link_extract.method == LinkExtractMethod.regex:
            if not self.discovery.link_extract.pattern:
                raise ValueError("discovery.link_extract.pattern is required when method=regex")

        if self.discovery and self.discovery.link_extract.method in (
            LinkExtractMethod.css,
            LinkExtractMethod.xpath,
            LinkExtractMethod.js,
        ):
            if not self.discovery.link_extract.selector:
                raise ValueError("discovery.link_extract.selector is required when method!=regex")

        return self


# ----------------------------
# Helpers
# ----------------------------

ConfigFile = SourceConfig | list[SourceConfig]


def export_json_schema() -> dict[str, Any]:
    """Export a JSON schema for SourceConfig.

    Useful for docs, linting, or external validation.
    """
    return SourceConfig.model_json_schema()
