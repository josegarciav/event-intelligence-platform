from __future__ import annotations

import time
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator

class ProductItem(BaseModel):
    source_id: str
    url: str
    title: str
    text: Optional[str] = None
    price: Optional[str] = None
    currency: Optional[str] = None
    seller: Optional[str] = None
    location: Optional[str] = None
    category_path: List[str] = Field(default_factory=list)
    images: List[str] = Field(default_factory=list)
    specs: Dict[str, Any] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=time.time)

    @field_validator('url')
    @classmethod
    def validate_url_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('URL cannot be empty')
        return v

    @field_validator('title')
    @classmethod
    def validate_title_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('Title cannot be empty')
        return v
