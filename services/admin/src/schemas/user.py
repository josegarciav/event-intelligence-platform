from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, EmailStr, field_validator
from src.models.user import Role


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    role: Role = Role.viewer

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class UserUpdate(BaseModel):
    role: Role | None = None
    is_active: bool | None = None


class UserRead(BaseModel):
    user_id: UUID
    email: str
    role: Role
    is_active: bool
    api_key: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ApiKeyResponse(BaseModel):
    api_key: str
    message: str = "Store this key securely — it will not be shown again."
