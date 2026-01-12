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
from fastapi import APIRouter, Query, HTTPException, Depends, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field

from app.config import settings
from app.db.connection import get_db_session
from app.db.models import Account, User, UserAccount, OAuthState
from app.services.encryption_service import get_encryption_service
from app.api.auth import verify_ui_session, verify_jwt_or_api_key
from app.application.account_linking_service import AccountLinkingService, OAuthResult
import uuid
import secrets

router = APIRouter()
logger = logging.getLogger(__name__)


# ============================================
# Response Models
# ============================================

class OAuthInitResponse(BaseModel):
    """OAuth initialization response"""
    auth_url: str = Field(
        ...,
        example="https://api.instagram.com/oauth/authorize?client_id=123&redirect_uri=...&scope=instagram_business_basic...",
        description="Complete Instagram OAuth authorization URL to redirect user to"
    )
    expires_at: str = Field(
        ...,
        example="2026-01-06T14:42:00.123Z",
        description="When the state token expires (10 minutes from now)"
    )

    class Config:
        from_attributes = True


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
                <a href="{settings.frontend_url}">Return to Chat</a>
            </div>
        </body>
    </html>
    """


def create_oauth_success_html(account: Account, conversations_synced: int = 0) -> str:
    """
    Create a consistent HTML success page for OAuth completion.

    Args:
        account: The linked Instagram account
        conversations_synced: Number of conversations synced from Instagram (0 if not synced)

    Returns:
        HTML string for success page
    """
    sync_info = ""
    if conversations_synced > 0:
        sync_info = f"""
        <div class="note" style="background: #d4edda; border-color: #c3e6cb; color: #155724;">
            <strong>✅ Conversation History Synced!</strong><br>
            We imported {conversations_synced} conversation{'s' if conversations_synced != 1 else ''} from your Instagram account.
            You can start messaging right away!
        </div>
        """

    return f"""
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
                    window.location.href = '{settings.frontend_url}';
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
                    <p><strong>Username:</strong> @{account.username}</p>
                    <p><strong>Account ID:</strong> {account.id}</p>
                    <p><strong>Account Type:</strong> {account.account_type}</p>
                </div>

                {sync_info}

                <div class="note">
                    <strong>Note:</strong> Refreshing your session to load the new account...
                </div>

                <p>Redirecting in 3 seconds, or click below to continue:</p>
                <button class="button" onclick="refreshSession()">Continue to Chat</button>
            </div>
        </body>
    </html>
    """


class OAuthInitRequest(BaseModel):
    """Request body for OAuth initialization"""
    force_reauth: bool = False


@router.post(
    "/instagram/init",
    response_model=OAuthInitResponse,
    summary="Initialize Instagram OAuth flow (Step 1/3)",
    responses={
        200: {"description": "OAuth initialization successful, redirect user to auth_url"},
        401: {"description": "User not authenticated (JWT required)"}
    }
)
async def init_instagram_oauth(
    request: OAuthInitRequest,
    auth: dict = Depends(verify_jwt_or_api_key),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Initialize Instagram OAuth flow by generating authorization URL.

    ## OAuth Flow Overview (3 Steps)

    1. **Initialize** (this endpoint): Get authorization URL
    2. **Redirect User**: Send user to authorization URL (Instagram login page)
    3. **Callback**: Instagram redirects back with code → we exchange for token

    ## Requirements

    - **JWT Authentication Required**: User must be logged in first
    - **Instagram Business Account**: Personal accounts not supported (must convert to Business/Creator)
    - **No Facebook Page Required**: Uses Instagram Business Login (2025 method)

    ## Permissions Requested

    - `instagram_business_basic` - View profile info
    - `instagram_business_manage_messages` - Send/receive DMs
    - `instagram_business_content_publish` - Post content
    - `instagram_business_manage_insights` - View analytics
    - `instagram_business_manage_comments` - Manage comments

    ## Security (CSRF Protection)

    We generate a random `state` token that:
    - Prevents CSRF attacks
    - Links OAuth callback to correct user session
    - Expires after 10 minutes (check `expires_at`)
    - One-time use only (deleted after callback)

    ## Example Frontend Flow

    ```javascript
    // 1. Get authorization URL
    const response = await fetch('/oauth/instagram/init', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${jwt_token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ force_reauth: false })
    });

    const { auth_url, expires_at } = await response.json();

    // 2. Redirect user to Instagram login
    window.location.href = auth_url;

    // 3. User authorizes → Instagram redirects to callback
    // 4. Callback handles token exchange and account linking
    // 5. User is redirected back to your app with success message
    ```

    ## When to Use `force_reauth`

    - `false` (default): If user already authorized, Instagram may skip login
    - `true`: Force user to re-login and re-authorize even if previously connected

    Use `force_reauth: true` when:
    - User wants to switch to different Instagram account
    - Previous authorization was revoked
    - Testing OAuth flow during development

    **Accepts both JWT session tokens and API keys.**
    """
    # Get authenticated user from JWT or API key
    user_id = auth.get("user_id")

    if not user_id:
        logger.error("OAuth init failed: Missing user_id in session")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session: missing user_id. Please login again."
        )

    # Query user from database to verify existence
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        logger.error(f"OAuth init failed: User {user_id} not found")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session: user not found. Please login again."
        )

    # Use account linking service to initialize OAuth
    service = AccountLinkingService(db)
    auth_url, expires_at = await service.initialize_oauth(
        user_id=user.id,
        redirect_uri=settings.instagram_oauth_redirect_uri,
        force_reauth=request.force_reauth
    )

    return OAuthInitResponse(
        auth_url=auth_url,
        expires_at=expires_at.isoformat()
    )


@router.get(
    "/instagram/callback",
    summary="Instagram OAuth callback (Step 3/3)"
)
async def instagram_oauth_callback(
    code: str = Query(..., description="Authorization code from Instagram"),
    state: str = Query(..., description="CSRF state token (required)"),
    error: str = Query(None, description="Error from OAuth provider"),
    error_description: str = Query(None, description="Error description"),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Handle Instagram OAuth callback.

    Instagram redirects the user here after they authorize your app. This endpoint:
    1. Validates CSRF state token (security check)
    2. Exchanges authorization code for access token
    3. Fetches Instagram account details
    4. Creates/updates account in database
    5. Links account to user
    6. Syncs conversation history from Instagram API
    7. Displays success page with auto-redirect

    ## How It Works

    After user clicks "Authorize" on Instagram:
    ```
    Instagram redirects to:
    https://your-domain.com/oauth/instagram/callback?code=ABC123&state=xyz789

    We process:
    1. Validate state token (prevent CSRF attacks)
    2. Exchange code for short-lived token (1 hour)
    3. Exchange for long-lived token (60 days)
    4. Fetch account details (username, profile pic, account type)
    5. Store encrypted token in database
    6. Sync existing conversation history (optional)
    7. Show success HTML page → auto-redirect to chat UI
    ```

    ## Response Types

    **Success** (200 OK - HTML):
    - Beautiful success page with account details
    - JavaScript auto-refresh after 3 seconds
    - Clears old session from localStorage
    - Redirects to chat UI

    **Error** (400/500 - HTML):
    - User-friendly error page explaining what went wrong
    - "Return to Chat" button
    - Error details for debugging

    ## Common Errors

    **"Invalid or expired state token"**:
    - State token expired (10 minutes max)
    - User already used this state token
    - CSRF attack attempted

    **"Authorization code has expired"**:
    - User took too long on Instagram's auth page
    - Code already exchanged
    - Ask user to try again

    **"Personal accounts not supported"**:
    - User tried to link Instagram Personal account
    - Need to convert to Business or Creator account first

    **"Token exchange failed"**:
    - Instagram API error
    - Invalid app credentials
    - Check `INSTAGRAM_CLIENT_ID` and `INSTAGRAM_CLIENT_SECRET`

    ## Why HTML Response?

    This endpoint returns HTML (not JSON) because:
    - User is redirected here from Instagram's web page
    - Displays user-friendly success/error messages
    - Auto-refreshes frontend to load new account
    - Provides "Return to Chat" button for manual navigation
    """
    # Handle OAuth errors from Instagram
    if error:
        logger.error(f"OAuth error from Instagram: {error} - {error_description}")
        return HTMLResponse(
            content=create_oauth_error_html(
                title="OAuth Error",
                message=error,
                details=error_description or "No description provided"
            ),
            status_code=400
        )

    try:
        # Use account linking service to handle callback
        service = AccountLinkingService(db)
        result: OAuthResult = await service.handle_oauth_callback(code, state)

        if not result.success:
            # Service returned error
            return HTMLResponse(
                content=create_oauth_error_html(
                    title="Account Linking Failed",
                    message=result.error_message or "Unknown error occurred during account linking"
                ),
                status_code=400
            )

        # Success - return success HTML with conversation sync info
        return HTMLResponse(
            content=create_oauth_success_html(
                account=result.account,
                conversations_synced=result.conversations_synced
            ),
            status_code=200
        )

    except Exception as e:
        logger.error(f"OAuth callback error: {type(e).__name__}: {str(e)}", exc_info=True)
        return HTMLResponse(
            content=create_oauth_error_html(
                title="Unexpected Error",
                message="An unexpected error occurred during account linking",
                details=f"Error: {str(e)}"
            ),
            status_code=500
        )
