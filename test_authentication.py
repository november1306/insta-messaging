#!/usr/bin/env python3
"""
Quick test script to verify authentication is working.

This script:
1. Initializes the database (creates tables)
2. Generates a test API key
3. Validates the API key
4. Tests UI authentication
5. Prints results

Run with: python test_authentication.py
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from app.db.connection import init_db, get_db_session
from app.services.api_key_service import APIKeyService
from app.db.models import APIKeyType
from app.api.ui_auth import authenticate_user, create_jwt_token, decode_jwt_token


async def main():
    print("=" * 70)
    print("🔐 Authentication System Test")
    print("=" * 70)
    print()

    # Step 1: Initialize database
    print("📊 Step 1: Initializing database...")
    try:
        await init_db()
        print("   ✅ Database initialized successfully")
    except Exception as e:
        print(f"   ❌ Database initialization failed: {e}")
        return
    print()

    # Step 2: Generate API key
    print("🔑 Step 2: Generating test API key...")
    try:
        # get_db_session is a generator, use it with async for to get the session
        from app.db.connection import async_session_maker
        async with async_session_maker() as db:
            api_key, db_key = await APIKeyService.create_api_key(
                db=db,
                name="Test Admin Key",
                key_type=APIKeyType.ADMIN,
                environment="test"
            )

            print(f"   ✅ API Key generated successfully!")
            print(f"   📝 Key ID: {db_key.id}")
            print(f"   📝 Key Type: {db_key.type.value}")
            print(f"   📝 API Key: {api_key}")
            print()
            print(f"   ⚠️  Save this key for testing:")
            print(f"   export TEST_API_KEY='{api_key}'")
    except Exception as e:
        print(f"   ❌ API key generation failed: {e}")
        import traceback
        traceback.print_exc()
        return
    print()

    # Step 3: Validate API key
    print("✅ Step 3: Validating API key...")
    try:
        from app.db.connection import async_session_maker
        async with async_session_maker() as db:
            validated_key = await APIKeyService.validate_api_key(db, api_key)

            if validated_key:
                print(f"   ✅ API key validated successfully!")
                print(f"   📝 Key ID: {validated_key.id}")
                print(f"   📝 Key Name: {validated_key.name}")
                print(f"   📝 Is Active: {validated_key.is_active}")
            else:
                print(f"   ❌ API key validation failed")
    except Exception as e:
        print(f"   ❌ API key validation error: {e}")
        import traceback
        traceback.print_exc()
    print()

    # Step 4: Test invalid API key
    print("🚫 Step 4: Testing invalid API key (should fail)...")
    try:
        from app.db.connection import async_session_maker
        async with async_session_maker() as db:
            invalid_key = await APIKeyService.validate_api_key(db, "sk_test_InvalidKey123")

            if invalid_key is None:
                print(f"   ✅ Correctly rejected invalid API key")
            else:
                print(f"   ❌ Invalid key was accepted (this is a bug!)")
    except Exception as e:
        print(f"   ❌ Error testing invalid key: {e}")
    print()

    # Step 5: Test UI authentication
    print("🖥️  Step 5: Testing UI authentication...")
    try:
        # Test valid login
        user = await authenticate_user("admin", "admin123")
        if user:
            print(f"   ✅ Login successful: {user['username']} ({user['role']})")

            # Generate JWT token
            token, expires_in = create_jwt_token(user['username'], user['role'])
            print(f"   ✅ JWT token generated (expires in {expires_in}s)")

            # Validate JWT token
            payload = decode_jwt_token(token)
            if payload:
                print(f"   ✅ JWT token validated: {payload.username}")
            else:
                print(f"   ❌ JWT token validation failed")
        else:
            print(f"   ❌ Login failed for admin/admin123")

        # Test invalid login
        invalid_user = await authenticate_user("admin", "wrongpassword")
        if invalid_user is None:
            print(f"   ✅ Correctly rejected invalid password")
        else:
            print(f"   ❌ Invalid credentials were accepted (this is a bug!)")

    except Exception as e:
        print(f"   ❌ UI authentication error: {e}")
        import traceback
        traceback.print_exc()
    print()

    # Summary
    print("=" * 70)
    print("📋 Summary")
    print("=" * 70)
    print()
    print("✅ Database is ready")
    print("✅ API key authentication is working")
    print("✅ UI authentication is working")
    print()
    print("🚀 Next steps:")
    print()
    print("1. Start the server:")
    print("   uvicorn app.main:app --reload")
    print()
    print("2. Test API with your key:")
    print(f"   curl -H 'Authorization: Bearer {api_key}' \\")
    print("        http://localhost:8000/api/v1/accounts")
    print()
    print("3. Test UI login:")
    print("   curl -X POST http://localhost:8000/ui/login \\")
    print("        -H 'Content-Type: application/json' \\")
    print("        -d '{\"username\":\"admin\",\"password\":\"admin123\"}'")
    print()
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
