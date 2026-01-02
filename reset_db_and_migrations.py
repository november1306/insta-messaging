#!/usr/bin/env python3
"""
Database Reset and Migration Script

Detects fresh deployments and recreates the database from scratch using the
baseline migration. Safe for both development and production environments.

Usage:
    python reset_db_and_migrations.py [--force] [--no-backup]

Options:
    --force      Skip confirmation prompt (use in automated deployments)
    --no-backup  Don't create backup of existing database
"""

import os
import sys
import shutil
import argparse
from pathlib import Path
from datetime import datetime
import subprocess


class DatabaseResetter:
    """Handles database reset and migration operations"""

    def __init__(self, force=False, no_backup=False):
        self.force = force
        self.no_backup = no_backup
        self.project_root = Path(__file__).parent
        self.env_file = self.project_root / ".env"
        self.db_path = None
        self.backup_path = None

    def log(self, message, level="INFO"):
        """Print colored log message"""
        colors = {
            "INFO": "\033[0;36m",    # Cyan
            "SUCCESS": "\033[0;32m", # Green
            "WARNING": "\033[1;33m", # Yellow
            "ERROR": "\033[0;31m",   # Red
            "RESET": "\033[0m"       # Reset
        }
        color = colors.get(level, colors["RESET"])
        reset = colors["RESET"]
        print(f"{color}[{level}]{reset} {message}")

    def load_env(self):
        """Load DATABASE_URL from .env file"""
        if not self.env_file.exists():
            self.log(".env file not found, using default database path", "WARNING")
            return "sqlite+aiosqlite:///./instagram_automation.db"

        with open(self.env_file, "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith("DATABASE_URL="):
                    return line.split("=", 1)[1].strip()

        self.log("DATABASE_URL not found in .env, using default", "WARNING")
        return "sqlite+aiosqlite:///./instagram_automation.db"

    def parse_database_path(self, database_url):
        """Extract file path from DATABASE_URL"""
        # Handle sqlite+aiosqlite:///./path/to/db.db
        if database_url.startswith("sqlite+aiosqlite:///"):
            path = database_url.replace("sqlite+aiosqlite:///", "")
            # Remove leading ./ if present
            if path.startswith("./"):
                path = path[2:]
            return self.project_root / path
        else:
            self.log(f"Unsupported DATABASE_URL format: {database_url}", "ERROR")
            self.log("This script only supports SQLite databases", "ERROR")
            sys.exit(1)

    def is_fresh_deployment(self):
        """Detect if this is a fresh deployment"""
        # Consider it fresh if:
        # 1. Database doesn't exist
        # 2. Database exists but is empty (< 1KB)
        # 3. --force flag is used

        if self.force:
            self.log("Force mode enabled - treating as fresh deployment", "INFO")
            return True

        if not self.db_path.exists():
            self.log("No existing database found - fresh deployment detected", "INFO")
            return True

        db_size = self.db_path.stat().st_size
        if db_size < 1024:  # Less than 1KB
            self.log(f"Database exists but is empty ({db_size} bytes) - treating as fresh", "INFO")
            return True

        self.log(f"Existing database found: {self.db_path} ({db_size / 1024:.1f} KB)", "WARNING")
        return False

    def backup_database(self):
        """Create backup of existing database"""
        if not self.db_path.exists():
            self.log("No database to backup", "INFO")
            return

        if self.no_backup:
            self.log("Skipping backup (--no-backup flag)", "WARNING")
            return

        # Create backup filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.backup_path = self.db_path.parent / f"{self.db_path.name}.backup.{timestamp}"

        try:
            shutil.copy2(self.db_path, self.backup_path)
            self.log(f"Backup created: {self.backup_path}", "SUCCESS")
        except Exception as e:
            self.log(f"Failed to create backup: {e}", "ERROR")
            if not self.force:
                self.log("Aborting to prevent data loss", "ERROR")
                sys.exit(1)

    def delete_database(self):
        """Delete existing database file"""
        if not self.db_path.exists():
            self.log("No database to delete", "INFO")
            return

        try:
            self.db_path.unlink()
            self.log(f"Deleted database: {self.db_path}", "SUCCESS")
        except Exception as e:
            self.log(f"Failed to delete database: {e}", "ERROR")
            sys.exit(1)

    def run_migrations(self):
        """Run Alembic migrations to create fresh database"""
        self.log("Running database migrations from baseline...", "INFO")

        try:
            # Run alembic upgrade head
            result = subprocess.run(
                ["alembic", "upgrade", "head"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                check=True
            )

            # Print alembic output
            if result.stdout:
                for line in result.stdout.strip().split("\n"):
                    if line.strip():
                        print(f"  {line}")

            self.log("Database created successfully from baseline migration", "SUCCESS")

        except subprocess.CalledProcessError as e:
            self.log("Migration failed!", "ERROR")
            if e.stdout:
                print(e.stdout)
            if e.stderr:
                print(e.stderr)
            sys.exit(1)
        except FileNotFoundError:
            self.log("Alembic not found. Make sure you're in the virtual environment.", "ERROR")
            self.log("Run: source venv/bin/activate  (Linux) or .\\venv\\Scripts\\activate (Windows)", "ERROR")
            sys.exit(1)

    def confirm_reset(self):
        """Ask user for confirmation before resetting"""
        if self.force:
            return True

        print("\n" + "=" * 60)
        print("  DATABASE RESET CONFIRMATION")
        print("=" * 60)
        print(f"\nDatabase: {self.db_path}")
        print(f"Backup:   {'Yes' if not self.no_backup else 'No (--no-backup)'}")
        print("\n⚠️  WARNING: This will DELETE all existing data!")
        print("=" * 60 + "\n")

        response = input("Type 'yes' to continue: ").strip().lower()
        return response == "yes"

    def run(self):
        """Main execution flow"""
        print("\n" + "=" * 60)
        print("  Database Reset and Migration Script")
        print("=" * 60 + "\n")

        # Step 1: Load database configuration
        self.log("Loading database configuration...", "INFO")
        database_url = self.load_env()
        self.db_path = self.parse_database_path(database_url)
        self.log(f"Database path: {self.db_path}", "INFO")

        # Step 2: Detect deployment type
        is_fresh = self.is_fresh_deployment()

        # Step 3: Confirm if not fresh and not forced
        if not is_fresh or (self.db_path.exists() and not self.force):
            if not self.confirm_reset():
                self.log("Operation cancelled by user", "WARNING")
                sys.exit(0)

        # Step 4: Backup existing database
        if self.db_path.exists():
            self.backup_database()

        # Step 5: Delete database
        self.delete_database()

        # Step 6: Run migrations
        self.run_migrations()

        # Step 7: Summary
        print("\n" + "=" * 60)
        print("  Database Reset Complete!")
        print("=" * 60)
        print("\nNext steps:")
        print("  1. Create admin user:")
        print("     python -m app.cli.manage_users")
        print("\n  2. Generate API keys:")
        print("     python -m app.cli.generate_api_key --name 'Admin Key' --type admin")
        print("\n  3. Start the application:")
        print("     scripts/linux/start.sh  (or scripts/win/start.bat)")

        if self.backup_path:
            print(f"\nBackup saved to: {self.backup_path}")
            print(f"To restore: mv {self.backup_path} {self.db_path}")

        print("\n" + "=" * 60 + "\n")


def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Reset database and run migrations from baseline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode (asks for confirmation):
  python reset_db_and_migrations.py

  # Force reset (no confirmation, useful for CI/CD):
  python reset_db_and_migrations.py --force

  # Reset without backup (faster, but less safe):
  python reset_db_and_migrations.py --force --no-backup
        """
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompt (for automated deployments)"
    )

    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Don't create backup of existing database"
    )

    args = parser.parse_args()

    resetter = DatabaseResetter(force=args.force, no_backup=args.no_backup)
    resetter.run()


if __name__ == "__main__":
    main()
