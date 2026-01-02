"""
Account Media Cleanup Service

Handles deletion of all media files associated with an Instagram account.
Used during complete account deletion to remove:
- Inbound media (downloaded from Instagram) in media/attachments/
- Outbound media (uploaded for sending) in media/outbound/{account_id}/
"""
import logging
import os
import shutil
from pathlib import Path
from typing import Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import MessageModel, MessageAttachment

logger = logging.getLogger(__name__)


class AccountMediaCleanup:
    """Service for cleaning up media files when an account is deleted."""

    def __init__(self, media_dir: str):
        """
        Initialize cleanup service.

        Args:
            media_dir: Base media directory path (e.g., "media/")
        """
        self.media_dir = Path(media_dir)
        self.attachments_dir = self.media_dir / "attachments"
        self.outbound_dir = self.media_dir / "outbound"

    async def cleanup_account_media(
        self,
        account_id: str,
        db: AsyncSession
    ) -> Dict[str, int]:
        """
        Delete all media files associated with an account's messages.

        This includes:
        - Inbound attachments downloaded from Instagram
        - Outbound media files uploaded for sending

        Args:
            account_id: The account ID whose media should be deleted
            db: Database session for querying messages

        Returns:
            Statistics dictionary with:
            {
                "inbound_files_deleted": int,
                "outbound_files_deleted": int,
                "total_bytes_freed": int
            }

        Note:
            - File deletion errors are logged but don't fail the operation
            - Missing files are silently skipped (already deleted)
            - Returns best-effort statistics
        """
        stats = {
            "inbound_files_deleted": 0,
            "outbound_files_deleted": 0,
            "total_bytes_freed": 0
        }

        try:
            # Clean up inbound attachments
            inbound_stats = await self._cleanup_inbound_attachments(account_id, db)
            stats["inbound_files_deleted"] = inbound_stats["files_deleted"]
            stats["total_bytes_freed"] += inbound_stats["bytes_freed"]

            # Clean up outbound media directory
            outbound_stats = self._cleanup_outbound_directory(account_id)
            stats["outbound_files_deleted"] = outbound_stats["files_deleted"]
            stats["total_bytes_freed"] += outbound_stats["bytes_freed"]

            logger.info(
                f"Media cleanup complete for account {account_id}: "
                f"{stats['inbound_files_deleted']} inbound files, "
                f"{stats['outbound_files_deleted']} outbound files, "
                f"{stats['total_bytes_freed']} bytes freed"
            )

        except Exception as e:
            logger.error(
                f"Error during media cleanup for account {account_id}: {e}",
                exc_info=True
            )
            # Don't re-raise - return partial statistics

        return stats

    async def _cleanup_inbound_attachments(
        self,
        account_id: str,
        db: AsyncSession
    ) -> Dict[str, int]:
        """
        Delete inbound attachment files from media/attachments/.

        Queries all messages for the account and deletes their attachment files.
        """
        stats = {"files_deleted": 0, "bytes_freed": 0}

        try:
            # Query all messages for this account with attachments loaded
            result = await db.execute(
                select(MessageModel)
                .where(MessageModel.account_id == account_id)
                .options(selectinload(MessageModel.attachments))
            )
            messages = result.scalars().all()

            # Collect all attachment file paths
            file_paths: List[Path] = []
            for message in messages:
                if message.attachments:
                    for attachment in message.attachments:
                        if attachment.media_url_local:
                            # media_url_local format: "media/attachments/{message_id}_{index}.{ext}"
                            # Convert to absolute path
                            file_path = Path(attachment.media_url_local)
                            if not file_path.is_absolute():
                                file_path = Path.cwd() / file_path
                            file_paths.append(file_path)

            # Delete files
            for file_path in file_paths:
                try:
                    if file_path.exists():
                        file_size = file_path.stat().st_size
                        file_path.unlink()
                        stats["files_deleted"] += 1
                        stats["bytes_freed"] += file_size
                        logger.debug(f"Deleted attachment file: {file_path}")
                    else:
                        logger.debug(f"Attachment file already deleted: {file_path}")
                except Exception as e:
                    logger.warning(
                        f"Failed to delete attachment file {file_path}: {e}"
                    )
                    # Continue with other files

        except Exception as e:
            logger.error(
                f"Error querying attachments for account {account_id}: {e}",
                exc_info=True
            )

        return stats

    def _cleanup_outbound_directory(self, account_id: str) -> Dict[str, int]:
        """
        Delete entire outbound media directory for an account.

        Removes: media/outbound/{account_id}/
        """
        stats = {"files_deleted": 0, "bytes_freed": 0}

        account_outbound_dir = self.outbound_dir / account_id

        try:
            if account_outbound_dir.exists() and account_outbound_dir.is_dir():
                # Calculate total size before deletion
                total_size = 0
                file_count = 0
                for root, dirs, files in os.walk(account_outbound_dir):
                    for file in files:
                        file_path = Path(root) / file
                        try:
                            total_size += file_path.stat().st_size
                            file_count += 1
                        except Exception as e:
                            logger.warning(f"Could not stat file {file_path}: {e}")

                # Delete entire directory
                shutil.rmtree(account_outbound_dir)
                stats["files_deleted"] = file_count
                stats["bytes_freed"] = total_size

                logger.info(
                    f"Deleted outbound directory {account_outbound_dir}: "
                    f"{file_count} files, {total_size} bytes"
                )
            else:
                logger.debug(
                    f"Outbound directory does not exist: {account_outbound_dir}"
                )

        except Exception as e:
            logger.error(
                f"Failed to delete outbound directory {account_outbound_dir}: {e}",
                exc_info=True
            )

        return stats
