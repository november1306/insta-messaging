"""
Instagram Messenger Automation - Main Application Entry Point
"""
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, Request, status, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from app.api import webhooks, accounts, messages, ui, events, oauth
from app.config import settings
from app.db import init_db, close_db
from app.version import __version__
from app.services.media_cleanup import periodic_cleanup_task
import logging
from pathlib import Path
import aiomysql
import asyncio

# Custom logging filter to redact sensitive data
class SensitiveDataFilter(logging.Filter):
    """Filter to redact sensitive data from logs"""

    def filter(self, record):
        if hasattr(record, 'msg'):
            msg = str(record.msg)
            import re

            # Redact access tokens in URLs
            if 'access_token=' in msg:
                msg = msg.split('access_token=')[0] + 'access_token=[REDACTED]'

            # Redact JWT tokens
            if 'eyJ' in msg and 'token' in msg.lower():
                msg = re.sub(r'eyJ[A-Za-z0-9_-]*\.eyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*', '[JWT_REDACTED]', msg)

            # Redact Instagram message IDs and other long identifiers (80+ chars of alphanumeric)
            # These are typically base64-encoded IDs from Instagram Graph API
            msg = re.sub(r'\b[A-Za-z0-9_-]{80,}\b', '[ID_REDACTED]', msg)

            record.msg = msg
        return True

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Add filter to all loggers
for handler in logging.root.handlers:
    handler.addFilter(SensitiveDataFilter())

# Add filter to httpx logger (logs API requests)
httpx_logger = logging.getLogger('httpx')
httpx_logger.addFilter(SensitiveDataFilter())

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager - handles startup and shutdown"""
    # Startup
    logger.info("🚀 Starting Instagram Messenger Automation")
    logger.info(f"📦 Version: {__version__}")
    logger.info(f"📝 Environment: {settings.environment}")

    # Initialize database
    await init_db()

    # Create media directory for Instagram attachments
    media_dir = Path(__file__).parent.parent / "media"
    try:
        media_dir.mkdir(parents=True, exist_ok=True)
        # Create outbound subdirectory for temporary outbound media
        outbound_dir = media_dir / "outbound"
        outbound_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"✅ Media directory ready: {media_dir}")
        logger.info(f"✅ Outbound media directory ready: {outbound_dir}")
    except Exception as e:
        logger.error(f"❌ Failed to create media directory: {e}")
        # Non-fatal - will retry when first media is downloaded

    # Initialize CRM MySQL connection pool (if enabled)
    crm_pool = None
    if settings.crm_mysql_enabled:
        if not settings.crm_mysql_user or not settings.crm_mysql_password:
            logger.warning("CRM_MYSQL_ENABLED=true but credentials missing. CRM sync disabled.")
        else:
            try:
                crm_pool = await aiomysql.create_pool(
                    host=settings.crm_mysql_host,
                    user=settings.crm_mysql_user,
                    password=settings.crm_mysql_password,
                    db=settings.crm_mysql_database,
                    minsize=1,
                    maxsize=5,
                    pool_recycle=3600,  # Recycle connections after 1 hour
                    connect_timeout=30,  # 30 second connection timeout
                    ssl=None,  # Explicitly disable SSL (as per test command)
                    charset='utf8mb4'  # UTF-8 with full Unicode support (Cyrillic, emojis, etc.)
                )
                logger.info(f"✅ CRM MySQL connected: {settings.crm_mysql_host}/{settings.crm_mysql_database}")
            except Exception as e:
                logger.error(f"❌ CRM MySQL connection failed: {e}. CRM sync disabled.")
                crm_pool = None

    app.state.crm_pool = crm_pool

    # Start media cleanup background task
    cleanup_task = asyncio.create_task(periodic_cleanup_task(media_dir))
    logger.info("✅ Media cleanup task started")

    # Start OAuth state cleanup background task
    from app.services.oauth_cleanup import periodic_oauth_state_cleanup
    oauth_cleanup_task = asyncio.create_task(periodic_oauth_state_cleanup())
    logger.info("✅ OAuth state cleanup task started")

    logger.info("✅ Configuration loaded successfully")
    logger.info("🔗 Webhook endpoint: /webhooks/instagram")

    yield

    # Shutdown
    logger.info("Shutting down...")

    # Cancel cleanup tasks
    cleanup_task.cancel()
    oauth_cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        logger.info("✅ Media cleanup task cancelled")
    try:
        await oauth_cleanup_task
    except asyncio.CancelledError:
        logger.info("✅ OAuth state cleanup task cancelled")

    # Close CRM pool
    if crm_pool:
        crm_pool.close()
        await crm_pool.wait_closed()
        logger.info("✅ CRM MySQL pool closed")

    await close_db()


app = FastAPI(
    title="Instagram Messenger Automation",
    description="Automated Instagram DM responses and CRM integration for e-commerce",
    version=__version__,
    lifespan=lifespan,
    docs_url="/docs",  # Enable auto-generated Swagger UI
    redoc_url="/redoc",  # Enable auto-generated ReDoc
    openapi_url="/openapi.json"  # Enable auto-generated OpenAPI spec
)


# ============================================
# CORS Middleware Configuration
# ============================================
# Required for frontend development (different port) and production deployments
# where frontend may be served from different domain/CDN

# Development origins (local frontend dev server)
dev_origins = [
    "http://localhost:5173",  # Vite dev server
    "http://127.0.0.1:5173",
]

# Production origins (will be overridden by environment variable)
# Set CORS_ORIGINS env var as comma-separated list: "https://example.com,https://www.example.com"
production_origins = settings.cors_origins.split(",") if hasattr(settings, 'cors_origins') and settings.cors_origins else []

# Combine dev and production origins
allowed_origins = dev_origins + production_origins

# Add current host for built frontend
allowed_origins.append("http://localhost:8000")
allowed_origins.append("http://127.0.0.1:8000")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"],  # Allow all headers
    expose_headers=["*"],  # Expose all headers to frontend
)

logger.info(f"✅ CORS configured for origins: {allowed_origins}")


# Add validation error handler for debugging
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Log validation errors for debugging"""
    logger.error(f"Validation error for {request.method} {request.url.path}")
    logger.error(f"Request body: {await request.body()}")
    logger.error(f"Validation errors: {exc.errors()}")
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": exc.errors(),
            "body": exc.body
        }
    )

# Register webhook routes
app.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])

# Register CRM integration API routes
app.include_router(accounts.router, prefix="/api/v1", tags=["accounts"])
app.include_router(messages.router, prefix="/api/v1", tags=["messages"])

# Register UI API routes (for web frontend)
app.include_router(ui.router, prefix="/api/v1", tags=["ui"])
app.include_router(events.router, prefix="/api/v1", tags=["events"])

# Register OAuth routes
app.include_router(oauth.router, prefix="/oauth", tags=["oauth"])


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "app": "Instagram Messenger Automation",
        "version": __version__,
        "status": "running",
        "environment": settings.environment,
        "webhook_url": "/webhooks/instagram"
    }


@app.get("/health")
async def health_check():
    """
    Health check endpoint for CRM integration API.
    
    Minimal implementation for MVP (Priority 1):
    - Return status and timestamp
    - Skip dependency checks (will add in Priority 2)
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "environment": settings.environment
    }


# ============================================
# Media Files Serving (Instagram Attachments)
# ============================================

# Import authentication dependency for media endpoint
from app.api.auth import verify_jwt_or_api_key

# Serve media files with authentication (images, videos, audio, documents)
# Downloaded from Instagram CDN and stored locally at media/{account_id}/{sender_id}/
media_dir = Path(__file__).parent.parent / "media"

@app.get("/media/outbound/{account_id}/{filename}")
async def serve_outbound_media(
    account_id: str,
    filename: str
):
    """
    Serve outbound media files - PUBLIC (no authentication required).

    Instagram Graph API requires publicly accessible URLs to fetch media attachments.
    These files are temporary (24-hour TTL) and stored in media/outbound/{account_id}/

    Path format: /media/outbound/{account_id}/{filename}
    Example: /media/outbound/page456/uuid_timestamp.jpg

    Security:
    - Files have random UUID filenames (not guessable)
    - 24-hour automatic deletion limits exposure window
    - Path traversal protection
    """
    # Construct file path
    file_path = media_dir / "outbound" / account_id / filename

    if not file_path.exists():
        logger.warning(f"Outbound media file not found: {file_path}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Media file not found or expired"
        )

    # Security: Verify the resolved path is still within outbound media directory
    # Prevents path traversal attacks
    outbound_dir = media_dir / "outbound"
    try:
        file_path.resolve().relative_to(outbound_dir.resolve())
    except ValueError:
        logger.error(f"Path traversal attempt detected in outbound media: {file_path}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid file path"
        )

    logger.debug(f"Serving outbound media file (public): {file_path}")

    # Return file for Instagram to fetch
    return FileResponse(file_path)


@app.get("/media/{account_id}/{sender_id}/{filename}")
async def serve_media(
    account_id: str,
    sender_id: str,
    filename: str,
    download: bool = False,
    auth_context: dict = Depends(verify_jwt_or_api_key)
):
    """
    Serve media files with authentication.

    Requires valid JWT token or API key. Users can only access media from
    their authenticated account to prevent unauthorized access to private
    Instagram DM attachments.

    Path format: /media/{account_id}/{sender_id}/{filename}
    Example: /media/page456/user123/mid_abc123_0.jpg

    Query parameters:
        download: If True, force download with Content-Disposition: attachment
    """
    # Verify user has access to this account's media
    # JWT tokens contain account_id, API keys have broader access
    if auth_context.get("auth_type") == "jwt":
        user_account_id = auth_context.get("account_id")
        if user_account_id != account_id:
            logger.warning(
                f"Unauthorized media access attempt: user account {user_account_id} "
                f"tried to access media from account {account_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to access this media"
            )
    # API keys have access to all accounts (for CRM integration)

    # Construct file path and verify it exists
    file_path = media_dir / account_id / sender_id / filename

    if not file_path.exists():
        logger.warning(f"Media file not found: {file_path}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Media file not found"
        )

    # Security: Verify the resolved path is still within media directory
    # Prevents path traversal attacks (e.g., ../../../etc/passwd)
    try:
        file_path.resolve().relative_to(media_dir.resolve())
    except ValueError:
        logger.error(f"Path traversal attempt detected: {file_path}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid file path"
        )

    # Determine if file should be downloaded vs previewed
    # File attachments (PDFs, docs, etc.) should download by default
    # Images/videos can be previewed in browser
    file_extension = file_path.suffix.lower()
    downloadable_extensions = {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt', '.zip', '.rar', '.7z'}

    # Force download if explicitly requested OR if it's a file attachment type
    should_download = download or (file_extension in downloadable_extensions)

    logger.debug(f"Serving media file: {file_path} (auth: {auth_context.get('auth_type')}, download: {should_download})")

    if should_download:
        # Force download with proper filename
        return FileResponse(
            file_path,
            filename=filename,
            media_type='application/octet-stream'
        )
    else:
        # Allow browser to preview (images, videos, audio)
        return FileResponse(file_path)

# Media endpoint info logged at startup
logger.info(f"✅ Authenticated media endpoint enabled at /media/{{account_id}}/{{sender_id}}/{{filename}}")


# ============================================
# Frontend Web UI (Vue.js SPA)
# ============================================

# Serve frontend static files (after npm run build)
frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"

if frontend_dist.exists():
    # Mount static assets
    app.mount(
        "/chat/assets",
        StaticFiles(directory=str(frontend_dist / "assets")),
        name="chat-assets"
    )

    logger.info(f"✅ Frontend assets mounted at /chat/assets")

    @app.get("/chat", include_in_schema=False)
    @app.get("/chat/{full_path:path}", include_in_schema=False)
    async def serve_frontend(full_path: str = ""):
        """Serve the Vue.js frontend SPA"""
        return FileResponse(frontend_dist / "index.html")
else:
    logger.warning(
        f"⚠️  Frontend not built. Run 'cd frontend && npm run build' to enable /chat UI. "
        f"For development, run 'cd frontend && npm run dev' separately."
    )
