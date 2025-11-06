"""
Instagram Messenger Automation - Main Application Entry Point
"""
from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.responses import FileResponse
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

# Load OpenAPI spec from file
openapi_spec_path = Path(__file__).parent / "static" / "openapi.yaml"
with open(openapi_spec_path, "r", encoding="utf-8") as f:
    openapi_spec = yaml.safe_load(f)

app = FastAPI(
    title="Instagram Messenger Automation",
    description="Automated Instagram DM responses for e-commerce",
    version="0.1.0",
    docs_url=None,  # Disable default docs
    redoc_url=None,  # Disable default redoc
    openapi_url=None  # We'll serve custom OpenAPI
)

# Register webhook routes
app.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])


@app.on_event("startup")
async def startup_event():
    """Initialize database and validate configuration on startup"""
    logger.info(f"🚀 Starting Instagram Messenger Automation")
    logger.info(f"📝 Environment: {settings.environment}")
    
    # Initialize database
    await init_db()
    
    logger.info(f"✅ Configuration loaded successfully")
    logger.info(f"🔗 Webhook endpoint: /webhooks/instagram")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on shutdown"""
    logger.info("Shutting down...")
    await close_db()


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

@app.get("/openapi.json", include_in_schema=False)
async def get_openapi():
    """Serve the OpenAPI spec from file"""
    return openapi_spec


@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    """Custom Swagger UI with enhanced features"""
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title=f"{openapi_spec['info']['title']} - API Documentation",
        swagger_ui_parameters={
            "persistAuthorization": True,  # Remember auth token
            "displayRequestDuration": True,  # Show request timing
            "filter": True,  # Enable search/filter
            "tryItOutEnabled": True,  # Enable "Try it out" by default
        }
    )


@app.get("/redoc", include_in_schema=False)
async def redoc_html():
    """Alternative API documentation with ReDoc"""
    return get_redoc_html(
        openapi_url="/openapi.json",
        title=f"{openapi_spec['info']['title']} - API Documentation"
    )
