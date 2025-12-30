"""
Cleanup orphaned attachment records from database.

Finds attachment records in the database where the local file doesn't exist
and removes them to prevent 404 errors in the UI.

Run with --dry-run to preview changes without making them.
"""
import asyncio
import argparse
import logging
from pathlib import Path
from sqlalchemy import select, delete
from app.db.connection import init_db, get_db_session
from app.db.models import MessageAttachment

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AttachmentCleaner:
    """Removes orphaned attachment records from database."""

    def __init__(self, base_dir: str = "/opt/insta-messaging", dry_run: bool = False):
        self.base_dir = Path(base_dir)
        self.dry_run = dry_run
        self.stats = {
            "total": 0,
            "exists": 0,
            "missing": 0,
            "deleted": 0,
            "errors": 0
        }

    def _get_absolute_path(self, media_path: str) -> Path:
        """
        Convert relative media path to absolute path.

        Args:
            media_path: Relative path like "media/attachments/file.jpg"

        Returns:
            Absolute path on the system
        """
        # Remove leading slash if present
        if media_path.startswith('/'):
            media_path = media_path[1:]

        # Build absolute path
        return self.base_dir / media_path

    async def cleanup_orphaned_attachments(self) -> None:
        """
        Main cleanup logic.

        Steps:
        1. Load all attachments from database
        2. For each attachment:
           - Check if file exists on disk
           - If missing, delete the record
        3. Print summary statistics
        """
        logger.info("=" * 60)
        logger.info("Orphaned Attachment Cleanup")
        logger.info("=" * 60)
        logger.info(f"Mode: {'DRY RUN (no changes)' if self.dry_run else 'LIVE (will make changes)'}")
        logger.info(f"Base directory: {self.base_dir}")
        logger.info("")

        # Load attachments from database
        logger.info("Loading attachments from database...")
        await init_db()

        async for db in get_db_session():
            result = await db.execute(select(MessageAttachment))
            attachments = result.scalars().all()

            self.stats["total"] = len(attachments)
            logger.info(f"Found {self.stats['total']} attachment records to check\n")

            # Process each attachment
            for i, attachment in enumerate(attachments, 1):
                try:
                    await self._check_attachment(db, attachment, i)
                except Exception as e:
                    logger.error(f"❌ Error processing {attachment.id}: {e}")
                    self.stats["errors"] += 1

            # Commit database changes
            if not self.dry_run and self.stats["deleted"] > 0:
                await db.commit()
                logger.info(f"\n✅ Database changes committed - {self.stats['deleted']} records deleted")
            elif self.dry_run and self.stats["missing"] > 0:
                logger.info(f"\n[DRY RUN] Would delete {self.stats['missing']} orphaned records")
            else:
                logger.info("\n✅ No orphaned records found")

            break  # Only process first session

        # Print summary
        self._print_summary()

    async def _check_attachment(
        self,
        db,
        attachment: MessageAttachment,
        index: int
    ) -> None:
        """
        Check if attachment file exists, delete record if missing.

        Args:
            db: Database session
            attachment: MessageAttachment model instance
            index: Current attachment number (for progress)
        """
        attachment_id = attachment.id
        media_path = attachment.media_url_local

        # Progress indicator (every 10 records)
        if index % 10 == 0 or index == self.stats["total"]:
            logger.info(f"Progress: {index}/{self.stats['total']} checked...")

        if not media_path:
            logger.warning(f"  ⚠️  [{index}] {attachment_id}: No local path set")
            return

        # Get absolute path
        absolute_path = self._get_absolute_path(media_path)

        # Check if file exists
        if absolute_path.exists():
            self.stats["exists"] += 1
            # Verbose logging only in dry-run mode
            if self.dry_run and index <= 5:
                logger.info(f"  ✅ [{index}] {attachment_id}: File exists - {media_path}")
        else:
            self.stats["missing"] += 1
            logger.warning(f"  ❌ [{index}] {attachment_id}: Missing file - {media_path}")
            logger.warning(f"      Absolute path checked: {absolute_path}")

            # Delete the orphaned record
            if not self.dry_run:
                await db.execute(
                    delete(MessageAttachment)
                    .where(MessageAttachment.id == attachment_id)
                )
                self.stats["deleted"] += 1
                logger.info(f"      🗑️  Deleted orphaned record")
            else:
                logger.info(f"      [DRY RUN] Would delete this record")

    def _print_summary(self) -> None:
        """Print cleanup summary statistics."""
        logger.info("\n" + "=" * 60)
        logger.info("Cleanup Summary")
        logger.info("=" * 60)
        logger.info(f"Total attachment records: {self.stats['total']}")
        logger.info(f"Files exist: {self.stats['exists']}")
        logger.info(f"Files missing: {self.stats['missing']}")
        logger.info(f"Records deleted: {self.stats['deleted']}")
        logger.info(f"Errors: {self.stats['errors']}")
        logger.info("=" * 60)

        if self.dry_run:
            logger.info("\n⚠️  DRY RUN MODE - No changes were made")
            logger.info("Run without --dry-run to delete orphaned records")
        elif self.stats["deleted"] > 0:
            logger.info(f"\n✅ Cleanup complete! Removed {self.stats['deleted']} orphaned attachment records")
            logger.info("\nUI should no longer show 404 errors for these attachments.")
        else:
            logger.info("\n✅ All attachment files exist - no cleanup needed")


async def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Cleanup orphaned attachment records from database"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without making them"
    )
    parser.add_argument(
        "--base-dir",
        default="/opt/insta-messaging",
        help="Base directory where media files are stored (default: /opt/insta-messaging)"
    )
    args = parser.parse_args()

    cleaner = AttachmentCleaner(
        base_dir=args.base_dir,
        dry_run=args.dry_run
    )

    await cleaner.cleanup_orphaned_attachments()


if __name__ == "__main__":
    asyncio.run(main())
