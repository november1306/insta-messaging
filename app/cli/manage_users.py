#!/usr/bin/env python3
"""
CLI tool to manage users for UI authentication.

Usage:
    python -m app.cli.manage_users create --username admin --password SecurePass123
    python -m app.cli.manage_users create --username admin --interactive
    python -m app.cli.manage_users list
    python -m app.cli.manage_users change-password --username admin
    python -m app.cli.manage_users deactivate --username olduser
    python -m app.cli.manage_users activate --username user

Examples:
    # Create user with password
    python -m app.cli.manage_users create --username admin --password MyPassword123

    # Create user interactively (prompts for password)
    python -m app.cli.manage_users create --username admin --interactive

    # List all users
    python -m app.cli.manage_users list

    # Change password for user
    python -m app.cli.manage_users change-password --username admin

    # Deactivate a user
    python -m app.cli.manage_users deactivate --username olduser
"""
import asyncio
import argparse
import sys
import getpass
import secrets
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select
from app.db.models import Base, User
from app.services.user_service import UserService
from app.config import settings


async def create_user(username: str, password: str = None, interactive: bool = False):
    """Create a new user"""

    # Get password
    if interactive:
        print(f"Creating user '{username}'")
        password = getpass.getpass("Enter password: ")
        password_confirm = getpass.getpass("Confirm password: ")

        if password != password_confirm:
            print("[ERROR] Passwords do not match")
            return

        if len(password) < 8:
            print("[ERROR] Password must be at least 8 characters")
            return

    elif not password:
        # Generate random password
        password = secrets.token_urlsafe(16)
        print(f"ℹ️  No password provided, generating random password")

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

    # Create the user
    async with async_session_maker() as session:
        try:
            user = await UserService.create_user(
                db=session,
                username=username,
                password=password
            )

            # Display the result
            print("\n" + "="*70)
            print("[SUCCESS] User created successfully!")
            print("="*70)
            print()
            print(f"Username: {user.username}")
            if not interactive:
                print(f"Password: {password}")
                print()
                print("⚠️  SAVE THIS PASSWORD - It will not be shown again!")
            print()
            print("User Details:")
            print(f"  ID: {user.id}")
            print(f"  Username: {user.username}")
            print(f"  Active: {user.is_active}")
            print(f"  Created: {user.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            print()
            print("="*70)

        except ValueError as e:
            print(f"[ERROR] {e}")
        except Exception as e:
            print(f"[ERROR] Error creating user: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await engine.dispose()


async def list_users():
    """List all users"""

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

    async with async_session_maker() as session:
        try:
            result = await session.execute(select(User))
            users = result.scalars().all()

            if not users:
                print("No users found.")
                return

            print("\n" + "="*70)
            print("Users:")
            print("="*70)
            print()

            for user in users:
                status = "Active" if user.is_active else "Deactivated"
                print(f"  - {user.username}")
                print(f"    ID: {user.id}")
                print(f"    Status: {status}")
                print(f"    Created: {user.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
                print()

            print(f"Total users: {len(users)}")
            print("="*70)

        except Exception as e:
            print(f"[ERROR] Error listing users: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await engine.dispose()


async def change_password(username: str):
    """Change user password"""

    # Get new password
    print(f"Changing password for user '{username}'")
    new_password = getpass.getpass("Enter new password: ")
    password_confirm = getpass.getpass("Confirm new password: ")

    if new_password != password_confirm:
        print("[ERROR] Passwords do not match")
        return

    if len(new_password) < 8:
        print("[ERROR] Password must be at least 8 characters")
        return

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

    async with async_session_maker() as session:
        try:
            # Get user
            user = await UserService.get_user_by_username(session, username)

            if not user:
                print(f"[ERROR] User '{username}' not found")
                return

            # Update password
            success = await UserService.update_password(session, user.id, new_password)

            if success:
                print(f"[SUCCESS] Password updated successfully for user '{username}'")
            else:
                print(f"[ERROR] Error updating password")

        except Exception as e:
            print(f"[ERROR] {e}")
            import traceback
            traceback.print_exc()
        finally:
            await engine.dispose()


async def deactivate_user(username: str):
    """Deactivate a user"""

    # Confirm deactivation
    confirm = input(f"Deactivate user '{username}'? (yes/no): ")
    if confirm.lower() not in ['yes', 'y']:
        print("Cancelled")
        return

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

    async with async_session_maker() as session:
        try:
            # Get user
            user = await UserService.get_user_by_username(session, username)

            if not user:
                print(f"[ERROR] User '{username}' not found")
                return

            # Deactivate
            success = await UserService.deactivate_user(session, user.id)

            if success:
                print(f"[SUCCESS] User '{username}' deactivated successfully")
            else:
                print(f"[ERROR] Error deactivating user")

        except Exception as e:
            print(f"[ERROR] {e}")
            import traceback
            traceback.print_exc()
        finally:
            await engine.dispose()


async def activate_user(username: str):
    """Activate a previously deactivated user"""

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

    async with async_session_maker() as session:
        try:
            # Get user
            user = await UserService.get_user_by_username(session, username)

            if not user:
                print(f"[ERROR] User '{username}' not found")
                return

            # Activate
            success = await UserService.activate_user(session, user.id)

            if success:
                print(f"[SUCCESS] User '{username}' activated successfully")
            else:
                print(f"[ERROR] Error activating user")

        except Exception as e:
            print(f"[ERROR] {e}")
            import traceback
            traceback.print_exc()
        finally:
            await engine.dispose()


def main():
    parser = argparse.ArgumentParser(
        description='Manage users for UI authentication',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # Create user command
    create_parser = subparsers.add_parser('create', help='Create a new user')
    create_parser.add_argument('--username', required=True, help='Username for login')
    create_parser.add_argument('--password', help='Password (if not provided, will generate random)')
    create_parser.add_argument('--interactive', action='store_true', help='Prompt for password interactively')

    # List users command
    subparsers.add_parser('list', help='List all users')

    # Change password command
    change_password_parser = subparsers.add_parser('change-password', help='Change user password')
    change_password_parser.add_argument('--username', required=True, help='Username')

    # Deactivate user command
    deactivate_parser = subparsers.add_parser('deactivate', help='Deactivate a user')
    deactivate_parser.add_argument('--username', required=True, help='Username to deactivate')

    # Activate user command
    activate_parser = subparsers.add_parser('activate', help='Activate a user')
    activate_parser.add_argument('--username', required=True, help='Username to activate')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Execute command
    if args.command == 'create':
        asyncio.run(create_user(args.username, args.password, args.interactive))
    elif args.command == 'list':
        asyncio.run(list_users())
    elif args.command == 'change-password':
        asyncio.run(change_password(args.username))
    elif args.command == 'deactivate':
        asyncio.run(deactivate_user(args.username))
    elif args.command == 'activate':
        asyncio.run(activate_user(args.username))


if __name__ == '__main__':
    main()
