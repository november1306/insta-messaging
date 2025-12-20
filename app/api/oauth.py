"""
OAuth API endpoints for Instagram Business Login.

Instagram Business Login Flow (2025):
1. User clicks embed URL → redirected to Instagram OAuth authorization page
2. User grants permissions → Instagram redirects to callback with authorization code
3. Exchange code for short-lived access token (1 hour) at api.instagram.com/oauth/access_token
4. Exchange short-lived token for long-lived token (60 days) at graph.instagram.com/access_token
5. Use token to fetch Instagram profile data at graph.instagram.com/{user_id}
6. Store encrypted token and account info in database

Key differences from Facebook Login:
- Uses Instagram-specific endpoints (api.instagram.com, graph.instagram.com)
- Returns Instagram user ID directly (no need to fetch Facebook pages)
- Uses ig_exchange_token grant type (not fb_exchange_token)
- Requires new scope format: instagram_business_* (old scopes deprecated Jan 27, 2025)

Reference: https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/business-login
"""
import httpx
import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, Query, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.db.connection import get_db_session
from app.db.models import Account, User, UserAccount, OAuthState
from app.services.encryption_service import get_encryption_service
import uuid
import secrets

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/instagram/init")
async def init_instagram_oauth(
    db: AsyncSession = Depends(get_db_session)
):
    """
    Initialize Instagram OAuth flow by generating a CSRF state token.

    NOTE: For proof-of-concept, this endpoint creates a temporary user.
    In production, this should require JWT authentication to get the real user_id.

    Returns:
        - state: CSRF token to include in OAuth URL
        - auth_url: Complete Instagram OAuth authorization URL
        - expires_at: When the state token expires (10 minutes)
    """
    # TODO: Replace with actual JWT authentication
    # For now, get or create a test user
    result = await db.execute(select(User).limit(1))
    user = result.scalar_one_or_none()

    if not user:
        # Create test user for POC
        import bcrypt
        password_hash = bcrypt.hashpw("password".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        user = User(
            username="admin",
            password_hash=password_hash,
            is_active=True
        )
        db.add(user)
        await db.flush()
        logger.info(f"Created test user: {user.username} (id={user.id})")

    # Generate cryptographically secure random state token
    state_token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(minutes=10)

    # Store state in database
    oauth_state = OAuthState(
        state=state_token,
        user_id=user.id,
        redirect_uri=settings.instagram_oauth_redirect_uri,
        created_at=datetime.utcnow(),
        expires_at=expires_at
    )
    db.add(oauth_state)
    await db.commit()

    logger.info(f"Generated OAuth state token for user {user.id}, expires at {expires_at}")

    # Build Instagram OAuth URL
    scopes = [
        "instagram_business_basic",
        "instagram_business_manage_messages",
        "instagram_business_content_publish",
        "instagram_business_manage_insights",
        "instagram_business_manage_comments"
    ]

    params = {
        "client_id": settings.instagram_oauth_client_id,
        "redirect_uri": settings.instagram_oauth_redirect_uri,
        "response_type": "code",
        "scope": " ".join(scopes),  # Space-separated per OAuth spec
        "state": state_token
    }

    # Build query string manually to ensure proper encoding
    from urllib.parse import urlencode
    query_string = urlencode(params)
    auth_url = f"https://www.instagram.com/oauth/authorize?{query_string}"

    return {
        "auth_url": auth_url,
        "expires_at": expires_at.isoformat()
    }


@router.get("/instagram/callback")
async def instagram_oauth_callback(
    code: str = Query(..., description="Authorization code from Instagram"),
    state: str = Query(..., description="CSRF state token (required)"),
    error: str = Query(None, description="Error from OAuth provider"),
    error_description: str = Query(None, description="Error description"),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Handle Instagram OAuth callback.

    Security:
    - Validates CSRF state token (one-time use)
    - Exchange code for access token
    - Get Instagram account info
    - Store account in database
    - Link to authenticated user from state token
    """
    try:
        logger.info("OAuth callback received")

        # Handle OAuth errors
        if error:
            logger.error(f"OAuth error from Instagram: {error} - {error_description}")
            return HTMLResponse(
                content=f"""
                <html>
                    <body style="font-family: Arial; padding: 40px; text-align: center;">
                        <h1 style="color: #e74c3c;">OAuth Error</h1>
                        <p><strong>Error:</strong> {error}</p>
                        <p><strong>Description:</strong> {error_description or 'No description provided'}</p>
                        <p><a href="/chat">Return to Chat</a></p>
                    </body>
                </html>
                """,
                status_code=400
            )

        # Validate CSRF state token
        result = await db.execute(
            select(OAuthState).where(OAuthState.state == state)
        )
        oauth_state = result.scalar_one_or_none()

        if not oauth_state:
            logger.error("Invalid OAuth state token")
            raise HTTPException(
                status_code=400,
                detail="Invalid OAuth state token. Please try again."
            )

        if oauth_state.expires_at < datetime.utcnow():
            logger.error("Expired OAuth state token")
            await db.delete(oauth_state)
            await db.commit()
            raise HTTPException(
                status_code=400,
                detail="OAuth state token expired. Please try again."
            )

        authenticated_user_id = oauth_state.user_id

        # Delete state token (one-time use)
        await db.delete(oauth_state)
        await db.commit()

        # Exchange authorization code for access token
        async with httpx.AsyncClient(timeout=30.0) as client:
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
                raise HTTPException(
                    status_code=400,
                    detail=f"Token exchange failed: {token_response.text}"
                )

            token_data = token_response.json()

            if "error_type" in token_data or "error" in token_data:
                error_msg = token_data.get("error_message") or token_data.get("error", {}).get("message", "Unknown error")
                logger.error(f"Token error: {error_msg}")
                raise HTTPException(status_code=400, detail=f"Token error: {error_msg}")

            # Instagram OAuth returns data array or flat object
            data_array = token_data.get("data", [])
            if not data_array or len(data_array) == 0:
                if "access_token" in token_data and "user_id" in token_data:
                    data = token_data
                else:
                    logger.error("Unexpected token response format")
                    raise HTTPException(
                        status_code=400,
                        detail="Unexpected token response format"
                    )
            else:
                data = data_array[0]

            short_lived_token = data.get("access_token")
            instagram_user_id = data.get("user_id")

            # Parse permissions
            permissions_raw = data.get("permissions", "")
            if isinstance(permissions_raw, list):
                permissions = permissions_raw
            elif isinstance(permissions_raw, str):
                permissions = permissions_raw.split(",") if permissions_raw else []
            else:
                permissions = []

            if not short_lived_token or not instagram_user_id:
                logger.error("Missing access token or user_id")
                raise HTTPException(status_code=400, detail="Invalid token response")

            # Exchange for long-lived token (60 days)
            long_lived_response = await client.get(
                "https://graph.instagram.com/access_token",
                params={
                    "grant_type": "ig_exchange_token",
                    "client_secret": settings.instagram_oauth_client_secret,
                    "access_token": short_lived_token
                }
            )

            if long_lived_response.status_code == 200:
                long_lived_data = long_lived_response.json()
                access_token = long_lived_data.get("access_token", short_lived_token)
                expires_in = long_lived_data.get("expires_in", 3600)
                token_type = "long-lived"
            else:
                access_token = short_lived_token
                expires_in = 3600
                token_type = "short-lived"
                logger.warning(f"Could not exchange for long-lived token: {long_lived_response.status_code}")

            token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

            # Get Instagram profile
            profile_response = await client.get(
                f"https://graph.instagram.com/{instagram_user_id}",
                params={
                    "fields": "id,username,name,profile_picture_url,followers_count,follows_count,media_count",
                    "access_token": access_token
                }
            )

            if profile_response.status_code != 200:
                logger.error(f"Failed to fetch Instagram profile: {profile_response.status_code}")
                raise HTTPException(
                    status_code=400,
                    detail="Failed to fetch Instagram profile"
                )

            instagram_account = profile_response.json()

        # Store account in database
        encryption = get_encryption_service(settings.session_secret)

        result = await db.execute(
            select(Account).where(Account.instagram_account_id == instagram_account["id"])
        )
        existing_account = result.scalar_one_or_none()

        if existing_account:
            existing_account.username = instagram_account.get("username", "")
            existing_account.access_token_encrypted = encryption.encrypt(access_token)
            existing_account.token_expires_at = token_expires_at
            existing_account.profile_picture_url = instagram_account.get("profile_picture_url")
            existing_account.last_synced_at = datetime.utcnow()
            account = existing_account
        else:
            account = Account(
                id=f"acc_{uuid.uuid4().hex[:12]}",
                instagram_account_id=instagram_account["id"],
                username=instagram_account.get("username", ""),
                access_token_encrypted=encryption.encrypt(access_token),
                token_expires_at=token_expires_at,
                profile_picture_url=instagram_account.get("profile_picture_url"),
                last_synced_at=datetime.utcnow(),
                crm_webhook_url=None,
                webhook_secret=None
            )
            db.add(account)

        # Link to authenticated user
        result = await db.execute(select(User).where(User.id == authenticated_user_id))
        user = result.scalar_one_or_none()

        if not user:
            logger.error(f"User {authenticated_user_id} not found")
            raise HTTPException(status_code=400, detail="Authentication failed: user not found")

        # Check if user-account link exists
        result = await db.execute(
            select(UserAccount).where(
                UserAccount.user_id == user.id,
                UserAccount.account_id == account.id
            )
        )
        link = result.scalar_one_or_none()

        if not link:
            link = UserAccount(
                user_id=user.id,
                account_id=account.id,
                role="owner",
                is_primary=True,
                linked_at=datetime.utcnow()
            )
            db.add(link)

        await db.commit()
        logger.info(f"Instagram account linked: @{account.username} -> user {user.username}")

        return HTMLResponse(
            content=f"""
            <html>
                <head>
                    <style>
                        body {{
                            font-family: Arial, sans-serif;
                            padding: 40px;
                            text-align: center;
                            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                            color: white;
                        }}
                        .container {{
                            background: white;
                            color: #333;
                            padding: 40px;
                            border-radius: 10px;
                            max-width: 600px;
                            margin: 0 auto;
                            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
                        }}
                        h1 {{ color: #27ae60; margin-bottom: 20px; }}
                        .account-info {{
                            background: #f8f9fa;
                            padding: 20px;
                            border-radius: 5px;
                            margin: 20px 0;
                            text-align: left;
                        }}
                        .account-info strong {{ color: #667eea; }}
                        a {{
                            display: inline-block;
                            background: #667eea;
                            color: white;
                            padding: 12px 30px;
                            text-decoration: none;
                            border-radius: 5px;
                            margin-top: 20px;
                        }}
                        a:hover {{ background: #764ba2; }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <h1>✅ Instagram Account Connected!</h1>
                        <p>Your Instagram Business Account has been successfully linked.</p>

                        <div class="account-info">
                            <p><strong>Username:</strong> @{instagram_account.get('username')}</p>
                            <p><strong>Name:</strong> {instagram_account.get('name', 'N/A')}</p>
                            <p><strong>Followers:</strong> {instagram_account.get('followers_count', 0):,}</p>
                            <p><strong>Following:</strong> {instagram_account.get('follows_count', 0):,}</p>
                            <p><strong>Posts:</strong> {instagram_account.get('media_count', 0):,}</p>
                            <p><strong>Account ID:</strong> {account.id}</p>
                            <p><strong>Instagram User ID:</strong> {instagram_user_id}</p>
                            <p><strong>Token Type:</strong> {token_type}</p>
                            <p><strong>Expires:</strong> {token_expires_at.strftime('%Y-%m-%d %H:%M UTC')}</p>
                            <p><strong>Permissions:</strong> {', '.join(permissions)}</p>
                        </div>

                        <p><strong>User:</strong> {user.username}</p>
                        <p>You can now send and receive Instagram messages!</p>

                        <a href="/chat">Go to Chat</a>
                    </div>
                </body>
            </html>
            """,
            status_code=200
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OAuth callback error: {type(e).__name__}: {str(e)}")
        return HTMLResponse(
            content=f"""
            <html>
                <body style="font-family: Arial; padding: 40px; text-align: center;">
                    <h1 style="color: #e74c3c;">❌ OAuth Error</h1>
                    <p><strong>Error:</strong> {str(e)}</p>
                    <p>Please check the logs for more details.</p>
                    <p><a href="/chat">Return to Chat</a></p>
                </body>
            </html>
            """,
            status_code=500
        )


