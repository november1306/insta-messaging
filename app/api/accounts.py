"""
CRM Integration API - Account Management Endpoints

Implements account configuration for Instagram business accounts.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
import uuid
import logging
import base64

from app.api.auth import verify_api_key
from app.db.connection import get_db_session
from app.db.models import Account

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================
# Pydantic Models (from OpenAPI spec)
# ============================================

class CreateAccountRequest(BaseModel):
    """Request to create a new Instagram account configuration"""
    instagram_account_id: str = Field(..., description="Instagram business account ID")
    username: str = Field(..., description="Instagram username")
    access_token: str = Field(..., description="Instagram Page Access Token")
    crm_webhook_url: str = Field(..., description="CRM endpoint for webhooks")
    webhook_secret: str = Field(..., description="Shared secret for webhook signatures")


class AccountResponse(BaseModel):
    """Account details response (credentials excluded)"""
    account_id: str
    instagram_account_id: str
    username: str
    crm_webhook_url: str
    created_at: datetime
    
    class Config:
        from_attributes = True


# ============================================
# Simple Encryption (MVP - replace later)
# ============================================
# WARNING: This is NOT real encryption - just base64 encoding!
# Anyone with database access can decode these credentials.
# TODO: Replace with cryptography.fernet in Priority 2 (Task 10)

def encrypt_credential(credential: str) -> str:
    """
    Simple encoding for MVP - just base64 for now.
    
    WARNING: This is NOT secure encryption. Do not use in production.
    TODO: Replace with real encryption (Fernet) in Priority 2.
    """
    return base64.b64encode(credential.encode()).decode()


# ============================================
# Endpoints
# ============================================

@router.post("/accounts", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
async def create_account(
    request: CreateAccountRequest,
    api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Create a new Instagram account configuration.
    
    Minimal implementation for MVP:
    - Store account with encoded credentials (NOT secure - see warning)
    - Skip Instagram token validation (will add in Priority 2)
    - Return 201 with account_id
    
    WARNING: Credentials are base64-encoded, NOT encrypted. 
    Do not use in production without implementing real encryption (Task 10).
    """
    logger.info(f"Creating account for Instagram user: {request.username}")
    
    # Check if account already exists
    result = await db.execute(
        select(Account).where(Account.instagram_account_id == request.instagram_account_id)
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        logger.warning(f"Account already exists: {request.instagram_account_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Account with instagram_account_id '{request.instagram_account_id}' already exists"
        )
    
    # Generate account ID
    account_id = f"acc_{uuid.uuid4().hex[:12]}"
    
    # Encode credentials (NOT secure - just base64 for MVP)
    encoded_token = encrypt_credential(request.access_token)
    encoded_webhook_secret = encrypt_credential(request.webhook_secret)
    
    # Create account record
    account = Account(
        id=account_id,
        instagram_account_id=request.instagram_account_id,
        username=request.username,
        access_token_encrypted=encoded_token,
        crm_webhook_url=request.crm_webhook_url,
        webhook_secret=encoded_webhook_secret,
        created_at=datetime.utcnow()  # Set explicitly for MVP
    )
    
    try:
        db.add(account)
        await db.commit()
    except Exception as e:
        logger.error(f"Database error creating account: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create account: {str(e)}"
        )
    
    logger.info(f"Account created: {account_id} (@{request.username})")
    
    return AccountResponse(
        account_id=account.id,
        instagram_account_id=account.instagram_account_id,
        username=account.username,
        crm_webhook_url=account.crm_webhook_url,
        created_at=account.created_at
    )
