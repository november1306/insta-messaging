#!/usr/bin/env python3
"""
Debug script to check API responses and identify issues
"""
import asyncio
import sys
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from app.db.models import MessageModel
from app.config import settings
from datetime import datetime, timezone, timedelta

async def debug_conversations():
    """Check what the conversations endpoint should return"""
    print("=" * 60)
    print("DEBUGGING CONVERSATIONS ENDPOINT")
    print("=" * 60)

    # Get business account ID from settings
    business_account_id = settings.instagram_business_account_id
    print(f"\n✓ Business Account ID from .env: {business_account_id}")

    # Calculate cutoff time
    RESPONSE_WINDOW_HOURS = 24
    now = datetime.now(timezone.utc)
    cutoff_time = now - timedelta(hours=RESPONSE_WINDOW_HOURS)
    print(f"✓ Cutoff time (24h ago): {cutoff_time.isoformat()}")
    print(f"✓ Current time: {now.isoformat()}")

    # Create database engine and session
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{settings.database_url.split(':///')[-1]}",
        echo=False
    )
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        # Get all inbound messages
        stmt = select(MessageModel).where(MessageModel.direction == 'inbound').order_by(desc(MessageModel.timestamp))
        result = await db.execute(stmt)
        all_inbound = result.scalars().all()

        print(f"\n📊 Total inbound messages: {len(all_inbound)}")
        print("\nAll inbound messages:")
        for msg in all_inbound:
            age_hours = (now - msg.timestamp).total_seconds() / 3600
            print(f"  • {msg.sender_id} -> {msg.recipient_id}")
            print(f"    Text: {msg.message_text[:50]}")
            print(f"    Time: {msg.timestamp.isoformat()} ({age_hours:.1f}h ago)")
            print(f"    Within 24h window: {age_hours < 24}")
            print(f"    Is business account: {msg.sender_id == business_account_id}")
            print()

        # Apply the same filters as the endpoint
        subq = (
            select(
                MessageModel.sender_id,
                func.max(MessageModel.id).label('latest_message_id')
            )
            .where(MessageModel.direction == 'inbound')
            .group_by(MessageModel.sender_id)
            .subquery()
        )

        stmt = (
            select(MessageModel)
            .join(
                subq,
                (MessageModel.sender_id == subq.c.sender_id) &
                (MessageModel.id == subq.c.latest_message_id)
            )
            .where(MessageModel.timestamp >= cutoff_time)
            .where(MessageModel.sender_id != business_account_id)
            .order_by(desc(MessageModel.timestamp))
        )

        result = await db.execute(stmt)
        messages = result.scalars().all()

        print(f"\n✅ Conversations that SHOULD appear ({len(messages)}):")
        for msg in messages:
            time_remaining = (msg.timestamp + timedelta(hours=RESPONSE_WINDOW_HOURS)) - now
            hours_remaining = max(0, int(time_remaining.total_seconds() / 3600))

            print(f"\n  Sender: {msg.sender_id}")
            print(f"  Last message: {msg.message_text[:50]}")
            print(f"  Timestamp: {msg.timestamp.isoformat()}")
            print(f"  Hours remaining: {hours_remaining}h")
            print(f"  Can respond: {hours_remaining > 0}")

        # Check for problematic messages
        print("\n\n⚠️  CHECKING FOR ISSUES:")

        # Issue 1: Messages from business account
        stmt = select(MessageModel).where(
            MessageModel.direction == 'inbound',
            MessageModel.sender_id == business_account_id
        )
        result = await db.execute(stmt)
        self_messages = result.scalars().all()

        if self_messages:
            print(f"\n❌ Found {len(self_messages)} INBOUND messages FROM business account (shouldn't exist!):")
            for msg in self_messages:
                print(f"   • ID: {msg.id}, Text: {msg.message_text[:50]}")
        else:
            print("\n✓ No inbound messages from business account (good!)")

        # Issue 2: Messages older than 24h
        stmt = select(MessageModel).where(
            MessageModel.direction == 'inbound',
            MessageModel.timestamp < cutoff_time
        )
        result = await db.execute(stmt)
        old_messages = result.scalars().all()

        if old_messages:
            print(f"\n⏰ Found {len(old_messages)} messages older than 24h (won't appear in UI):")
            for msg in old_messages:
                age_hours = (now - msg.timestamp).total_seconds() / 3600
                print(f"   • {msg.sender_id}: {age_hours:.1f}h ago")

        print("\n" + "=" * 60)

if __name__ == "__main__":
    asyncio.run(debug_conversations())
