"""
JWT token utilities for authentication.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, ExpiredSignatureError, jwt
from pydantic import BaseModel
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


class TokenData(BaseModel):
    """Data encoded in JWT token."""
    sub: str  # Subject (user ID)
    type: str  # Token type: "access" or "refresh"
    exp: datetime  # Expiration time


class TokenPair(BaseModel):
    """Access and refresh token pair."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # Seconds until access token expires


def create_access_token(user_id: str) -> str:
    """
    Create a JWT access token.

    Args:
        user_id: User ID to encode in token

    Returns:
        Encoded JWT token string
    """
    expires = datetime.now(timezone.utc) + timedelta(
        minutes=settings.jwt_access_token_expire_minutes
    )

    payload = {
        "sub": user_id,
        "type": "access",
        "exp": expires,
        "iat": datetime.now(timezone.utc),
    }

    return jwt.encode(
        payload,
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm
    )


def create_refresh_token(user_id: str) -> str:
    """
    Create a JWT refresh token.

    Args:
        user_id: User ID to encode in token

    Returns:
        Encoded JWT token string
    """
    expires = datetime.now(timezone.utc) + timedelta(
        days=settings.jwt_refresh_token_expire_days
    )

    payload = {
        "sub": user_id,
        "type": "refresh",
        "exp": expires,
        "iat": datetime.now(timezone.utc),
    }

    return jwt.encode(
        payload,
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm
    )


def create_token_pair(user_id: str) -> TokenPair:
    """
    Create both access and refresh tokens.

    Args:
        user_id: User ID to encode in tokens

    Returns:
        TokenPair with both tokens
    """
    return TokenPair(
        access_token=create_access_token(user_id),
        refresh_token=create_refresh_token(user_id),
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


def verify_token(token: str, expected_type: str = "access") -> Optional[TokenData]:
    """
    Verify and decode a JWT token.

    Args:
        token: JWT token string
        expected_type: Expected token type ("access" or "refresh")

    Returns:
        TokenData if valid, None if invalid
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm]
        )

        user_id = payload.get("sub")
        token_type = payload.get("type")
        exp = payload.get("exp")

        if user_id is None or token_type is None:
            logger.debug(f"Token missing required fields: sub={user_id is not None}, type={token_type is not None}")
            return None

        if token_type != expected_type:
            logger.debug(f"Token type mismatch: expected {expected_type}, got {token_type}")
            return None

        return TokenData(
            sub=user_id,
            type=token_type,
            exp=datetime.fromtimestamp(exp, tz=timezone.utc)
        )

    except ExpiredSignatureError:
        logger.debug(f"Token expired for type {expected_type}")
        return None
    except JWTError as e:
        logger.warning(f"JWT verification failed: {type(e).__name__}: {e}")
        return None


def get_refresh_token_expiry() -> datetime:
    """Get the expiry datetime for a new refresh token."""
    return datetime.now(timezone.utc) + timedelta(
        days=settings.jwt_refresh_token_expire_days
    )
