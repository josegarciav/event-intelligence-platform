"""
src.schemas.user

Pydantic schemas for platform users.
Used for API validation, serialization, and DB interaction.
#TODO: Add ENUM classes on attendance_status, role.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


# ---------------------------------------------------------------------------
# Base Schemas
# ---------------------------------------------------------------------------

class UserBase(BaseModel):
    """
    Base user attributes shared across schemas.
    """

    email: EmailStr = Field(
        ...,
        description="User email address (unique identifier).",
    )

    first_name: str | None = Field(
        default=None,
        description="User first name.",
    )

    last_name: str | None = Field(
        default=None,
        description="User last name.",
    )

    display_name: str | None = Field(
        default=None,
        description="Public display name.",
    )

    profile_image_url: str | None = Field(
        default=None,
        description="URL to user profile image.",
    )


# ---------------------------------------------------------------------------
# Create Schema
# ---------------------------------------------------------------------------

class UserCreate(UserBase):
    """
    Schema used when creating a new user.
    """

    password: str = Field(
        ...,
        min_length=8,
        description="Plaintext password (hashed before storage).",
    )


# ---------------------------------------------------------------------------
# Update Schema
# ---------------------------------------------------------------------------

class UserUpdate(BaseModel):
    """
    Schema for updating user attributes.
    All fields optional.
    """

    first_name: str | None = None
    last_name: str | None = None
    display_name: str | None = None
    profile_image_url: str | None = None
    is_active: bool | None = None


# ---------------------------------------------------------------------------
# DB / Response Schema
# ---------------------------------------------------------------------------

class UserRead(UserBase):
    """
    Schema returned in API responses.
    """

    user_id: UUID
    is_active: bool
    is_verified: bool
    is_admin: bool

    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
