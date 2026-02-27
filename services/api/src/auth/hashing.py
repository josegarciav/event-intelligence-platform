"""Password hashing utilities using bcrypt."""

import bcrypt


def hash_password(plaintext: str) -> str:
    """Hash a plaintext password using bcrypt."""
    return bcrypt.hashpw(plaintext.encode(), bcrypt.gensalt()).decode()


def verify_password(plaintext: str, hashed: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    return bcrypt.checkpw(plaintext.encode(), hashed.encode())
