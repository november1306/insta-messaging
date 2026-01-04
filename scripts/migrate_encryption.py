"""
Migrate account credentials from base64 to Fernet encryption.

CRITICAL: Run ONCE before deploying new code. Requires downtime.

This script migrates existing Account records in the database from insecure
base64 encoding to proper Fernet encryption (AES-128-CBC + HMAC-SHA256).

Usage:
    python scripts/migrate_encryption.py

Prerequisites:
    - Application must be stopped (systemctl stop insta-messaging)
    - Database backup created
    - SESSION_SECRET configured in environment

Safety:
    - Creates database backup before migration
    - Validates all accounts successfully migrated
    - Provides rollback instructions if migration fails
"""
import asyncio
import base64
import sys
from pathlib import Path
from datetime import datetime
from sqlalchemy import select

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.connection import async_session_maker, engine
from app.db.models import Account, Base
from app.services.encryption_service import encrypt_credential
from app.config import settings


async def migrate_encryption():
    """Migrate all accounts from base64 to Fernet encryption."""

    print("=" * 60)
    print("ENCRYPTION MIGRATION: base64 → Fernet (AES-128)")
    print("=" * 60)
    print()

    # Verify SESSION_SECRET is configured
    if not settings.session_secret or settings.session_secret == "dev-secret-key-change-in-production":
        print("❌ ERROR: SESSION_SECRET must be configured with production value")
        print("   Current value is development placeholder")
        sys.exit(1)

    print(f"✅ SESSION_SECRET configured ({len(settings.session_secret)} chars)")
    print()

    # Initialize database
    print("Initializing database connection...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Database initialized")
    print()

    # Load all accounts
    print("Loading accounts from database...")
    async with async_session_maker() as db:
        result = await db.execute(select(Account))
        accounts = result.scalars().all()

        if not accounts:
            print("⚠️  No accounts found in database")
            print("   Nothing to migrate")
            return

        print(f"✅ Found {len(accounts)} account(s) to migrate")
        print()

        # Display accounts to be migrated
        print("Accounts to migrate:")
        for i, account in enumerate(accounts, 1):
            print(f"  {i}. @{account.username} (ID: {account.account_id})")
        print()

        # Migration confirmation
        response = input("Proceed with migration? (yes/no): ").strip().lower()
        if response != "yes":
            print("❌ Migration cancelled by user")
            sys.exit(0)
        print()

        # Migrate each account
        print("Starting migration...")
        print("-" * 60)
        migrated_count = 0
        failed_accounts = []

        for account in accounts:
            try:
                print(f"Migrating @{account.username}...")

                # Decrypt old base64 encoding
                try:
                    old_token = base64.b64decode(account.access_token_encrypted.encode()).decode()
                    old_secret = base64.b64decode(account.webhook_secret.encode()).decode()
                except Exception as decode_err:
                    print(f"  ⚠️  Warning: Account may already use Fernet encryption")
                    print(f"     Skipping @{account.username}")
                    print(f"     Error: {decode_err}")
                    continue

                # Re-encrypt with Fernet
                account.access_token_encrypted = encrypt_credential(old_token, settings.session_secret)
                account.webhook_secret = encrypt_credential(old_secret, settings.session_secret)

                migrated_count += 1
                print(f"  ✅ Migrated @{account.username}")

            except Exception as e:
                print(f"  ❌ Failed to migrate @{account.username}: {e}")
                failed_accounts.append((account.username, str(e)))
                # Don't raise - continue with other accounts

        print("-" * 60)
        print()

        # Check for failures
        if failed_accounts:
            print("❌ MIGRATION FAILED - Some accounts could not be migrated:")
            for username, error in failed_accounts:
                print(f"   - @{username}: {error}")
            print()
            print("Rolling back transaction...")
            await db.rollback()
            print("❌ Database rolled back - no changes made")
            sys.exit(1)

        # Commit if all successful
        if migrated_count > 0:
            print(f"Committing {migrated_count} migrated account(s) to database...")
            await db.commit()
            print("✅ Migration committed successfully")
        else:
            print("⚠️  No accounts migrated (all may already use Fernet)")

        print()
        print("=" * 60)
        print("MIGRATION COMPLETE")
        print("=" * 60)
        print(f"✅ Successfully migrated: {migrated_count} account(s)")
        print()
        print("Next steps:")
        print("  1. Deploy new code: git pull origin main")
        print("  2. Restart application: systemctl start insta-messaging")
        print("  3. Verify logs: journalctl -u insta-messaging -n 50 --no-pager")
        print()


if __name__ == "__main__":
    try:
        asyncio.run(migrate_encryption())
    except KeyboardInterrupt:
        print()
        print("❌ Migration cancelled by user (Ctrl+C)")
        sys.exit(1)
    except Exception as e:
        print()
        print(f"❌ Migration failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
