"""
OAuth API endpoints for Instagram Business Login (Instagram Platform API).

Instagram Business Login Flow (2025 - NO Facebook Page Required!):
1. User clicks "Connect Instagram" → redirected to Instagram OAuth authorization page
2. User grants permissions → Instagram redirects to callback with authorization code
3. Exchange code for short-lived access token (1 hour) at api.instagram.com/oauth/access_token
4. Exchange short-lived token for long-lived token (60 days) at graph.instagram.com/access_token
5. Fetch Instagram account details at graph.instagram.com/me (includes id, username, account_type)
6. Store encrypted token and account info in database

Key Features:
- ✅ NO Facebook Page required (Instagram Business Login method)
- ✅ Direct Instagram authentication - no Facebook infrastructure needed
- ✅ OAuth user_id = Business Account ID (same ID used in webhooks)
- ✅ Supports Business and Creator accounts (rejects Personal accounts)
- ✅ Uses graph.instagram.com API (NOT graph.facebook.com)

Scopes Required:
- instagram_business_basic (required)
- instagram_business_manage_messages (for DM automation)
- instagram_business_content_publish (for content posting)
- instagram_business_manage_insights (for analytics)
- instagram_business_manage_comments (for comment management)

References:
- Official Guide: https://gist.github.com/PrenSJ2/0213e60e834e66b7e09f7f93999163fc
- Meta Docs: https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/business-login
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
from app.api.auth import verify_ui_session
import uuid
import secrets
from pydantic import BaseModel

router = APIRouter()
logger = logging.getLogger(__name__)


def create_oauth_error_html(title: str, message: str, details: str = None) -> str:
    """
    Create a consistent HTML error page for OAuth failures.

    Args:
        title: Error title (e.g., "Authentication Failed")
        message: Main error message
        details: Optional additional details

    Returns:
        HTML string for error page
    """
    details_html = f"<p style='color: #666;'>{details}</p>" if details else ""

    return f"""
    <html>
        <head>
            <title>{title}</title>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
                    padding: 40px;
                    text-align: center;
                    background-color: #f5f5f5;
                }}
                .container {{
                    max-width: 600px;
                    margin: 0 auto;
                    background: white;
                    padding: 40px;
                    border-radius: 8px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }}
                h1 {{
                    color: #e74c3c;
                    margin-bottom: 20px;
                }}
                p {{
                    color: #333;
                    line-height: 1.6;
                    margin: 15px 0;
                }}
                a {{
                    display: inline-block;
                    margin-top: 20px;
                    padding: 12px 24px;
                    background-color: #3498db;
                    color: white;
                    text-decoration: none;
                    border-radius: 4px;
                    transition: background-color 0.2s;
                }}
                a:hover {{
                    background-color: #2980b9;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>{title}</h1>
                <p>{message}</p>
                {details_html}
                <a href="{settings.frontend_url}/chat/">Return to Chat</a>
            </div>
        </body>
    </html>
    """


class OAuthInitRequest(BaseModel):
    """Request body for OAuth initialization"""
    force_reauth: bool = False


@router.post("/instagram/init")
async def init_instagram_oauth(
    request: OAuthInitRequest,
    session: dict = Depends(verify_ui_session),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Initialize Instagram OAuth flow by generating a CSRF state token.

    Requires JWT authentication - user must be logged in before initiating OAuth flow.

    Args:
        request: OAuth initialization parameters (force_reauth: bool)

    Returns:
        - state: CSRF token to include in OAuth URL
        - auth_url: Complete Instagram OAuth authorization URL
        - expires_at: When the state token expires (10 minutes)
    """
    # Get authenticated user from JWT session
    user_id = session.get("user_id")

    if not user_id:
        logger.error("OAuth init failed: Missing user_id in session")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session: missing user_id. Please login again."
        )

    # Query user from database
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        logger.error(f"OAuth init failed: User {user_id} not found")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session: user not found. Please login again."
        )

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
    # Using Instagram Business Login (2024+) - NO Facebook Page required!
    # Reference: https://gist.github.com/PrenSJ2/0213e60e834e66b7e09f7f93999163fc
    scopes = [
        "instagram_business_basic",
        "instagram_business_manage_messages",
        "instagram_business_content_publish",
        "instagram_business_manage_insights",
        "instagram_business_manage_comments"
        # NOTE: pages_read_engagement is NOT needed for Instagram Business Login!
    ]

    params = {
        "client_id": settings.instagram_oauth_client_id,
        "redirect_uri": settings.instagram_oauth_redirect_uri,
        "response_type": "code",
        "scope": " ".join(scopes),  # Space-separated per OAuth spec
        "state": state_token
    }

    # Add force_reauth if requested (for linking multiple accounts or switching accounts)
    if request.force_reauth:
        params["force_reauth"] = "true"

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
                        <p><a href="{settings.frontend_url}/chat/">Return to Chat</a></p>
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
            return HTMLResponse(
                content=create_oauth_error_html(
                    title="Invalid State Token",
                    message="The OAuth state token is invalid or has already been used.",
                    details="Please return to the app and try connecting your Instagram account again."
                ),
                status_code=400
            )

        if oauth_state.expires_at < datetime.utcnow():
            logger.error("Expired OAuth state token")
            await db.delete(oauth_state)
            await db.commit()
            return HTMLResponse(
                content=create_oauth_error_html(
                    title="Session Expired",
                    message="The OAuth session has expired (10-minute timeout).",
                    details="Please return to the app and start the Instagram connection process again."
                ),
                status_code=400
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
                return HTMLResponse(
                    content=create_oauth_error_html(
                        title="Token Exchange Failed",
                        message="Failed to exchange authorization code for access token.",
                        details="Instagram rejected the token request. Please try again or contact support if the issue persists."
                    ),
                    status_code=400
                )

            token_data = token_response.json()

            # Log sanitized token response (SECURITY: Never log access tokens)
            sanitized_token_data = {
                k: '[REDACTED]' if k in ['access_token', 'user_id'] else v
                for k, v in token_data.items()
            }
            logger.info(f"Instagram OAuth token response: {sanitized_token_data}")

            if "error_type" in token_data or "error" in token_data:
                error_msg = token_data.get("error_message") or token_data.get("error", {}).get("message", "Unknown error")
                logger.error(f"Token error: {error_msg}")
                return HTMLResponse(
                    content=create_oauth_error_html(
                        title="Instagram Error",
                        message="Instagram returned an error during authentication.",
                        details=f"Error: {error_msg}"
                    ),
                    status_code=400
                )

            # Instagram OAuth returns data array or flat object
            data_array = token_data.get("data", [])
            if not data_array or len(data_array) == 0:
                if "access_token" in token_data and "user_id" in token_data:
                    data = token_data
                else:
                    logger.error("Unexpected token response format")
                    return HTMLResponse(
                        content=create_oauth_error_html(
                            title="Invalid Response",
                            message="Instagram returned an unexpected response format.",
                            details="The OAuth token response was not in the expected format. Please try again."
                        ),
                        status_code=400
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
                return HTMLResponse(
                    content=create_oauth_error_html(
                        title="Missing Credentials",
                        message="Instagram did not provide required authentication credentials.",
                        details="The access token or user ID was missing from Instagram's response. Please try again."
                    ),
                    status_code=400
                )

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

            # Fetch Instagram Business Account details using Instagram Business Login (2024+)
            # With this method, the user_id from OAuth IS the business account ID!
            # No Facebook Pages needed - direct access to Instagram account
            # Reference: https://gist.github.com/PrenSJ2/0213e60e834e66b7e09f7f93999163fc

            logger.info(f"Fetching Instagram account details for user_id: {instagram_user_id}")

            # Fetch account details from graph.instagram.com (NOT graph.facebook.com!)
            ig_response = await client.get(
                f"https://graph.instagram.com/me",
                params={
                    "fields": "id,username,name,profile_picture_url,followers_count,media_count,account_type",
                    "access_token": access_token
                }
            )

            if ig_response.status_code != 200:
                logger.error(f"Failed to fetch Instagram account details: {ig_response.status_code} - {ig_response.text}")
                return HTMLResponse(
                    content=create_oauth_error_html(
                        title="Account Fetch Failed",
                        message="Could not retrieve your Instagram account information.",
                        details="Instagram API did not respond correctly. Please try again or contact support."
                    ),
                    status_code=400
                )

            ig_data = ig_response.json()

            # The 'id' from Instagram API is the business account ID (same as user_id from OAuth)
            business_account_id = ig_data.get("id")
            username = ig_data.get("username")
            profile_pic = ig_data.get("profile_picture_url")
            account_type = ig_data.get("account_type", "UNKNOWN")  # BUSINESS, CREATOR, or PERSONAL

            # Log account details for debugging
            logger.info(
                f"Instagram account fetched: @{username}, "
                f"ID={business_account_id}, "
                f"Type={account_type}, "
                f"OAuth user_id={instagram_user_id}"
            )

            # Verify IDs match (they should be identical for Instagram Business Login)
            if business_account_id != str(instagram_user_id):
                logger.warning(
                    f"ID mismatch! OAuth user_id={instagram_user_id} != "
                    f"API account ID={business_account_id}. Using API ID."
                )

            # Validate account type - reject personal accounts
            if account_type == "PERSONAL":
                logger.error(f"Personal account rejected: @{username} (ID: {business_account_id})")
                return HTMLResponse(
                    content=f"""
                    <html>
                        <head>
                            <style>
                                body {{
                                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
                                    padding: 40px;
                                    text-align: center;
                                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                                    color: white;
                                    margin: 0;
                                }}
                                .container {{
                                    background: white;
                                    color: #333;
                                    padding: 40px;
                                    border-radius: 10px;
                                    max-width: 700px;
                                    margin: 0 auto;
                                    box-shadow: 0 10px 40px rgba(0,0,0,0.2);
                                }}
                                h1 {{ color: #e74c3c; margin-bottom: 20px; }}
                                .error-box {{
                                    background: #fee;
                                    border: 2px solid #e74c3c;
                                    color: #c0392b;
                                    padding: 20px;
                                    border-radius: 5px;
                                    margin: 20px 0;
                                }}
                                .button {{
                                    display: inline-block;
                                    background: #667eea;
                                    color: white;
                                    padding: 12px 30px;
                                    text-decoration: none;
                                    border-radius: 5px;
                                    margin-top: 20px;
                                }}
                                .button:hover {{ background: #764ba2; }}
                            </style>
                        </head>
                        <body>
                            <div class="container">
                                <h1>❌ Business Account Required</h1>
                                <div class="error-box">
                                    <p>Your Instagram account (@{username}) is a <strong>Personal Account</strong>.</p>
                                    <p>This app requires a <strong>Business</strong> or <strong>Creator</strong> account.</p>
                                </div>

                                <h3>How to Convert to Business Account:</h3>
                                <ol style="text-align: left; max-width: 500px; margin: 20px auto;">
                                    <li>Open Instagram app → Go to your profile</li>
                                    <li>Tap menu (☰) → Settings → Account</li>
                                    <li>Tap "Switch to Professional Account"</li>
                                    <li>Choose <strong>Business</strong> or <strong>Creator</strong></li>
                                    <li>Complete the setup</li>
                                    <li>Return here and try connecting again</li>
                                </ol>

                                <p style="margin-top: 30px;">
                                    <a href="https://help.instagram.com/502981923235522" target="_blank">
                                        Instagram Help: Convert to Business Account
                                    </a>
                                </p>

                                <a href="{settings.frontend_url}/chat/" class="button">
                                    Return to Chat
                                </a>
                            </div>
                        </body>
                    </html>
                    """,
                    status_code=400
                )

            if not username or not business_account_id:
                raise HTTPException(
                    status_code=400,
                    detail="Failed to fetch Instagram account username or ID"
                )

            instagram_account = {
                "id": business_account_id,  # Instagram Business Account ID
                "user_id": instagram_user_id,  # OAuth user ID (should be same as id)
                "username": username,
                "profile_picture_url": profile_pic,
                "account_type": account_type.lower()  # 'business', 'creator', or 'personal'
            }

            logger.info(
                f"Successfully linked Instagram account: @{username} "
                f"(ID: {business_account_id}, Type: {account_type})"
            )

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
            existing_account.account_type = instagram_account.get("account_type")  # Store for debugging
            account = existing_account
        else:
            account = Account(
                id=f"acc_{uuid.uuid4().hex[:12]}",
                instagram_account_id=instagram_account["id"],  # Business account ID
                username=instagram_account.get("username", ""),
                access_token_encrypted=encryption.encrypt(access_token),
                token_expires_at=token_expires_at,
                profile_picture_url=instagram_account.get("profile_picture_url"),
                account_type=instagram_account.get("account_type"),  # Store for debugging
                crm_webhook_url=None,
                webhook_secret=None
            )
            db.add(account)

        # Link to authenticated user
        result = await db.execute(select(User).where(User.id == authenticated_user_id))
        user = result.scalar_one_or_none()

        if not user:
            logger.error(f"User {authenticated_user_id} not found")
            return HTMLResponse(
                content=create_oauth_error_html(
                    title="User Not Found",
                    message="The user account associated with this OAuth session could not be found.",
                    details="Your session may have expired. Please log in again and try connecting your Instagram account."
                ),
                status_code=400
            )

        # Check if user-account link already exists (prevent duplicates)
        result = await db.execute(
            select(UserAccount).where(
                UserAccount.user_id == user.id,
                UserAccount.account_id == account.id
            )
        )
        existing_link = result.scalar_one_or_none()

        if existing_link:
            # Account already linked - just updated token, don't create duplicate
            logger.info(f"Account @{account.username} already linked to user {user.username}, updated token")
        else:
            # Create new user-account link
            # Check if user has any existing primary accounts
            result = await db.execute(
                select(UserAccount).where(
                    UserAccount.user_id == user.id,
                    UserAccount.is_primary == True
                )
            )
            has_primary = result.scalar_one_or_none() is not None

            # Only set as primary if user has no other primary account
            link = UserAccount(
                user_id=user.id,
                account_id=account.id,
                is_primary=not has_primary,  # First account becomes primary
                linked_at=datetime.utcnow()
            )
            db.add(link)
            logger.info(f"Linked Instagram account: @{account.username} -> user {user.username}")

        await db.commit()

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
                        .button {{
                            display: inline-block;
                            background: #667eea;
                            color: white;
                            padding: 12px 30px;
                            text-decoration: none;
                            border-radius: 5px;
                            margin-top: 20px;
                            cursor: pointer;
                            border: none;
                            font-size: 16px;
                        }}
                        .button:hover {{ background: #764ba2; }}
                        .note {{
                            background: #fff3cd;
                            border: 1px solid #ffc107;
                            color: #856404;
                            padding: 10px;
                            border-radius: 5px;
                            margin: 15px 0;
                            font-size: 14px;
                        }}
                    </style>
                    <script>
                        function refreshSession() {{
                            // Clear old session from localStorage
                            localStorage.removeItem('session_token');
                            localStorage.removeItem('session_account_id');
                            localStorage.removeItem('session_expires_at');

                            // Redirect to frontend chat
                            window.location.href = '{settings.frontend_url}/chat/';
                        }}

                        // Auto-refresh after 3 seconds
                        setTimeout(refreshSession, 3000);
                    </script>
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

                        <div class="note">
                            <strong>Note:</strong> Refreshing your session to load the new account...
                        </div>

                        <p>Redirecting in 3 seconds, or click below to continue:</p>
                        <button class="button" onclick="refreshSession()">Continue to Chat</button>
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
                    <p><a href="{settings.frontend_url}/chat/">Return to Chat</a></p>
                </body>
            </html>
            """,
            status_code=500
        )


