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

from app.config import settings
from app.db.connection import get_db_session
from app.db.models import Account, User, UserAccount, OAuthState
from app.services.encryption_service import get_encryption_service
from app.api.auth import verify_ui_session
from app.application.account_linking_service import AccountLinkingService, OAuthResult
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

    Uses AccountLinkingService to handle OAuth flow, token exchange,
    account creation, and conversation history sync.

    Security:
    - Validates CSRF state token (one-time use)
    - Exchanges code for access token
    - Creates/updates account in database
    - Links to authenticated user from state token
    - Syncs conversation history from Instagram API
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
