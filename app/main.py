"""
Instagram Messenger Automation - Main Application Entry Point
"""
from contextlib import asynccontextmanager
from functools import wraps
from datetime import datetime, timezone
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from app.api import webhooks, accounts, messages, ui, events
from app.config import settings
from app.db import init_db, close_db
from app.version import __version__
import logging
import yaml
from pathlib import Path
import aiomysql

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# OpenAPI spec - loaded during startup
openapi_spec = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager - handles startup and shutdown"""
    global openapi_spec
    
    # Startup
    logger.info("🚀 Starting Instagram Messenger Automation")
    logger.info(f"📦 Version: {__version__}")
    logger.info(f"📝 Environment: {settings.environment}")
    
    # Load OpenAPI spec from file (fail gracefully if missing)
    openapi_spec_path = Path(__file__).parent / "static" / "openapi.yaml"
    try:
        with open(openapi_spec_path, "r", encoding="utf-8") as f:
            openapi_spec = yaml.safe_load(f)
        logger.info(f"✅ Loaded OpenAPI spec from {openapi_spec_path}")
    except FileNotFoundError:
        logger.warning(
            f"⚠️  OpenAPI spec not found at {openapi_spec_path}. "
            f"/docs endpoint will not be available. "
            f"This is expected if CRM integration API is not yet implemented."
        )
    except yaml.YAMLError as e:
        logger.error(
            f"❌ Failed to parse OpenAPI spec at {openapi_spec_path}: {e}. "
            f"/docs endpoint will not be available."
        )
    
    # Initialize database
    await init_db()

    # Initialize CRM MySQL connection pool (if enabled)
    crm_pool = None
    if settings.crm_mysql_enabled:
        if not settings.crm_mysql_user or not settings.crm_mysql_password:
            logger.warning("⚠️  CRM_MYSQL_ENABLED=true but credentials missing. CRM sync disabled.")
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
                    ssl=None  # Explicitly disable SSL (as per test command)
                )
                logger.info(f"✅ CRM MySQL connected: {settings.crm_mysql_host}/{settings.crm_mysql_database}")
            except Exception as e:
                logger.error(f"❌ CRM MySQL connection failed: {e}. CRM sync disabled.")
                crm_pool = None

    app.state.crm_pool = crm_pool

    logger.info("✅ Configuration loaded successfully")
    logger.info("🔗 Webhook endpoint: /webhooks/instagram")

    yield

    # Shutdown
    logger.info("Shutting down...")

    # Close CRM pool
    if crm_pool:
        crm_pool.close()
        await crm_pool.wait_closed()
        logger.info("✅ CRM MySQL pool closed")

    await close_db()


app = FastAPI(
    title="Instagram Messenger Automation",
    description="Automated Instagram DM responses for e-commerce",
    version=__version__,
    lifespan=lifespan,
    docs_url=None,  # Disable default docs
    redoc_url=None,  # Disable default redoc
    openapi_url=None  # We'll serve custom OpenAPI
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
# CRM Integration API Documentation
# ============================================

def require_openapi_spec(func):
    """Decorator to check if OpenAPI spec is available before serving docs"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        if openapi_spec is None:
            return JSONResponse(
                status_code=404,
                content={
                    "error": "not_available",
                    "message": "OpenAPI specification is not available. The CRM integration API is not yet implemented.",
                    "hint": "The OpenAPI spec file is missing or could not be loaded. Check server logs for details."
                }
            )
        return await func(*args, **kwargs)
    return wrapper


@app.get("/openapi.json", include_in_schema=False)
@require_openapi_spec
async def get_openapi():
    """Serve the OpenAPI spec from file"""
    return openapi_spec


@app.get("/docs", include_in_schema=False)
@require_openapi_spec
async def custom_swagger_ui_html():
    """Custom Swagger UI with enhanced features"""
    # Extract title from spec, fallback to default
    title = openapi_spec.get('info', {}).get('title', 'API Documentation') if openapi_spec else 'API Documentation'
    
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title=title,
        swagger_ui_parameters={
            "persistAuthorization": True,  # Remember auth token
            "displayRequestDuration": True,  # Show request timing
            "filter": True,  # Enable search/filter
            "tryItOutEnabled": True,  # Enable "Try it out" by default
        }
    )


@app.get("/redoc", include_in_schema=False)
@require_openapi_spec
async def redoc_html():
    """Alternative API documentation with ReDoc"""
    # Extract title from spec, fallback to default
    title = openapi_spec.get('info', {}).get('title', 'API Documentation') if openapi_spec else 'API Documentation'

    return get_redoc_html(
        openapi_url="/openapi.json",
        title=title
    )


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
