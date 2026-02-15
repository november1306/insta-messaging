"""
Lightweight factory for creating Account objects in tests.

Use this when you need an Account instance without full database seeding.
For tests that need a real DB with linked users, use the `seeded_db` fixture instead.
"""
from datetime import datetime, timezone, timedelta

from app.db.models import Account


def make_account(
    id: str = "acc_factory_001",
    instagram_account_id: str = "17841400000000001",
    username: str = "factory_account",
    messaging_channel_id: str | None = "17841400000000001",
    access_token_encrypted: str = "encrypted_placeholder",
    token_expires_at: datetime | None = None,
    account_type: str = "business",
    **kwargs,
) -> Account:
    """
    Build an Account model instance with sensible defaults.

    All parameters are overridable. Does NOT touch the database.

    Args:
        id: Account ID (default: acc_factory_001)
        instagram_account_id: Instagram's OAuth profile ID
        username: Instagram username
        messaging_channel_id: Webhook routing channel ID
        access_token_encrypted: Pre-encrypted token string
        token_expires_at: Token expiration (default: 60 days from now)
        account_type: 'business', 'creator', etc.
        **kwargs: Additional Account fields to override

    Returns:
        Account model instance (not persisted)
    """
    if token_expires_at is None:
        token_expires_at = datetime.now(timezone.utc) + timedelta(days=60)

    return Account(
        id=id,
        instagram_account_id=instagram_account_id,
        username=username,
        messaging_channel_id=messaging_channel_id,
        access_token_encrypted=access_token_encrypted,
        token_expires_at=token_expires_at,
        account_type=account_type,
        **kwargs,
    )
