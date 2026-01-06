"""
Instagram Account Linking Service

Handles OAuth flow, account creation, and conversation sync.
Follows application service pattern (orchestrates domain logic).
"""
from dataclasses import dataclass
from typing import Optional
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import httpx
import logging
import uuid
import secrets

from app.db.models import Account, UserAccount, User, OAuthState, InstagramProfile, MessageModel
from app.clients.instagram_client import InstagramClient
from app.services.encryption_service import get_encryption_service
from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class OAuthResult:
    """Result of OAuth flow"""
    success: bool
    account: Optional[Account] = None
    error_message: Optional[str] = None
    conversations_synced: int = 0


class AccountLinkingService:
    """
    Service for Instagram account OAuth linking and setup.

    Responsibilities:
    - Initialize OAuth flow
    - Handle OAuth callback (validate, exchange tokens, create account)
    - Sync conversation history from Instagram
    - Link accounts to users
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.encryption = get_encryption_service(settings.session_secret)

    async def initialize_oauth(
        self,
        user_id: int,
        redirect_uri: str,
        force_reauth: bool = False
    ) -> tuple[str, datetime]:
        """
        Initialize OAuth flow for a user.

        Args:
            user_id: Authenticated user ID
            redirect_uri: Where to redirect after OAuth
            force_reauth: Force user to reauth (for linking multiple accounts)

        Returns:
            Tuple of (auth_url, expires_at)
        """
        # Generate CSRF token
        state = secrets.token_urlsafe(32)

        # Store state in database
        now = datetime.now(timezone.utc)
        oauth_state = OAuthState(
            state=state,
            user_id=user_id,
            redirect_uri=redirect_uri,
            created_at=now,
            expires_at=now + timedelta(minutes=10)
        )
        self.db.add(oauth_state)
        await self.db.commit()

        # Build Instagram OAuth URL
        # Note: Only requesting scopes we actually use
        scopes = [
            "instagram_business_basic",
            "instagram_business_manage_messages",
        ]

        from urllib.parse import urlencode

        params = {
            "client_id": settings.instagram_oauth_client_id,
            "redirect_uri": settings.instagram_oauth_redirect_uri,
            "response_type": "code",
            "scope": " ".join(scopes),  # Space-separated per OAuth spec
            "state": state
        }

        # Add force_reauth if requested (for linking multiple accounts)
        if force_reauth:
            params["force_reauth"] = "true"

        query_string = urlencode(params)
        auth_url = f"https://www.instagram.com/oauth/authorize?{query_string}"

        logger.info(f"OAuth flow initialized for user {user_id} (force_reauth={force_reauth})")
        return auth_url, oauth_state.expires_at

    async def handle_oauth_callback(
        self,
        code: str,
        state: str
    ) -> OAuthResult:
        """
        Handle OAuth callback and link account.

        This method wraps all database operations in a single transaction
        to ensure atomic behavior. If any step fails, all changes are rolled back.

        Args:
            code: Authorization code from Instagram
            state: CSRF state token

        Returns:
            OAuthResult with account and sync status
        """
        try:
            # 1. Validate state token
            oauth_state = await self._validate_state_token(state)
            if not oauth_state:
                return OAuthResult(success=False, error_message="Invalid state token")

            user_id = oauth_state.user_id

            # Delete state token (one-time use) - will be committed with transaction
            await self.db.delete(oauth_state)

            # 2. Exchange code for access token (no DB operation)
            token_data = await self._exchange_code_for_token(code)
            if not token_data:
                await self.db.rollback()  # Rollback state deletion
                return OAuthResult(success=False, error_message="Token exchange failed")

            access_token = token_data["access_token"]
            expires_in = token_data.get("expires_in", 5184000)  # Default 60 days

            # 3. Fetch Instagram account details (no DB operation)
            async with httpx.AsyncClient() as http_client:
                instagram_client = InstagramClient(
                    http_client=http_client,
                    access_token=access_token,
                    logger_instance=logger
                )

                account_data = await instagram_client.get_business_account_profile(
                    token_data["user_id"]
                )

                if not account_data:
                    await self.db.rollback()
                    return OAuthResult(success=False, error_message="Failed to fetch account details")

                # Validate account type
                account_type = account_data.get("account_type", "").upper()
                if account_type == "PERSONAL":
                    await self.db.rollback()
                    return OAuthResult(
                        success=False,
                        error_message="Personal accounts not supported. Please convert to Business or Creator account."
                    )

                # 4. Create or update account (DB operation - no commit inside)
                account = await self._create_or_update_account(
                    instagram_account_id=token_data["user_id"],
                    username=account_data.get("username"),
                    access_token=access_token,
                    token_expires_at=datetime.now(timezone.utc) + timedelta(seconds=expires_in),
                    profile_picture_url=account_data.get("profile_picture_url"),
                    account_type=account_type or "unknown"
                )

                # 5. Link to user (DB operation - no commit inside)
                await self._link_account_to_user(user_id, account.id)

                # 6. Sync conversation history (optional, graceful degradation)
                # Note: Conversation sync errors are logged but don't fail the transaction
                conversations_synced = await self._sync_conversation_history(
                    instagram_client,
                    account
                )

                # COMMIT ALL CHANGES ATOMICALLY
                # This commits: state deletion, account creation/update, user link, and synced messages
                await self.db.commit()

                logger.info(
                    f"✅ Account {account.id} linked to user {user_id}, "
                    f"synced {conversations_synced} conversations"
                )

                return OAuthResult(
                    success=True,
                    account=account,
                    conversations_synced=conversations_synced
                )

        except Exception as e:
            # Rollback ALL changes on any error
            await self.db.rollback()
            logger.error(f"❌ OAuth callback failed, rolled back transaction: {e}", exc_info=True)
            return OAuthResult(
                success=False,
                error_message=f"Account linking failed: {str(e)}"
            )

    async def _validate_state_token(self, state: str) -> Optional[OAuthState]:
        """Validate CSRF state token (no commit - relies on parent transaction)"""
        result = await self.db.execute(
            select(OAuthState).where(OAuthState.state == state)
        )
        oauth_state = result.scalar_one_or_none()

        if not oauth_state:
            logger.error("Invalid OAuth state token")
            return None

        if oauth_state.expires_at < datetime.now(timezone.utc):
            logger.error("Expired OAuth state token")
            await self.db.delete(oauth_state)
            # Note: Deletion will be committed by parent transaction
            return None

        return oauth_state

    async def _exchange_code_for_token(self, code: str) -> Optional[dict]:
        """Exchange authorization code for access token"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Step 1: Get short-lived token
            token_response = await client.post(
                "https://api.instagram.com/oauth/access_token",
                data={
                    "client_id": settings.instagram_oauth_client_id,
                    "client_secret": settings.instagram_oauth_client_secret,
                    "grant_type": "authorization_code",
                    "redirect_uri": settings.instagram_oauth_redirect_uri,
                    "code": code
                }
            )

            if token_response.status_code != 200:
                logger.error(f"Token exchange failed: {token_response.status_code}")
                return None

            short_lived_data = token_response.json()
            short_lived_token = short_lived_data.get("access_token")
            user_id = short_lived_data.get("user_id")

            # Step 2: Exchange for long-lived token (60 days)
            long_lived_response = await client.get(
                "https://graph.instagram.com/access_token",
                params={
                    "grant_type": "ig_exchange_token",
                    "client_secret": settings.instagram_oauth_client_secret,
                    "access_token": short_lived_token
                }
            )

            if long_lived_response.status_code != 200:
                logger.warning("Long-lived token exchange failed, using short-lived token")
                return {
                    "access_token": short_lived_token,
                    "user_id": user_id,
                    "expires_in": 3600  # 1 hour
                }

            long_lived_data = long_lived_response.json()
            return {
                "access_token": long_lived_data.get("access_token"),
                "user_id": user_id,
                "expires_in": long_lived_data.get("expires_in", 5184000)  # 60 days
            }

    async def _create_or_update_account(
        self,
        instagram_account_id: str,
        username: str,
        access_token: str,
        token_expires_at: datetime,
        profile_picture_url: Optional[str],
        account_type: Optional[str]
    ) -> Account:
        """Create new account or update existing one (no commit - relies on parent transaction)"""
        # Check if account exists
        result = await self.db.execute(
            select(Account).where(Account.instagram_account_id == instagram_account_id)
        )
        account = result.scalar_one_or_none()

        if account:
            # Update existing account
            account.username = username
            account.access_token_encrypted = self.encryption.encrypt(access_token)
            account.token_expires_at = token_expires_at
            account.profile_picture_url = profile_picture_url
            account.account_type = account_type
            # Set messaging_channel_id if not already set (backfill for OAuth-only accounts)
            if not account.messaging_channel_id:
                account.messaging_channel_id = instagram_account_id
            logger.info(f"Updated existing account: {account.id}")
        else:
            # Create new account
            account = Account(
                id=f"acc_{uuid.uuid4().hex[:12]}",
                instagram_account_id=instagram_account_id,
                messaging_channel_id=instagram_account_id,  # Initialize with OAuth profile ID
                username=username,
                access_token_encrypted=self.encryption.encrypt(access_token),
                token_expires_at=token_expires_at,
                profile_picture_url=profile_picture_url,
                account_type=account_type
            )
            self.db.add(account)
            logger.info(f"Created new account: {account.id}")

        # Flush to get account.id populated (but don't commit transaction)
        await self.db.flush()
        return account

    async def _link_account_to_user(self, user_id: int, account_id: str):
        """Link account to user (create UserAccount junction record - no commit)"""
        # Check if link already exists
        result = await self.db.execute(
            select(UserAccount).where(
                UserAccount.user_id == user_id,
                UserAccount.account_id == account_id
            )
        )
        existing_link = result.scalar_one_or_none()

        if existing_link:
            logger.info(f"Account {account_id} already linked to user {user_id}")
            return

        # Check if user has any primary account
        result = await self.db.execute(
            select(UserAccount).where(
                UserAccount.user_id == user_id,
                UserAccount.is_primary == True
            )
        )
        has_primary = result.scalar_one_or_none() is not None

        # Create link (first account becomes primary)
        user_account = UserAccount(
            user_id=user_id,
            account_id=account_id,
            is_primary=not has_primary
        )
        self.db.add(user_account)
        # Note: No commit - relies on parent transaction

        logger.info(f"Linked account {account_id} to user {user_id} (primary: {not has_primary})")

    async def _sync_conversation_history(
        self,
        instagram_client: InstagramClient,
        account: Account
    ) -> int:
        """
        Sync conversation history from Instagram API.

        Returns:
            Number of conversations synced
        """
        try:
            # Fetch conversations from Instagram
            conversations = await instagram_client.get_conversations(limit=50)

            if not conversations:
                logger.info("No conversations returned from Instagram API (may not be supported)")
                return 0

            synced_count = 0

            for conv in conversations:
                # Extract conversation participants
                participants = conv.get("participants", {}).get("data", [])
                if not participants:
                    continue

                # DEBUG: Log participants to understand Instagram's ID usage
                participant_ids = [p.get("id") for p in participants]
                logger.info(f"🔍 Conversation {conv.get('id')[:20]}... participants: {participant_ids}")
                logger.info(f"   Business IDs: instagram_account_id={account.instagram_account_id}, messaging_channel_id={account.messaging_channel_id}")

                # Find which participant is the business account
                # Instagram conversations have exactly 2 participants: business account + customer
                # The business participant might use a different ID (messaging_channel_id) than the OAuth profile ID

                if len(participants) != 2:
                    logger.warning(f"⚠️ Unexpected participant count: {len(participants)}")
                    continue

                participant1_id = participants[0].get("id")
                participant2_id = participants[1].get("id")

                # Strategy: The business account is the participant that appears in ALL conversations
                # Since we know one of them MUST be the business account:
                # - If one matches our known business IDs (instagram_account_id or messaging_channel_id), that's it
                # - Otherwise, assume the first participant is the business (Instagram convention)

                business_participant_id = None
                customer_id = None

                # Check if either participant matches known business IDs
                if participant1_id in {account.instagram_account_id, account.messaging_channel_id}:
                    business_participant_id = participant1_id
                    customer_id = participant2_id
                elif participant2_id in {account.instagram_account_id, account.messaging_channel_id}:
                    business_participant_id = participant2_id
                    customer_id = participant1_id
                else:
                    # Neither matches - assume first is business (Instagram lists business account first)
                    logger.info(f"📝 Neither participant matches known business IDs, assuming participant 0 is business")
                    business_participant_id = participant1_id
                    customer_id = participant2_id

                # Update messaging_channel_id if we detected a different business ID
                # This handles the case where Instagram uses different IDs for OAuth vs messaging
                if business_participant_id != account.messaging_channel_id:
                    logger.info(f"📝 Updating messaging_channel_id from {account.messaging_channel_id} to {business_participant_id}")
                    account.messaging_channel_id = business_participant_id
                    # Note: Will be committed by parent transaction

                if not customer_id:
                    logger.warning(f"⚠️ Could not identify customer in conversation {conv.get('id')[:20]}")
                    continue

                customer = {"id": customer_id}

                # Cache customer profile
                await self._cache_customer_profile(
                    instagram_client,
                    customer_id
                )

                # Fetch and store messages for this conversation
                messages = await instagram_client.get_conversation_messages(
                    conv.get("id"),
                    limit=25
                )

                if messages:
                    await self._store_conversation_messages(
                        account,
                        customer_id,
                        messages
                    )
                    synced_count += 1

            logger.info(f"✅ Synced {synced_count} conversations from Instagram API")
            return synced_count

        except Exception as e:
            logger.warning(f"⚠️ Conversation sync failed (non-critical): {e}")
            return 0

    async def _cache_customer_profile(
        self,
        instagram_client: InstagramClient,
        customer_id: str
    ):
        """Cache customer profile in InstagramProfile table (no commit - relies on parent transaction)"""
        profile = await instagram_client.get_user_profile(customer_id)

        if not profile:
            return

        # Check if profile already cached
        result = await self.db.execute(
            select(InstagramProfile).where(InstagramProfile.sender_id == customer_id)
        )
        cached_profile = result.scalar_one_or_none()

        username = profile.get("username", "")
        profile_pic = profile.get("profile_picture_url")

        if cached_profile:
            # Update existing
            cached_profile.username = username
            cached_profile.profile_picture_url = profile_pic
            cached_profile.last_updated = datetime.now(timezone.utc)
        else:
            # Create new
            new_profile = InstagramProfile(
                sender_id=customer_id,
                username=username,
                profile_picture_url=profile_pic,
                last_updated=datetime.now(timezone.utc)
            )
            self.db.add(new_profile)

        # Note: No commit - relies on parent transaction

    async def _store_conversation_messages(
        self,
        account: Account,
        customer_id: str,
        messages: list[dict]
    ):
        """Store conversation messages in database (no commit - relies on parent transaction)"""
        for msg in messages:
            message_id = msg.get("id")
            message_text = msg.get("message")
            created_time = msg.get("created_time")
            from_data = msg.get("from", {})
            from_id = from_data.get("id")

            # Determine direction
            # Use messaging_channel_id for routing consistency with webhooks
            business_id = account.messaging_channel_id or account.instagram_account_id

            if from_id == account.instagram_account_id or from_id == business_id:
                direction = "outbound"
                sender_id = business_id
                recipient_id = customer_id
            else:
                direction = "inbound"
                sender_id = customer_id
                recipient_id = business_id

            # Check if message already exists
            result = await self.db.execute(
                select(MessageModel).where(MessageModel.id == message_id)
            )
            existing_message = result.scalar_one_or_none()

            if existing_message:
                continue  # Skip duplicates

            # Create message
            # Note: MessageModel expects plain strings, not value objects
            message = MessageModel(
                id=message_id,
                account_id=account.id,
                sender_id=sender_id,  # Plain string, not value object
                recipient_id=recipient_id,  # Plain string, not value object
                message_text=message_text or "",  # Ensure not None
                direction=direction,
                timestamp=datetime.fromisoformat(created_time.replace("Z", "+00:00")) if created_time else datetime.now(timezone.utc),
                delivery_status="sent"
            )
            self.db.add(message)

        # Note: No commit - relies on parent transaction
