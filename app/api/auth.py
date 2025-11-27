"""
Authentication dependencies for CRM Integration API

Implements API key validation with database lookup and bcrypt verification.
"""
from fastapi import Header, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import logging

from app.db.connection import get_db_session
from app.db.models import APIKey
from app.services.api_key_service import APIKeyService

logger = logging.getLogger(__name__)


async def verify_api_key(
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db_session)
) -> APIKey:
    """
    Verify API key from Authorization header using database validation.

    Args:
        authorization: Authorization header value (e.g., "Bearer sk_test_...")
        db: Database session (injected)

    Returns:
        APIKey: Validated API key object with permissions

    Raises:
        HTTPException: 401 if authentication fails
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
        logger.warning("API request rejected: Invalid API key")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key. Check your credentials.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    logger.debug(f"API key validated: {db_key.id} (name: {db_key.name})")
    return db_key
