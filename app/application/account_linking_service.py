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

from app.db.models import Account, UserAccount, User, OAuthState
from app.clients.instagram_client import InstagramClient
from app.services.encryption_service import get_encryption_service
from app.application.instagram_sync_service import InstagramSyncService
from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class OAuthResult:
    """Result of OAuth flow"""
    success: bool
    account: Optional[Account] = None
    error_message: Optional[str] = None
    conversations_synced: int = 0
    redirect_url: Optional[str] = None  # Frontend URL to redirect to after OAuth


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
        frontend_redirect_url: Optional[str] = None,
        force_reauth: bool = False
    ) -> tuple[str, datetime]:
        """
        Initialize OAuth flow for a user.

        Args:
            user_id: Authenticated user ID
            frontend_redirect_url: Where to redirect frontend after OAuth completes
                                   (e.g., http://localhost:5173 for local dev)
                                   Defaults to settings.frontend_url if not provided
            force_reauth: Force user to reauth (for linking multiple accounts)

        Returns:
            Tuple of (auth_url, expires_at)
        """
        # Generate CSRF token
        state = secrets.token_urlsafe(32)

        # Use provided frontend URL or default to settings
        final_redirect_url = frontend_redirect_url or settings.frontend_url

        # Store state in database
        now = datetime.now(timezone.utc)
        oauth_state = OAuthState(
            state=state,
            user_id=user_id,
            redirect_uri=final_redirect_url,  # Frontend redirect URL (not OAuth callback)
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

        # ⚠️ DO NOT CHANGE THIS - force_reauth=true is the correct Instagram OAuth parameter
        # Meta uses this exact parameter in their own Developer Dashboard embed URLs
        # Do NOT use auth_type=rerequest (that's Facebook-only, for re-requesting declined permissions)
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
            frontend_redirect_url = oauth_state.redirect_uri  # Save before deletion

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
                sync_service = InstagramSyncService(self.db, instagram_client)
                sync_result = await sync_service.sync_account(account, hours_back=24)
                conversations_synced = sync_result.conversations_synced

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
                    conversations_synced=conversations_synced,
                    redirect_url=frontend_redirect_url
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
            # Note: Do NOT set messaging_channel_id here - let webhook binding set the correct value
            # The instagram_account_id (from OAuth) can differ from messaging_channel_id (from webhooks)
            logger.info(f"Updated existing account: {account.id}")
        else:
            # Create new account
            account = Account(
                id=f"acc_{uuid.uuid4().hex[:12]}",
                instagram_account_id=instagram_account_id,
                messaging_channel_id=None,  # Let webhook binding or conversation sync set the correct value
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

        # Create link (no primary concept - frontend manages account selection)
        user_account = UserAccount(
            user_id=user_id,
            account_id=account_id
        )
        self.db.add(user_account)
        # Note: No commit - relies on parent transaction

        logger.info(f"Linked account {account_id} to user {user_id}")
