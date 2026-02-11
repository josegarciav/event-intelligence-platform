"""
src.schemas.user

Pydantic schemas for platform users.
Used for API validation, serialization, and DB interaction.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class AttendanceStatus(str, Enum):
    """Maps to event_attendees.attendance_status column."""

    GOING = "going"
    INTERESTED = "interested"
    ATTENDED = "attended"


class OrganizerRole(str, Enum):
    """Maps to organizer_users.role column."""

    OWNER = "owner"
    MANAGER = "manager"
    EDITOR = "editor"


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


# ---------------------------------------------------------------------------
# Junction Table Schemas: event_attendees
# ---------------------------------------------------------------------------


class EventAttendeeCreate(BaseModel):
    """Schema for creating a record in the event_attendees junction table."""

    event_id: UUID
    user_id: UUID
    attendance_status: AttendanceStatus = AttendanceStatus.INTERESTED


class EventAttendeeRead(BaseModel):
    """Schema returned when reading from the event_attendees junction table."""

    event_id: UUID
    user_id: UUID
    attendance_status: AttendanceStatus
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Junction Table Schemas: organizer_users
# ---------------------------------------------------------------------------


class OrganizerUserCreate(BaseModel):
    """Schema for creating a record in the organizer_users junction table."""

    organizer_id: UUID
    user_id: UUID
    role: OrganizerRole = OrganizerRole.MANAGER


class OrganizerUserRead(BaseModel):
    """Schema returned when reading from the organizer_users junction table."""

    organizer_id: UUID
    user_id: UUID
    role: OrganizerRole
    created_at: datetime

    class Config:
        from_attributes = True
