"""
Media Cleanup Service - Background task to delete expired outbound media files

Outbound media files are temporary (24-hour TTL) since Instagram stores the sent messages.
This service runs periodically to clean up old files and prevent disk bloat.
"""
import asyncio
from pathlib import Path
from datetime import datetime, timezone, timedelta
import logging

logger = logging.getLogger(__name__)


async def cleanup_expired_media(media_dir: Path, max_age_hours: int = 24):
    """
    Delete outbound media files older than max_age_hours.

    Args:
        media_dir: Path to the media directory (contains 'outbound' subdirectory)
        max_age_hours: Maximum age in hours before files are deleted (default: 24)

    Returns:
        int: Number of files deleted
    """
    outbound_dir = media_dir / "outbound"

    if not outbound_dir.exists():
        logger.debug("Outbound media directory does not exist, skipping cleanup")
        return 0

    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    deleted_count = 0
    total_size_deleted = 0

    try:
        # Iterate through account directories
        for account_dir in outbound_dir.iterdir():
            if not account_dir.is_dir():
                continue

            # Iterate through files in each account directory
            for file_path in account_dir.iterdir():
                if not file_path.is_file():
                    continue

                try:
                    # Get file modification time
                    file_mtime = datetime.fromtimestamp(
                        file_path.stat().st_mtime,
                        tz=timezone.utc
                    )

                    # Delete if older than cutoff
                    if file_mtime < cutoff_time:
                        file_size = file_path.stat().st_size
                        file_path.unlink()
                        deleted_count += 1
                        total_size_deleted += file_size
                        logger.debug(f"Deleted expired media file: {file_path}")

                except Exception as e:
                    logger.error(f"Error deleting file {file_path}: {e}")
                    continue

            # Remove empty account directories
            try:
                if account_dir.is_dir() and not any(account_dir.iterdir()):
                    account_dir.rmdir()
                    logger.debug(f"Removed empty directory: {account_dir}")
            except Exception as e:
                logger.debug(f"Could not remove directory {account_dir}: {e}")

    except Exception as e:
        logger.error(f"Error during media cleanup: {e}", exc_info=True)

    if deleted_count > 0:
        size_mb = total_size_deleted / 1024 / 1024
        logger.info(
            f"🧹 Cleaned up {deleted_count} expired outbound media files "
            f"({size_mb:.2f} MB freed)"
        )

    return deleted_count


async def periodic_cleanup_task(media_dir: Path, interval_hours: int = 1, max_age_hours: int = 24):
    """
    Run cleanup task periodically in a background loop.

    Args:
        media_dir: Path to the media directory
        interval_hours: How often to run cleanup (default: 1 hour)
        max_age_hours: Maximum age of files before deletion (default: 24 hours)
    """
    logger.info(
        f"📅 Media cleanup task started - "
        f"runs every {interval_hours}h, deletes files older than {max_age_hours}h"
    )

    while True:
        try:
            await cleanup_expired_media(media_dir, max_age_hours)
        except Exception as e:
            logger.error(f"Cleanup task error: {e}", exc_info=True)

        # Wait for next cleanup cycle
        await asyncio.sleep(interval_hours * 3600)  # Convert hours to seconds
