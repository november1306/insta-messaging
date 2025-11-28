"""
Authentication dependencies for CRM Integration API

Implements API key validation with database lookup and bcrypt verification.
Also provides JWT session validation for UI authentication.
"""
from fastapi import Header, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import logging
import jwt

from app.db.connection import get_db_session
from app.db.models import APIKey
from app.services.api_key_service import APIKeyService
from app.config import settings

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


async def verify_ui_session(
    authorization: Optional[str] = Header(None)
) -> dict:
    """
    Verify UI session token (JWT) from Authorization header.

    Used for UI authentication (Phase 1: session-based auth).
    Unlike API keys, this validates JWT tokens for frontend sessions.

    Args:
        authorization: Authorization header value (e.g., "Bearer <jwt_token>")

    Returns:
        dict: Session context with account_id
              Example: {"account_id": "123456789"}

    Raises:
        HTTPException: 401 if token is missing, invalid, or expired
    """
    # Check if Authorization header is present and valid format
    if not authorization or not authorization.startswith("Bearer "):
        logger.warning("UI session rejected: Missing or invalid Authorization header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing session token. Please login again.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Extract the JWT token
    token = authorization[7:].strip()  # Remove "Bearer " prefix

    if not token:
        logger.warning("UI session rejected: Empty token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Empty session token. Please login again.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    try:
        # Decode and validate JWT token
        payload = jwt.decode(
            token,
            settings.session_secret,
            algorithms=[settings.jwt_algorithm]
        )

        # Verify token type
        if payload.get("type") != "ui_session":
            logger.warning(f"UI session rejected: Invalid token type '{payload.get('type')}'")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type. Please login again."
            )

        # Extract account context
        account_id = payload.get("account_id")
        if not account_id:
            logger.warning("UI session rejected: Missing account_id in token")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token structure. Please login again."
            )

        logger.debug(f"UI session validated for account: {account_id}")
        return {"account_id": account_id}

    except jwt.ExpiredSignatureError:
        logger.warning("UI session rejected: Token expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired. Please login again."
        )
    except jwt.InvalidTokenError as e:
        logger.warning(f"UI session rejected: Invalid token - {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session token. Please login again."
        )


async def verify_jwt_or_api_key(
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db_session)
) -> dict:
    """
    Flexible authentication: accepts either JWT (UI) or API key (CRM).

    This allows a single endpoint to serve both the web UI and CRM integrations
    without code duplication.

    Returns:
        dict: Authentication context with account_id or api_key info

    Raises:
        HTTPException: 401 if neither authentication method is valid
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication. Provide either JWT token or API key.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    token = authorization[7:].strip()

    # Try JWT authentication first (starts with eyJ which is base64 encoded JSON header)
    if token.startswith("eyJ"):
        try:
            # Decode and validate JWT token
            payload = jwt.decode(
                token,
                settings.session_secret,
                algorithms=[settings.jwt_algorithm]
            )

            logger.debug(f"JWT decoded successfully. Payload: {payload}")

            if payload.get("type") == "ui_session":
                account_id = payload.get("account_id")
                if account_id:
                    logger.debug(f"Authenticated via JWT for account: {account_id}")
                    return {"account_id": account_id, "auth_type": "jwt"}
                else:
                    logger.warning("JWT validation failed: Missing account_id in token")
            else:
                logger.warning(f"JWT validation failed: Invalid token type '{payload.get('type')}'")
        except Exception as e:
            logger.warning(f"JWT validation failed: {type(e).__name__}: {str(e)}")
            pass  # Fall through to try API key

    # Try API key authentication
    db_key = await APIKeyService.validate_api_key(db, token)
    if db_key:
        logger.debug(f"Authenticated via API key: {db_key.name}")
        return {"api_key": db_key, "auth_type": "api_key"}

    # Both authentication methods failed
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication. Provide a valid JWT token or API key."
    )
