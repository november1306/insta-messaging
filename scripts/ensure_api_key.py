#!/usr/bin/env python3
"""
Ensure the VITE_API_KEY from .env exists in the database.
This script is idempotent - it will create the key if it doesn't exist,
or do nothing if it already exists.
"""
import os
import sys
import asyncio
from pathlib import Path

# Add app directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.connection import get_db_session, init_db
from app.services.api_key_service import APIKeyService
from app.db.models import APIKeyType


async def ensure_api_key():
    """Ensure the VITE_API_KEY from .env exists in the database."""
    # Initialize database
    await init_db()

    # Read VITE_API_KEY from environment
    api_key = os.getenv("VITE_API_KEY")

    if not api_key:
        print("❌ VITE_API_KEY not found in environment")
        sys.exit(1)

    if not api_key.startswith("sk_test_") and not api_key.startswith("sk_live_"):
        print(f"❌ Invalid API key format: {api_key}")
        sys.exit(1)

    # Extract prefix (first 10 characters for quick lookup)
    key_prefix = api_key[:10]  # e.g., "sk_test_yl"

    print(f"🔑 Checking if API key with prefix '{key_prefix}' exists in database...")

    # Check if key already exists
    async for db in get_db_session():
        existing_key = await APIKeyService.validate_api_key(db, api_key)

        if existing_key:
            print(f"✅ API key already exists in database (ID: {existing_key.id})")
            return

        # Key doesn't exist, create it
        print(f"📝 API key not found, creating it...")

        # Create the API key using the service
        # We need to use a different approach since we have the raw key
        import bcrypt
        from app.db.models import APIKey as APIKeyModel
        from sqlalchemy import select
        import secrets

        # Check if a key with this prefix exists
        result = await db.execute(
            select(APIKeyModel).where(APIKeyModel.key_prefix == key_prefix)
        )
        existing = result.scalar_one_or_none()

        if existing:
            print(f"✅ API key with prefix '{key_prefix}' already exists (ID: {existing.id})")
            return

        # Create new API key
        key_hash = bcrypt.hashpw(api_key.encode(), bcrypt.gensalt()).decode()

        new_key = APIKeyModel(
            id=f"key_{secrets.token_hex(8)}",
            name="Frontend Chat UI",
            key_prefix=key_prefix,
            key_hash=key_hash,
            type=APIKeyType.ADMIN,
            is_active=True
        )

        db.add(new_key)
        await db.commit()
        await db.refresh(new_key)

        print(f"✅ Created API key in database (ID: {new_key.id}, prefix: {key_prefix})")
        print(f"   Name: {new_key.name}")
        print(f"   Type: {new_key.type}")
        break


if __name__ == "__main__":
    asyncio.run(ensure_api_key())
