"""
Instagram Messenger Automation - Main Application Entry Point
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.responses import JSONResponse
from app.api import webhooks
from app.config import settings
from app.db import init_db, close_db
import logging
import yaml
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load OpenAPI spec from file (fail gracefully if missing)
openapi_spec = None
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

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager - handles startup and shutdown"""
    # Startup
    logger.info("🚀 Starting Instagram Messenger Automation")
    logger.info(f"📝 Environment: {settings.environment}")
    
    # Initialize database
    await init_db()
    
    logger.info("✅ Configuration loaded successfully")
    logger.info("🔗 Webhook endpoint: /webhooks/instagram")
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")
    await close_db()


app = FastAPI(
    title="Instagram Messenger Automation",
    description="Automated Instagram DM responses for e-commerce",
    version="0.1.0",
    lifespan=lifespan,
    docs_url=None,  # Disable default docs
    redoc_url=None,  # Disable default redoc
    openapi_url=None  # We'll serve custom OpenAPI
)

# Register webhook routes
app.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "app": "Instagram Messenger Automation",
        "status": "running",
        "environment": settings.environment,
        "webhook_url": "/webhooks/instagram"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "environment": settings.environment,
        "database": "connected"
    }


# ============================================
# CRM Integration API Documentation
# ============================================

def require_openapi_spec(func):
    """Decorator to check if OpenAPI spec is available before serving docs"""
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


def get_openapi_title() -> str:
    """Safely extract title from OpenAPI spec with fallback"""
    if openapi_spec and isinstance(openapi_spec, dict):
        return openapi_spec.get('info', {}).get('title', 'API Documentation') + " - API Documentation"
    return "API Documentation"


@app.get("/openapi.json", include_in_schema=False)
@require_openapi_spec
async def get_openapi():
    """Serve the OpenAPI spec from file"""
    return openapi_spec


@app.get("/docs", include_in_schema=False)
@require_openapi_spec
async def custom_swagger_ui_html():
    """Custom Swagger UI with enhanced features"""
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title=get_openapi_title(),
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
    return get_redoc_html(
        openapi_url="/openapi.json",
        title=get_openapi_title()
    )
