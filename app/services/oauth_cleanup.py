"""
OAuth State Cleanup Service - Background task to remove expired state tokens

Runs periodically to prevent oauth_states table from growing unbounded.
Deletes state tokens that have expired (expires_at < now).
"""
import asyncio
import logging
from datetime import datetime, timezone
from sqlalchemy import delete
from app.db.models import OAuthState
from app.db.connection import get_db_session

logger = logging.getLogger(__name__)


async def cleanup_expired_oauth_states():
    """
    Delete expired OAuth state tokens from database.

    Returns:
        Number of expired states deleted
    """
    try:
        async for db in get_db_session():
            result = await db.execute(
                delete(OAuthState).where(OAuthState.expires_at < datetime.now(timezone.utc))
            )
            await db.commit()
            deleted_count = result.rowcount

            if deleted_count > 0:
                logger.info(f"🧹 Cleaned up {deleted_count} expired OAuth state token(s)")

            return deleted_count
    except Exception as e:
        logger.error(f"❌ OAuth state cleanup failed: {e}")
        return 0


async def periodic_oauth_state_cleanup(interval_seconds: int = 3600):
    """
    Run OAuth state cleanup periodically.

    Args:
        interval_seconds: How often to run cleanup (default: 1 hour)
    """
    logger.info(f"🔄 OAuth state cleanup task started (runs every {interval_seconds}s)")

    while True:
        try:
            await asyncio.sleep(interval_seconds)
            await cleanup_expired_oauth_states()
        except asyncio.CancelledError:
            logger.info("OAuth state cleanup task cancelled")
            break
        except Exception as e:
            logger.error(f"❌ Unexpected error in OAuth state cleanup: {e}")
            # Continue running even if one cleanup fails
