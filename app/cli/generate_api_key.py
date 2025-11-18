#!/usr/bin/env python3
"""
CLI tool to generate API keys for CRM integration.

Usage:
    python -m app.cli.generate_api_key --name "My API Key" --type admin --env test
    python -m app.cli.generate_api_key --name "Account Key" --type account --env live --accounts acc_123,acc_456

Examples:
    # Generate admin key for testing
    python -m app.cli.generate_api_key --name "Development Admin" --type admin --env test

    # Generate production admin key
    python -m app.cli.generate_api_key --name "Production Admin" --type admin --env live

    # Generate account-scoped key
    python -m app.cli.generate_api_key --name "Customer A Integration" --type account --accounts acc_abc123
"""
import asyncio
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.db.models import Base, APIKeyType
from app.services.api_key_service import APIKeyService
from app.config import settings


async def generate_key(
    name: str,
    key_type: str,
    environment: str,
    account_ids: list[str] = None,
    expires_days: int = None
):
    """Generate a new API key"""

    # Validate key type
    try:
        api_key_type = APIKeyType[key_type.upper()]
    except KeyError:
        print(f"❌ Error: Invalid key type '{key_type}'. Must be 'admin' or 'account'")
        return

    # Validate environment
    if environment not in ['test', 'live']:
        print(f"❌ Error: Invalid environment '{environment}'. Must be 'test' or 'live'")
        return

    # Validate account IDs for account-scoped keys
    if api_key_type == APIKeyType.ACCOUNT and not account_ids:
        print("❌ Error: Account-scoped keys require --accounts parameter")
        return

    # Calculate expiration
    expires_at = None
    if expires_days:
        from datetime import timedelta
        expires_at = datetime.now(timezone.utc) + timedelta(days=expires_days)

    # Initialize database
    database_url = settings.database_url
    engine = create_async_engine(
        database_url,
        echo=False,
        connect_args={"check_same_thread": False},
    )

    async_session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # Create tables if they don't exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Generate the key
    async with async_session_maker() as session:
        try:
            api_key, db_key = await APIKeyService.create_api_key(
                db=session,
                name=name,
                key_type=api_key_type,
                environment=environment,
                account_ids=account_ids,
                expires_at=expires_at
            )

            # Display the result
            print("\n" + "="*70)
            print("✅ API Key created successfully!")
            print("="*70)
            print()
            print(f"API Key: {api_key}")
            print()
            print("⚠️  SAVE THIS KEY - It will not be shown again!")
            print()
            print("Key Details:")
            print(f"  • ID: {db_key.id}")
            print(f"  • Name: {db_key.name}")
            print(f"  • Type: {db_key.type.value}")
            print(f"  • Environment: {environment}")
            print(f"  • Created: {db_key.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")

            if expires_at:
                print(f"  • Expires: {expires_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")

            if account_ids:
                print(f"  • Permitted Accounts: {', '.join(account_ids)}")

            print()
            print("Usage Example:")
            print(f"  curl -H 'Authorization: Bearer {api_key}' \\")
            print(f"       http://localhost:8000/api/v1/messages/send")
            print()
            print("="*70)

        except Exception as e:
            print(f"❌ Error creating API key: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await engine.dispose()


def main():
    parser = argparse.ArgumentParser(
        description='Generate API keys for CRM integration',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate admin key for testing
  %(prog)s --name "Development Admin" --type admin --env test

  # Generate production admin key with 90-day expiration
  %(prog)s --name "Production Admin" --type admin --env live --expires 90

  # Generate account-scoped key for specific accounts
  %(prog)s --name "Customer A" --type account --env live --accounts acc_123,acc_456
        """
    )

    parser.add_argument(
        '--name',
        required=True,
        help='Descriptive name for the API key'
    )

    parser.add_argument(
        '--type',
        required=True,
        choices=['admin', 'account'],
        help='Key type: admin (full access) or account (limited to specific accounts)'
    )

    parser.add_argument(
        '--env',
        '--environment',
        dest='environment',
        required=True,
        choices=['test', 'live'],
        help='Environment: test or live'
    )

    parser.add_argument(
        '--accounts',
        help='Comma-separated list of account IDs (required for account-scoped keys)'
    )

    parser.add_argument(
        '--expires',
        type=int,
        metavar='DAYS',
        help='Expiration in days (optional, default: no expiration)'
    )

    args = parser.parse_args()

    # Parse account IDs
    account_ids = None
    if args.accounts:
        account_ids = [acc.strip() for acc in args.accounts.split(',')]

    # Run the async function
    asyncio.run(generate_key(
        name=args.name,
        key_type=args.type,
        environment=args.environment,
        account_ids=account_ids,
        expires_days=args.expires
    ))


if __name__ == '__main__':
    main()
