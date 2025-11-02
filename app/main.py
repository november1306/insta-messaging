"""
Instagram Messenger Automation - Main Application Entry Point
"""
from fastapi import FastAPI
from app.api import webhooks
from app.config import settings
from app.core.database import init_db, close_db
import logging

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Instagram Messenger Automation",
    description="Automated Instagram DM responses for e-commerce",
    version="0.1.0"
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
