"""
Backfill account_id for existing messages.

This script populates the account_id column for messages that were created
before the column was added.

Strategy:
1. Match recipient_id to Account.messaging_channel_id (preferred)
2. Fallback to Account.instagram_account_id
3. Log orphaned messages (no matching account)

Usage:
    python scripts/backfill_account_ids.py [--dry-run] [--batch-size 1000]

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

from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.connection import init_db, get_db_session_context
from app.db.models import MessageModel, Account

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AccountIdBackfillStats:
    """Track backfill statistics"""

    def __init__(self):
        self.total_messages = 0
        self.messages_without_account_id = 0
        self.matched_by_messaging_channel_id = 0
        self.matched_by_instagram_account_id = 0
        self.orphaned = 0
        self.updated = 0

    def print_summary(self):
        """Print statistics summary"""
        logger.info("=" * 70)
        logger.info("Backfill Summary:")
        logger.info(f"  Total messages: {self.total_messages}")
        logger.info(f"  Messages needing backfill: {self.messages_without_account_id}")
        logger.info(f"  Matched by messaging_channel_id: {self.matched_by_messaging_channel_id}")
        logger.info(f"  Matched by instagram_account_id: {self.matched_by_instagram_account_id}")
        logger.info(f"  Orphaned (no account found): {self.orphaned}")
        logger.info(f"  Successfully updated: {self.updated}")
        logger.info("=" * 70)


async def backfill_account_ids(
    db: AsyncSession,
    dry_run: bool = False,
    batch_size: int = 1000
) -> AccountIdBackfillStats:
    """
    Backfill account_id for existing messages.

    Args:
        db: Database session
        dry_run: If True, don't make changes (just log what would happen)
        batch_size: Number of messages to process per batch

    Returns:
        Statistics about the backfill operation
    """
    stats = AccountIdBackfillStats()

    # Get total message count
    total_count_result = await db.execute(select(func.count(MessageModel.id)))
    stats.total_messages = total_count_result.scalar()
    logger.info(f"Total messages in database: {stats.total_messages}")

    # Get messages without account_id
    count_result = await db.execute(
        select(func.count(MessageModel.id)).where(MessageModel.account_id.is_(None))
    )
    stats.messages_without_account_id = count_result.scalar()
    logger.info(f"Messages needing backfill: {stats.messages_without_account_id}")

    if stats.messages_without_account_id == 0:
        logger.info("✅ All messages already have account_id. Nothing to backfill.")
        return stats

    # Load all accounts into memory (should be small number)
    accounts_result = await db.execute(select(Account))
    accounts = accounts_result.scalars().all()

    # Create lookup dictionaries
    by_messaging_channel = {
        acc.messaging_channel_id: acc.id
        for acc in accounts
        if acc.messaging_channel_id
    }
    by_instagram_account = {
        acc.instagram_account_id: acc.id
        for acc in accounts
        if acc.instagram_account_id
    }

    logger.info(f"Loaded {len(accounts)} accounts:")
    logger.info(f"  {len(by_messaging_channel)} with messaging_channel_id")
    logger.info(f"  {len(by_instagram_account)} with instagram_account_id")

    # Process messages in batches
    offset = 0
    while True:
        # Fetch batch of messages without account_id
        stmt = (
            select(MessageModel)
            .where(MessageModel.account_id.is_(None))
            .limit(batch_size)
            .offset(offset)
        )
        result = await db.execute(stmt)
        messages = result.scalars().all()

        if not messages:
            break  # No more messages to process

        logger.info(f"Processing batch: offset={offset}, size={len(messages)}")

        for msg in messages:
            # For inbound messages: match by recipient_id (our account)
            # For outbound messages: match by sender_id (our account)
            lookup_id = msg.recipient_id if msg.direction == 'inbound' else msg.sender_id

            # Try matching by messaging_channel_id first (preferred)
            matched_account_id = by_messaging_channel.get(lookup_id)

            if matched_account_id:
                stats.matched_by_messaging_channel_id += 1
                match_method = "messaging_channel_id"
            else:
                # Fallback: try matching by instagram_account_id
                matched_account_id = by_instagram_account.get(lookup_id)
                if matched_account_id:
                    stats.matched_by_instagram_account_id += 1
                    match_method = "instagram_account_id"
                else:
                    # No match found - orphaned message
                    stats.orphaned += 1
                    logger.warning(
                        f"⚠️  Orphaned message: id={msg.id}, "
                        f"direction={msg.direction}, "
                        f"sender_id={msg.sender_id}, "
                        f"recipient_id={msg.recipient_id}, "
                        f"timestamp={msg.timestamp}"
                    )
                    continue

            # Update message (or log if dry-run)
            if dry_run:
                logger.info(
                    f"[DRY RUN] Would update message {msg.id}: "
                    f"account_id={matched_account_id} (via {match_method})"
                )
            else:
                msg.account_id = matched_account_id
                stats.updated += 1

                if stats.updated % 100 == 0:
                    logger.info(f"  Updated {stats.updated} messages...")

        # Commit batch
        if not dry_run:
            await db.commit()
            logger.info(f"✅ Committed batch of {len(messages)} messages")

        offset += batch_size

    return stats


async def verify_backfill(db: AsyncSession) -> bool:
    """
    Verify that all messages have account_id.

    Returns:
        True if all messages have account_id, False otherwise
    """
    result = await db.execute(
        select(func.count(MessageModel.id)).where(MessageModel.account_id.is_(None))
    )
    count = result.scalar()

    if count == 0:
        logger.info("✅ Verification passed: All messages have account_id")
        return True
    else:
        logger.error(f"❌ Verification failed: {count} messages still missing account_id")
        return False


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Backfill account_id for existing messages"
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
        help='Only verify that all messages have account_id'
    )

    args = parser.parse_args()

    # Log configuration
    logger.info("=" * 70)
    logger.info("Account ID Backfill Script")
    logger.info("=" * 70)
    logger.info(f"Dry run: {args.dry_run}")
    logger.info(f"Batch size: {args.batch_size}")
    logger.info(f"Verify only: {args.verify_only}")
    logger.info("=" * 70)

    # Initialize database
    await init_db()

    # Get database session
    async with await get_db_session_context() as db:
        if args.verify_only:
            # Just verify
            success = await verify_backfill(db)
            sys.exit(0 if success else 1)
        else:
            # Run backfill
            stats = await backfill_account_ids(
                db,
                dry_run=args.dry_run,
                batch_size=args.batch_size
            )

            # Print summary
            stats.print_summary()

            # Verify if not dry-run
            if not args.dry_run:
                logger.info("\nVerifying backfill...")
                success = await verify_backfill(db)

                if success:
                    logger.info("\n✅ Backfill completed successfully!")
                    sys.exit(0)
                else:
                    logger.error("\n❌ Backfill completed but verification failed!")
                    sys.exit(1)
            else:
                logger.info("\n[DRY RUN] No changes were made.")
                if stats.orphaned > 0:
                    logger.warning(
                        f"\n⚠️  Warning: {stats.orphaned} orphaned messages found. "
                        f"These messages won't be backfilled."
                    )
                sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
