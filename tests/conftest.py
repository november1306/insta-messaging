"""
Pytest configuration and shared fixtures.
"""
import pytest_asyncio
import os
from app.db.connection import init_db, close_db


@pytest_asyncio.fixture(scope="function", autouse=True)
async def clean_database():
    """
    Clean database before each test.
    
    This fixture runs before each test function to ensure a clean state.
    """
    # Remove existing database file if it exists
    db_file = "instagram_automation.db"
    if os.path.exists(db_file):
        os.remove(db_file)
    
    # Initialize fresh database
    await init_db()
    
    yield
    
    # Cleanup after test
    await close_db()
    
    # Remove database file after test
    if os.path.exists(db_file):
        os.remove(db_file)
