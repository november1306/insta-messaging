#!/usr/bin/env python3
"""
Test Preconditions Script

Creates a test user, ensures the @el_dmytr Instagram account exists,
and links them together. Each run creates the next testN user.

Usage:
    python scripts/preconditions.py

Can run after /reset-db or independently on an existing database.
"""

import sys
import asyncio
from pathlib import Path

# Add project root to path (find by looking for requirements.txt or .git)
current_path = Path(__file__).resolve().parent
while current_path.parent != current_path:
    if (current_path / "requirements.txt").exists() or (current_path / ".git").exists():
        project_root = current_path
        break
    current_path = current_path.parent
else:
    project_root = Path.cwd()

sys.path.insert(0, str(project_root))


def log(message, level="INFO"):
    """Print colored log message"""
    colors = {
        "INFO": "\033[0;36m",
        "SUCCESS": "\033[0;32m",
        "WARNING": "\033[0;33m",
        "ERROR": "\033[0;31m",
        "RESET": "\033[0m"
    }
    color = colors.get(level, colors["RESET"])
    reset = colors["RESET"]
    print(f"{color}[{level}]{reset} {message}")


async def run_preconditions():
    """Run seed_preconditions with a real database session."""
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from app.config import settings
    from app.db.seed import seed_preconditions, EL_DMYTR_USERNAME, EL_DMYTR_ACCOUNT_ID

    engine = create_async_engine(
        settings.database_url,
        echo=False,
        connect_args={"check_same_thread": False},
    )

    async_session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    try:
        async with async_session_maker() as session:
            result = await seed_preconditions(session, settings.session_secret)

            user = result["user"]
            account = result["account"]

            log(f"Created user: {user.username} (password: testpass)", "SUCCESS")
            log(f"Account {EL_DMYTR_USERNAME} ({EL_DMYTR_ACCOUNT_ID}) ready", "SUCCESS")
            log(f"Linked {EL_DMYTR_USERNAME} -> {user.username}", "SUCCESS")

            return True

    except Exception as e:
        log(f"Error: {e}", "ERROR")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await engine.dispose()


def main():
    print("\n" + "=" * 60)
    print("  Test Preconditions")
    print("=" * 60 + "\n")

    success = asyncio.run(run_preconditions())

    if not success:
        log("Preconditions failed", "ERROR")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("  Preconditions Complete!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
