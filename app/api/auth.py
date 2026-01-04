"""
Authentication dependencies for CRM Integration API

Implements API key validation with database lookup and bcrypt verification.
Also provides JWT session validation for UI authentication.
Also provides user registration endpoint for master account creation.
"""
from fastapi import Header, HTTPException, status, Depends, APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from pydantic import BaseModel, Field, field_validator
import logging
import jwt
import re

from app.db.connection import get_db_session
from app.db.models import APIKey
from app.services.api_key_service import APIKeyService
from app.services.user_service import UserService
from app.config import settings

logger = logging.getLogger(__name__)

# Create router for auth endpoints
router = APIRouter()


# ============================================
# Request/Response Models
# ============================================

class RegisterRequest(BaseModel):
    """Request model for user registration"""
    username: str = Field(..., min_length=3, max_length=50, description="Username for login (3-50 characters)")
    password: str = Field(..., min_length=8, description="Password (minimum 8 characters)")

    @field_validator('username')
    @classmethod
    def validate_username(cls, v: str) -> str:
        """Validate username format (alphanumeric + underscore)"""
        if not re.match(r'^[a-zA-Z0-9_]+$', v):
            raise ValueError('Username must contain only letters, numbers, and underscores')
        return v


class RegisterResponse(BaseModel):
    """Response model for successful registration"""
    message: str
    username: str
    user_id: int


# ============================================
# Registration Endpoint
# ============================================

@router.post("/auth/register", response_model=RegisterResponse)
async def register_user(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Register a new master user account.

    This creates a master account that can link and manage multiple Instagram OAuth accounts.
    After registration, the user should login with their credentials to receive a JWT token.

    Args:
        request: Registration request with username and password
        db: Database session

    Returns:
        RegisterResponse: Success message with username and user_id

    Raises:
        HTTPException: 400 if username already exists
        HTTPException: 422 if validation fails
    """
    try:
        # Create user via UserService
        user = await UserService.create_user(
            db=db,
            username=request.username,
            password=request.password
        )

        logger.info(f"User registered successfully: {user.username} (id={user.id})")

        return RegisterResponse(
            message="Registration successful. Please login with your credentials.",
            username=user.username,
            user_id=user.id
        )

    except ValueError as e:
        # Username already exists
        logger.warning(f"Registration failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        # Unexpected error
        logger.error(f"Registration error: {type(e).__name__}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed. Please try again."
        )


# ============================================
# Authentication Dependencies
# ============================================


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

        # Extract session context (user_id, username, primary_account_id)
        user_id = payload.get("user_id")
        username = payload.get("username")
        # Support both old "account_id" and new "primary_account_id" for backward compatibility
        primary_account_id = payload.get("primary_account_id") or payload.get("account_id")

        # user_id is required, but primary_account_id may be None for new users
        if not user_id:
            logger.warning("UI session rejected: Missing user_id in token")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token structure. Please login again."
            )

        logger.debug(f"UI session validated for user: {user_id} (account: {primary_account_id})")
        return {
            "account_id": primary_account_id,  # Return as account_id for backward compatibility
            "user_id": user_id,
            "username": username
        }

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
                # Support both new "primary_account_id" and old "account_id" for backward compatibility
                account_id = payload.get("primary_account_id") or payload.get("account_id")
                user_id = payload.get("user_id")

                # Note: If account_id is missing (old token before account linking),
                # get_current_account() will handle fallback by querying the database.
                # We intentionally don't query here to keep JWT validation stateless and fast.

                if account_id:
                    logger.debug(f"Authenticated via JWT for account: {account_id}")
                    return {"account_id": account_id, "auth_type": "jwt", "user_id": user_id}
                elif user_id:
                    # User authenticated but token has no account_id (created before OAuth linking)
                    # This is acceptable - downstream handlers like get_current_account will fetch from DB
                    logger.debug(f"JWT valid for user {user_id}, but no account_id in token (will be fetched by endpoint)")
                    return {"account_id": None, "auth_type": "jwt", "user_id": user_id}
                else:
                    logger.warning("JWT validation failed: Missing user_id in token")
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
