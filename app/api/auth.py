"""
Authentication dependencies for CRM Integration API

This is a STUB implementation for MVP development.
TODO: Replace with real API key validation from database 
      (see .kiro/specs/crm-integration/tasks.md - Priority 2, Task 10)

WARNING: This stub accepts ANY Bearer token. Do not deploy to production.

Expected environment variable: ENVIRONMENT = "development" | "staging" | "production" | "prod"
Must be set in .env or deployment config. Defaults to "development" if unset.
"""
from fastapi import Header, HTTPException, status
from typing import Optional
import logging
import os

logger = logging.getLogger(__name__)

# Prevent accidental production deployment with stub auth
# This check runs at module import time to fail fast on startup
_ENV = os.getenv("ENVIRONMENT", "development").lower()
if _ENV in ("production", "prod"):
    raise RuntimeError(
        "Stub authentication module cannot be imported in production environment. "
        "Implement real API key validation (Priority 2, Task 10) before deploying."
    )


def verify_api_key(
    authorization: Optional[str] = Header(None)
) -> str:
    """
    Stub authentication for MVP - use "Bearer test_key" or any non-empty Bearer token.
    
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
    
    # STUB: Accept any non-empty key for now
    if not api_key:
        logger.warning("API request rejected: Empty API key")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Empty API key. Provide a valid API key after 'Bearer '.",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Return the key (in real implementation, would return APIKey object with permissions)
    return api_key
