from __future__ import annotations

import time
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator, HttpUrl

class JobPostItem(BaseModel):
    source_id: str
    url: str
    title: str
    company: str
    location: str
    date_posted: Optional[str] = None
    contract_type: Optional[str] = None
    description: str
    tags: List[str] = Field(default_factory=list)
    raw_text: Optional[str] = None
    timestamp: float = Field(default_factory=time.time)

    # Metadata
    listing_url: Optional[str] = None
    extraction_meta: Dict[str, Any] = Field(default_factory=dict)

    @field_validator('url')
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not v.startswith(('http://', 'https://')):
            raise ValueError('URL must be absolute and start with http:// or https://')
        return v

    @field_validator('title')
    @classmethod
    def validate_title(cls, v: str) -> str:
        if len(v.strip()) < 3:
            raise ValueError('Title must be at least 3 characters long')
        return v

    @field_validator('description')
    @classmethod
    def validate_description(cls, v: str, info: Any) -> str:
        # We'll make min length configurable via extraction_meta or just use a default
        min_len = 10
        if len(v.strip()) < min_len:
            raise ValueError(f'Description must be at least {min_len} characters long')
        return v
