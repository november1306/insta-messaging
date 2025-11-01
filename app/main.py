"""
Instagram Messenger Automation - Main Application Entry Point
"""
from fastapi import FastAPI
from app.api import webhooks
from app.config import settings
import logging

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
    """Validate configuration on startup"""
    logger.info(f"🚀 Starting Instagram Messenger Automation")
    logger.info(f"📝 Environment: {settings.environment}")
    logger.info(f"✅ Configuration loaded successfully")
    logger.info(f"🔗 Webhook endpoint: /webhooks/instagram")


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "app": "Instagram Messenger Automation",
        "status": "running",
        "environment": settings.environment,
        "webhook_url": "/webhooks/instagram"
    }
