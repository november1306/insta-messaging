"""
Migrate attachment storage from nested structure to flat structure.

OLD format: media/{channel_id}/{sender_id}/{filename}
NEW format: media/attachments/{message_id}_{index}.{ext}

Strategy:
1. Create media/attachments/ directory
2. Copy (not move) files for safety
3. Update database paths
4. Verify all attachments accessible
5. Manual cleanup of old directories after verification period

Run with --dry-run to preview changes without making them.
"""
import asyncio
import argparse
import logging
import shutil
from pathlib import Path
from typing import Dict, List, Tuple
from sqlalchemy import select, update
from app.db.connection import init_db, get_db_session
from app.db.models import MessageAttachment

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AttachmentPathMigrator:
    """Migrates attachment storage from nested to flat structure."""

    def __init__(self, base_dir: str = "media", dry_run: bool = False):
        self.base_dir = Path(base_dir)
        self.attachments_dir = self.base_dir / "attachments"
        self.dry_run = dry_run
        self.stats = {
            "total": 0,
            "migrated": 0,
            "skipped_already_new": 0,
            "skipped_missing_file": 0,
            "errors": 0
        }

    def _extract_extension(self, filename: str) -> str:
        """
        Extract file extension from filename.

        Args:
            filename: Original filename with extension

        Returns:
            Extension including dot (e.g., ".jpg"), or empty string
        """
        path = Path(filename)
        return path.suffix

    def _build_new_path(
        self,
        attachment_id: str,
        old_path: str
    ) -> Tuple[Path, Path]:
        """
        Build new attachment path.

        Args:
            attachment_id: Attachment ID (message_id_index format)
            old_path: Current local path

        Returns:
            Tuple of (old_absolute_path, new_absolute_path)
        """
        # Parse old path
        old_absolute = Path(old_path)
        if not old_absolute.is_absolute():
            old_absolute = Path.cwd() / old_path

        # Extract extension from old filename
        extension = self._extract_extension(old_path)

        # Build new path: media/attachments/{attachment_id}.{ext}
        filename = f"{attachment_id}{extension}"
        new_absolute = self.attachments_dir / filename

        return old_absolute, new_absolute

    def _is_already_new_format(self, path: str) -> bool:
        """Check if path is already in new format."""
        return path and 'attachments' in path

    async def migrate_attachments(self) -> None:
        """
        Main migration logic.

        Steps:
        1. Create attachments directory
        2. Load all attachments from database
        3. For each attachment:
           - Skip if already new format
           - Copy file to new location
           - Update database path
        4. Print summary statistics
        """
        logger.info("=" * 60)
        logger.info("Attachment Path Migration")
        logger.info("=" * 60)
        logger.info(f"Mode: {'DRY RUN (no changes)' if self.dry_run else 'LIVE (will make changes)'}")
        logger.info(f"Base directory: {self.base_dir.absolute()}")
        logger.info(f"Target directory: {self.attachments_dir.absolute()}")
        logger.info("")

        # Step 1: Create attachments directory
        if not self.dry_run:
            self.attachments_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"✅ Created directory: {self.attachments_dir}")
        else:
            logger.info(f"[DRY RUN] Would create directory: {self.attachments_dir}")

        # Step 2: Load attachments from database
        logger.info("\nLoading attachments from database...")
        await init_db()

        async for db in get_db_session():
            result = await db.execute(select(MessageAttachment))
            attachments = result.scalars().all()

            self.stats["total"] = len(attachments)
            logger.info(f"Found {self.stats['total']} attachments to process\n")

            # Step 3: Process each attachment
            for i, attachment in enumerate(attachments, 1):
                try:
                    await self._migrate_attachment(db, attachment, i)
                except Exception as e:
                    logger.error(f"❌ Error processing {attachment.id}: {e}")
                    self.stats["errors"] += 1

            # Commit database changes
            if not self.dry_run:
                await db.commit()
                logger.info("\n✅ Database changes committed")
            else:
                logger.info("\n[DRY RUN] Would commit database changes")

            break  # Only process first session

        # Step 4: Print summary
        self._print_summary()

    async def _migrate_attachment(
        self,
        db,
        attachment: MessageAttachment,
        index: int
    ) -> None:
        """
        Migrate a single attachment.

        Args:
            db: Database session
            attachment: MessageAttachment model instance
            index: Current attachment number (for progress)
        """
        attachment_id = attachment.id
        old_path = attachment.media_url_local

        logger.info(f"[{index}/{self.stats['total']}] Processing: {attachment_id}")
        logger.info(f"  Current path: {old_path}")

        # Check if already migrated
        if self._is_already_new_format(old_path):
            logger.info(f"  ⏭️  Already in new format, skipping")
            self.stats["skipped_already_new"] += 1
            return

        # Build new path
        old_absolute, new_absolute = self._build_new_path(attachment_id, old_path)

        # Check if source file exists
        if not old_absolute.exists():
            logger.warning(f"  ⚠️  Source file not found: {old_absolute}")
            self.stats["skipped_missing_file"] += 1
            return

        # Calculate new relative path (from project root)
        # Convert absolute path to relative: C:\workspace\insta-auto\media\attachments\file.jpg -> media/attachments/file.jpg
        try:
            cwd = Path.cwd()
            new_relative_path = new_absolute.relative_to(cwd)
            new_relative = str(new_relative_path).replace("\\", "/")
        except ValueError:
            # If path is not relative to cwd, construct manually
            new_relative = str(new_absolute).replace(str(cwd) + "\\", "").replace("\\", "/")

        # Copy file to new location
        if not self.dry_run:
            try:
                shutil.copy2(old_absolute, new_absolute)
                logger.info(f"  ✅ Copied file: {old_absolute} -> {new_absolute}")
            except Exception as e:
                logger.error(f"  ❌ Copy failed: {e}")
                self.stats["errors"] += 1
                return
        else:
            logger.info(f"  [DRY RUN] Would copy: {old_absolute} -> {new_absolute}")

        # Update database
        if not self.dry_run:
            await db.execute(
                update(MessageAttachment)
                .where(MessageAttachment.id == attachment_id)
                .values(media_url_local=new_relative)
            )
            logger.info(f"  ✅ Updated database path to: {new_relative}")
        else:
            logger.info(f"  [DRY RUN] Would update database path to: {new_relative}")

        self.stats["migrated"] += 1

    def _print_summary(self) -> None:
        """Print migration summary statistics."""
        logger.info("\n" + "=" * 60)
        logger.info("Migration Summary")
        logger.info("=" * 60)
        logger.info(f"Total attachments: {self.stats['total']}")
        logger.info(f"Migrated: {self.stats['migrated']}")
        logger.info(f"Already new format: {self.stats['skipped_already_new']}")
        logger.info(f"Missing files: {self.stats['skipped_missing_file']}")
        logger.info(f"Errors: {self.stats['errors']}")
        logger.info("=" * 60)

        if self.dry_run:
            logger.info("\n⚠️  DRY RUN MODE - No changes were made")
            logger.info("Run without --dry-run to apply changes")
        else:
            logger.info("\n✅ Migration complete!")
            logger.info("\nNext steps:")
            logger.info("1. Verify attachments are accessible in UI")
            logger.info("2. Keep old files for 1 week as backup")
            logger.info("3. Delete old media directories after verification:")
            logger.info("   - media/17841405728832526/")
            logger.info("   - media/17841478096518771/")
            logger.info("   - media/24370771369265571/")
            logger.info("   - media/outbound/")


async def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Migrate attachment storage to flat structure"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without making them"
    )
    parser.add_argument(
        "--base-dir",
        default="media",
        help="Base media directory (default: media)"
    )
    args = parser.parse_args()

    migrator = AttachmentPathMigrator(
        base_dir=args.base_dir,
        dry_run=args.dry_run
    )

    await migrator.migrate_attachments()


if __name__ == "__main__":
    asyncio.run(main())
