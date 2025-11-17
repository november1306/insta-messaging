"""
UI Authentication - Simple hardcoded credentials with JWT tokens.

This is a simple authentication system for the web chat UI.
Uses hardcoded credentials (bcrypt hashed) and JWT tokens for session management.

For production, replace with proper user management system or OAuth.
"""
from fastapi import HTTPException, status, Depends, Header
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone
from typing import Optional
import bcrypt
import jwt
import os
import logging

logger = logging.getLogger(__name__)

# JWT Configuration
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production-12345")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24


# ============================================
# Hardcoded Users (MVP - Replace with DB later)
# ============================================

# Passwords are pre-hashed with bcrypt for security
# To add new users, generate hash with: bcrypt.hashpw("password".encode(), bcrypt.gensalt())
HARDCODED_USERS = {
    "admin": {
        "password_hash": "$2b$12$Dih5efRthforbcBOnewDsuQkAkWQipG0snJmNElF4Q6juJqZ5LP9q",  # "admin123"
        "role": "admin",
        "display_name": "Administrator"
    },
    "demo": {
        "password_hash": "$2b$12$/oII2hpemHIg0ir/FsbMAuy46zpe227j/kpniUq3OJKB2c6wEHOKq",  # "demo123"
        "role": "viewer",
        "display_name": "Demo User"
    }
}


# ============================================
# Pydantic Models
# ============================================

class LoginRequest(BaseModel):
    """Login request payload"""
    username: str
    password: str


class LoginResponse(BaseModel):
    """Login response with JWT token"""
    token: str
    expires_in: int  # seconds
    username: str
    role: str
    display_name: str


class TokenPayload(BaseModel):
    """JWT token payload"""
    username: str
    role: str
    exp: datetime  # expiration


# ============================================
# Authentication Functions
# ============================================

def verify_password(plain_password: str, password_hash: str) -> bool:
    """
    Verify a password against a bcrypt hash.

    Args:
        plain_password: Plain text password
        password_hash: bcrypt hash

    Returns:
        True if password matches
    """
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), password_hash.encode('utf-8'))
    except Exception as e:
        logger.error(f"Error verifying password: {e}")
        return False


def create_jwt_token(username: str, role: str) -> tuple[str, int]:
    """
    Create a JWT token for a user.

    Args:
        username: Username
        role: User role

    Returns:
        Tuple of (token, expires_in_seconds)
    """
    expires_at = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)
    expires_in = JWT_EXPIRATION_HOURS * 3600

    payload = {
        "username": username,
        "role": role,
        "exp": expires_at
    }

    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

    return token, expires_in


def decode_jwt_token(token: str) -> Optional[TokenPayload]:
    """
    Decode and validate a JWT token.

    Args:
        token: JWT token string

    Returns:
        TokenPayload if valid, None if invalid/expired
    """
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return TokenPayload(**payload)
    except jwt.ExpiredSignatureError:
        logger.warning("JWT token has expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid JWT token: {e}")
        return None


async def authenticate_user(username: str, password: str) -> Optional[dict]:
    """
    Authenticate a user with username and password.

    Args:
        username: Username
        password: Plain text password

    Returns:
        User dict if authenticated, None otherwise
    """
    user = HARDCODED_USERS.get(username)

    if not user:
        logger.warning(f"Login attempt for non-existent user: {username}")
        return None

    if not verify_password(password, user["password_hash"]):
        logger.warning(f"Invalid password for user: {username}")
        return None

    logger.info(f"User authenticated: {username}")
    return {
        "username": username,
        "role": user["role"],
        "display_name": user["display_name"]
    }


# ============================================
# FastAPI Dependencies
# ============================================

async def verify_ui_token(authorization: Optional[str] = Header(None)) -> TokenPayload:
    """
    Verify JWT token from Authorization header for UI access.

    Args:
        authorization: Authorization header (Bearer token)

    Returns:
        TokenPayload if valid

    Raises:
        HTTPException: 401 if token is missing or invalid
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header. Use 'Bearer <token>'.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    token = authorization[7:].strip()  # Remove "Bearer " prefix

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Empty token",
            headers={"WWW-Authenticate": "Bearer"}
        )

    payload = decode_jwt_token(token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"}
        )

    return payload


# ============================================
# Password Hash Generator (for adding new users)
# ============================================

def generate_password_hash(password: str) -> str:
    """
    Generate bcrypt hash for a password.
    Use this to add new hardcoded users.

    Args:
        password: Plain text password

    Returns:
        bcrypt hash string
    """
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


# Example usage (for development):
# if __name__ == "__main__":
#     print(f"admin123: {generate_password_hash('admin123')}")
#     print(f"demo123: {generate_password_hash('demo123')}")
