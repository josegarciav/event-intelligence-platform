from __future__ import annotations

import time
from typing import Any

from pydantic import BaseModel, Field, field_validator


class ProductItem(BaseModel):
    source_id: str
    url: str
    title: str
    text: str | None = None
    price: str | None = None
    currency: str | None = None
    seller: str | None = None
    location: str | None = None
    category_path: list[str] = Field(default_factory=list)
    images: list[str] = Field(default_factory=list)
    specs: dict[str, Any] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=time.time)

    @field_validator("url")
    @classmethod
    def validate_url_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("URL cannot be empty")
        return v

    @field_validator("title")
    @classmethod
    def validate_title_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Title cannot be empty")
        return v
