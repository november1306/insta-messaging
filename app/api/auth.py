"""
Authentication dependencies for CRM Integration API

Implements proper API key validation with database lookup and bcrypt verification.
Supports both stub mode (development) and real mode (production).

Expected environment variable: ENVIRONMENT = "development" | "staging" | "production" | "prod"
Must be set in .env or deployment config. Defaults to "development" if unset.

Set USE_STUB_AUTH=true to force stub authentication in development.
"""
from fastapi import Header, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import logging
import os

from app.db.connection import get_db_session
from app.db.models import APIKey
from app.services.api_key_service import APIKeyService

logger = logging.getLogger(__name__)


def _verify_api_key_stub(authorization: Optional[str]) -> str:
    """
    STUB authentication for backward compatibility and testing.
    Only enabled if USE_STUB_AUTH=true environment variable is set.

    Args:
        authorization: Authorization header value (e.g., "Bearer test_key")

    Returns:
        str: API key string for stub implementation

    Raises:
        HTTPException: 401 if Authorization header is missing or invalid format
    """
    # Check if Authorization header is present and valid format
    if not authorization or not authorization.startswith("Bearer "):
        logger.warning("API request rejected: Invalid or missing Authorization header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization. Use 'Authorization: Bearer <api_key>'.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Extract the key
    api_key = authorization[7:].strip()  # Remove "Bearer " prefix

    # STUB: Accept any non-empty key
    if not api_key:
        logger.warning("API request rejected: Empty API key")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Empty API key. Provide a valid API key after 'Bearer '.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    logger.debug("STUB AUTH: Accepted API key (stub mode enabled)")
    return api_key


async def verify_api_key(
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db_session)
) -> APIKey:
    """
    Verify API key from Authorization header using database validation.

    Falls back to stub authentication if USE_STUB_AUTH=true environment variable is set.
    This allows gradual migration from stub to real auth.

    Args:
        authorization: Authorization header value (e.g., "Bearer sk_test_...")
        db: Database session (injected)

    Returns:
        APIKey: Validated API key object with permissions

    Raises:
        HTTPException: 401 if authentication fails
    """
    # Check if stub mode is enabled
    use_stub = os.getenv("USE_STUB_AUTH", "false").lower() in ("true", "1", "yes")

    if use_stub:
        logger.warning("Using STUB authentication (USE_STUB_AUTH=true)")
        _verify_api_key_stub(authorization)
        # Return a fake APIKey for stub mode (not from database)
        from app.db.models import APIKeyType
        return APIKey(
            id="stub_key",
            key_prefix="stub",
            key_hash="stub",
            name="Stub Key",
            type=APIKeyType.ADMIN,
            is_active=True
        )

    # Real authentication from here

    # Check if Authorization header is present and valid format
    if not authorization or not authorization.startswith("Bearer "):
        logger.warning("API request rejected: Invalid or missing Authorization header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization. Use 'Authorization: Bearer <api_key>'.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Extract the key
    api_key = authorization[7:].strip()  # Remove "Bearer " prefix

    if not api_key:
        logger.warning("API request rejected: Empty API key")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Empty API key. Provide a valid API key after 'Bearer '.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Validate against database
    db_key = await APIKeyService.validate_api_key(db, api_key)

    if not db_key:
        logger.warning(f"API request rejected: Invalid API key")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key. Check your credentials.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    logger.debug(f"API key validated: {db_key.id} (name: {db_key.name})")
    return db_key
