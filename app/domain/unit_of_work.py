"""
Unit of Work pattern for transaction management.

The Unit of Work pattern ensures:
1. All operations happen in a single transaction
2. Atomic commit (all or nothing)
3. Post-commit hooks run AFTER successful commit (for SSE broadcasts, webhooks, etc.)
4. Proper resource cleanup

This fixes the SSE race condition where broadcasts happened before commit.
"""

from abc import ABC, abstractmethod
from typing import Callable, List, TYPE_CHECKING
from sqlalchemy.ext.asyncio import AsyncSession
import logging

if TYPE_CHECKING:
    from app.core.interfaces import IMessageRepository, IAccountRepository

logger = logging.getLogger(__name__)


class AbstractUnitOfWork(ABC):
    """
    Abstract Unit of Work for transaction management.

    Provides:
    - Transaction boundaries (commit/rollback)
    - Repository access (messages, accounts)
    - Post-commit hooks for side effects (SSE, webhooks)
    """

    messages: 'IMessageRepository'
    accounts: 'IAccountRepository'

    async def __aenter__(self):
        """Enter async context"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Exit async context.

        On success: commits and runs post-commit hooks
        On exception: rolls back (no hooks run)
        """
        try:
            if exc_type is None:
                await self.commit()
            else:
                await self.rollback()
        finally:
            await self.close()

    @abstractmethod
    async def commit(self):
        """Commit transaction and execute post-commit hooks"""
        pass

    @abstractmethod
    async def rollback(self):
        """Rollback transaction"""
        pass

    @abstractmethod
    async def close(self):
        """Close resources"""
        pass

    @abstractmethod
    def add_post_commit_hook(self, hook: Callable):
        """
        Register a post-commit hook.

        Hook will be called AFTER successful commit.
        Use for side effects like SSE broadcasts, webhook notifications.

        Args:
            hook: Async callable to execute after commit
        """
        pass


class SQLAlchemyUnitOfWork(AbstractUnitOfWork):
    """
    SQLAlchemy implementation of Unit of Work.

    Features:
    - Transaction management via SQLAlchemy session
    - Post-commit hooks for side effects
    - Repository initialization
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize Unit of Work.

        Args:
            session: SQLAlchemy async session
        """
        self._session = session
        self._post_commit_hooks: List[Callable] = []

        # Import here to avoid circular dependencies
        from app.repositories.message_repository import MessageRepository
        from app.repositories.account_repository import AccountRepository

        # Initialize repositories
        self.messages = MessageRepository(session)
        self.accounts = AccountRepository(session)

    async def commit(self):
        """
        Commit transaction and execute post-commit hooks.

        Post-commit hooks are executed in order after successful commit.
        Hook failures are logged but don't affect the transaction.
        """
        try:
            await self._session.commit()
            logger.debug(f"✅ Transaction committed, running {len(self._post_commit_hooks)} post-commit hooks")

            # Run post-commit hooks
            for hook in self._post_commit_hooks:
                try:
                    if callable(hook):
                        # Check if it's async
                        import inspect
                        if inspect.iscoroutinefunction(hook):
                            await hook()
                        else:
                            hook()
                except Exception as e:
                    # Log but don't fail - transaction already committed
                    logger.error(f"❌ Post-commit hook failed: {e}", exc_info=True)

        finally:
            # Always clear hooks after commit
            self._post_commit_hooks.clear()

    async def rollback(self):
        """
        Rollback transaction.

        Discards all pending changes and clears post-commit hooks.
        """
        try:
            await self._session.rollback()
            logger.debug("↩️  Transaction rolled back")
        finally:
            # Clear hooks on rollback - they won't run
            self._post_commit_hooks.clear()

    async def close(self):
        """Close session and release resources"""
        await self._session.close()

    def add_post_commit_hook(self, hook: Callable):
        """
        Add a post-commit hook.

        Args:
            hook: Callable (sync or async) to execute after commit

        Example:
            async def notify_user():
                await send_notification(message)

            uow.add_post_commit_hook(notify_user)
        """
        self._post_commit_hooks.append(hook)


async def get_unit_of_work(session: AsyncSession) -> AbstractUnitOfWork:
    """
    Factory function for Unit of Work.

    Args:
        session: SQLAlchemy async session

    Returns:
        Configured Unit of Work instance

    Usage in FastAPI:
        async def endpoint(
            db: AsyncSession = Depends(get_db_session)
        ):
            async with get_unit_of_work(db) as uow:
                message = await uow.messages.save(message)
                uow.add_post_commit_hook(
                    lambda: broadcast_message(message)
                )
                # Commit happens on context exit
    """
    return SQLAlchemyUnitOfWork(session)
