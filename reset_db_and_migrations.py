#!/usr/bin/env python3
"""
Database Reset Script - Deletes database and runs migrations from scratch.

Usage:
    python reset_db_and_migrations.py
"""

import sys
import subprocess
from pathlib import Path


def log(message, level="INFO"):
    """Print colored log message"""
    colors = {
        "INFO": "\033[0;36m",
        "SUCCESS": "\033[0;32m",
        "ERROR": "\033[0;31m",
        "RESET": "\033[0m"
    }
    color = colors.get(level, colors["RESET"])
    reset = colors["RESET"]
    print(f"{color}[{level}]{reset} {message}")


def get_database_path():
    """Get database path from .env or use default"""
    project_root = Path(__file__).parent
    env_file = project_root / ".env"

    database_url = "sqlite+aiosqlite:///./instagram_automation.db"

    if env_file.exists():
        with open(env_file, "r") as f:
            for line in f:
                if line.strip().startswith("DATABASE_URL="):
                    database_url = line.split("=", 1)[1].strip()
                    break

    # Parse SQLite path from URL
    if database_url.startswith("sqlite+aiosqlite:///"):
        path = database_url.replace("sqlite+aiosqlite:///", "")
        if path.startswith("./"):
            path = path[2:]
        return project_root / path
    else:
        log(f"Unsupported DATABASE_URL: {database_url}", "ERROR")
        sys.exit(1)


def main():
    project_root = Path(__file__).parent

    print("\n" + "=" * 60)
    print("  Database Reset")
    print("=" * 60 + "\n")

    # Get database path
    db_path = get_database_path()
    log(f"Database: {db_path}", "INFO")

    # Delete database if exists
    if db_path.exists():
        db_path.unlink()
        log("Database deleted", "SUCCESS")
    else:
        log("No existing database found", "INFO")

    # Initialize database schema from models
    log("Creating tables from models...", "INFO")
    try:
        result = subprocess.run(
            [sys.executable, "-c", "import asyncio; from app.db.connection import init_db; asyncio.run(init_db())"],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=True
        )
        log("Tables created successfully", "SUCCESS")
    except subprocess.CalledProcessError as e:
        log("Table creation failed!", "ERROR")
        if e.stdout:
            print(e.stdout)
        if e.stderr:
            print(e.stderr)
        sys.exit(1)

    # Run migrations
    log("Running migrations...", "INFO")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=True
        )
        if result.stdout:
            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    print(f"  {line}")

        log("Database initialized successfully", "SUCCESS")

    except subprocess.CalledProcessError as e:
        log("Migration failed!", "ERROR")
        if e.stdout:
            print(e.stdout)
        if e.stderr:
            print(e.stderr)
        sys.exit(1)
    except FileNotFoundError:
        log("Alembic not found. Activate virtual environment first.", "ERROR")
        sys.exit(1)

    print("\n" + "=" * 60 + "\n")


if __name__ == "__main__":
    main()
