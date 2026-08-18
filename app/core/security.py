import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
import jwt
import bcrypt
from app.core.config import settings

# 1. Password Hashing with native bcrypt
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plaintext password against a stored bcrypt hash."""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8")
    )


def get_password_hash(password: str) -> str:
    """Generates a salted bcrypt hash from a plaintext password."""
    # Truncate to 72 bytes to adhere to bcrypt specification
    password_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password_bytes, salt).decode("utf-8")


# 2. JWT Generation & Verification
def create_access_token(
    subject: str | Any,
    expires_delta: timedelta | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """Creates an encoded JSON Web Token (JWT)."""
    now = datetime.now(timezone.utc)
    
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode: dict[str, Any] = {
        "sub": str(subject),
        "iat": now,
        "exp": expire,
    }

    if extra_claims:
        to_encode.update(extra_claims)

    return jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Decodes and validates a JWT token."""
    try:
        return jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
    except jwt.PyJWTError:
        return None


# 3. API Key Generation & Hashing Utilities
def generate_api_key(prefix: str = "wh_live_") -> tuple[str, str, str]:
    """Generates a secure random API key."""
    random_secret = secrets.token_urlsafe(32)
    raw_key = f"{prefix}{random_secret}"
    key_prefix = raw_key[:16]
    hashed_key = hash_api_key(raw_key)
    return raw_key, key_prefix, hashed_key


def hash_api_key(api_key: str) -> str:
    """Computes a SHA-256 hexadecimal digest for an API key."""
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()