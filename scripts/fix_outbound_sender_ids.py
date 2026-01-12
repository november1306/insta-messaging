"""
Fix sender_id bug in outbound messages.

Bug: Outbound messages have database account ID (acc_xxx) in sender_id field
     instead of Instagram account ID (numeric string).

This breaks conversation filtering and is inconsistent with inbound messages
which use Instagram user IDs.

Fix: Replace sender_id with Account.instagram_account_id for outbound messages.

Usage:
    python scripts/fix_outbound_sender_ids.py [--dry-run] [--batch-size 1000]

Options:
    --dry-run: Show what would be updated without making changes
    --batch-size: Number of messages to process in each batch (default: 1000)
"""

import asyncio
import argparse
import logging
import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.connection import init_db, get_db_session_context
from app.db.models import MessageModel, Account

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SenderIdFixStats:
    """Track fix statistics"""

    def __init__(self):
        self.total_outbound = 0
        self.buggy_sender_ids = 0
        self.fixed = 0
        self.account_not_found = 0
        self.already_correct = 0

    def print_summary(self):
        """Print statistics summary"""
        logger.info("=" * 70)
        logger.info("Sender ID Fix Summary:")
        logger.info(f"  Total outbound messages: {self.total_outbound}")
        logger.info(f"  Buggy sender_ids (acc_xxx format): {self.buggy_sender_ids}")
        logger.info(f"  Already correct (Instagram ID): {self.already_correct}")
        logger.info(f"  Successfully fixed: {self.fixed}")
        logger.info(f"  Account not found: {self.account_not_found}")
        logger.info("=" * 70)


async def fix_outbound_sender_ids(
    db: AsyncSession,
    dry_run: bool = False,
    batch_size: int = 1000
) -> SenderIdFixStats:
    """
    Fix sender_id for outbound messages.

    Current bug: sender_id = 'acc_xxx' (database ID)
    Fix: sender_id = Instagram account ID (numeric)

    Args:
        db: Database session
        dry_run: If True, don't make changes (just log what would happen)
        batch_size: Number of messages to process per batch

    Returns:
        Statistics about the fix operation
    """
    stats = SenderIdFixStats()

    # Get total outbound message count
    total_count_result = await db.execute(
        select(func.count(MessageModel.id)).where(MessageModel.direction == 'outbound')
    )
    stats.total_outbound = total_count_result.scalar()
    logger.info(f"Total outbound messages: {stats.total_outbound}")

    # Get outbound messages with buggy sender_id (starts with 'acc_')
    buggy_count_result = await db.execute(
        select(func.count(MessageModel.id)).where(
            MessageModel.direction == 'outbound',
            MessageModel.sender_id.like('acc_%')
        )
    )
    stats.buggy_sender_ids = buggy_count_result.scalar()
    stats.already_correct = stats.total_outbound - stats.buggy_sender_ids

    logger.info(f"Buggy sender_ids (acc_xxx format): {stats.buggy_sender_ids}")
    logger.info(f"Already correct (Instagram ID): {stats.already_correct}")

    if stats.buggy_sender_ids == 0:
        logger.info("✅ All outbound messages already have correct sender_id. Nothing to fix.")
        return stats

    # Load all accounts into memory
    accounts_result = await db.execute(select(Account))
    accounts = accounts_result.scalars().all()

    # Create lookup dictionary: database account_id → instagram_account_id
    account_id_to_instagram_id = {
        acc.id: acc.instagram_account_id
        for acc in accounts
    }

    logger.info(f"Loaded {len(accounts)} accounts for lookup")

    # Process messages in batches
    offset = 0
    while True:
        # Fetch batch of buggy outbound messages
        stmt = (
            select(MessageModel)
            .where(
                MessageModel.direction == 'outbound',
                MessageModel.sender_id.like('acc_%')
            )
            .limit(batch_size)
            .offset(offset)
        )
        result = await db.execute(stmt)
        messages = result.scalars().all()

        if not messages:
            break  # No more messages to process

        logger.info(f"Processing batch: offset={offset}, size={len(messages)}")

        for msg in messages:
            old_sender_id = msg.sender_id  # Database ID (acc_xxx)

            # Look up Instagram account ID
            instagram_account_id = account_id_to_instagram_id.get(old_sender_id)

            if not instagram_account_id:
                # Account not found (maybe deleted?)
                stats.account_not_found += 1
                logger.warning(
                    f"⚠️  Account not found for message {msg.id}: "
                    f"sender_id={old_sender_id}"
                )
                continue

            # Update sender_id
            if dry_run:
                logger.info(
                    f"[DRY RUN] Would fix message {msg.id}: "
                    f"{old_sender_id} → {instagram_account_id}"
                )
            else:
                msg.sender_id = instagram_account_id
                stats.fixed += 1

                if stats.fixed % 100 == 0:
                    logger.info(f"  Fixed {stats.fixed} messages...")

        # Commit batch
        if not dry_run:
            await db.commit()
            logger.info(f"✅ Committed batch of {len(messages)} messages")

        offset += batch_size

    return stats


async def verify_fix(db: AsyncSession) -> bool:
    """
    Verify that no outbound messages have database IDs in sender_id.

    Returns:
        True if all outbound sender_ids are Instagram IDs, False otherwise
    """
    result = await db.execute(
        select(func.count(MessageModel.id)).where(
            MessageModel.direction == 'outbound',
            MessageModel.sender_id.like('acc_%')
        )
    )
    count = result.scalar()

    if count == 0:
        logger.info("✅ Verification passed: All outbound messages have Instagram IDs in sender_id")
        return True
    else:
        logger.error(f"❌ Verification failed: {count} outbound messages still have database IDs")
        return False


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Fix sender_id bug in outbound messages"
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be updated without making changes'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=1000,
        help='Number of messages to process per batch (default: 1000)'
    )
    parser.add_argument(
        '--verify-only',
        action='store_true',
        help='Only verify that all sender_ids are correct'
    )

    args = parser.parse_args()

    # Log configuration
    logger.info("=" * 70)
    logger.info("Outbound Sender ID Fix Script")
    logger.info("=" * 70)
    logger.info(f"Dry run: {args.dry_run}")
    logger.info(f"Batch size: {args.batch_size}")
    logger.info(f"Verify only: {args.verify_only}")
    logger.info("=" * 70)

    # Initialize database
    await init_db()

    # Get database session
    async with get_db_session_context() as db:
        if args.verify_only:
            # Just verify
            success = await verify_fix(db)
            sys.exit(0 if success else 1)
        else:
            # Run fix
            stats = await fix_outbound_sender_ids(
                db,
                dry_run=args.dry_run,
                batch_size=args.batch_size
            )

            # Print summary
            stats.print_summary()

            # Verify if not dry-run
            if not args.dry_run:
                logger.info("\nVerifying fix...")
                success = await verify_fix(db)

                if success:
                    logger.info("\n✅ Fix completed successfully!")
                    sys.exit(0)
                else:
                    logger.error("\n❌ Fix completed but verification failed!")
                    sys.exit(1)
            else:
                logger.info("\n[DRY RUN] No changes were made.")
                if stats.account_not_found > 0:
                    logger.warning(
                        f"\n⚠️  Warning: {stats.account_not_found} messages reference "
                        f"deleted accounts. These messages won't be fixed."
                    )
                sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
