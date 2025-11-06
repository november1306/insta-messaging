"""
Tests for API authentication (stub implementation)

Note: Tests included for MVP to verify security boundaries (401 responses).
Core functionality tests help prevent accidental security regressions.
"""
import pytest
from fastapi import HTTPException
from app.api.auth import verify_api_key


def test_verify_api_key_with_valid_bearer_token():
    """Test that valid Bearer token is accepted"""
    result = verify_api_key(authorization="Bearer test_key")
    assert result == "test_key"


def test_verify_api_key_with_any_key():
    """Test that any non-empty key is accepted (stub behavior)"""
    result = verify_api_key(authorization="Bearer my_custom_key_123")
    assert result == "my_custom_key_123"


def test_verify_api_key_missing_header():
    """Test that missing Authorization header returns 401"""
    with pytest.raises(HTTPException) as exc_info:
        verify_api_key(authorization=None)
    
    assert exc_info.value.status_code == 401
    assert "Invalid Authorization" in exc_info.value.detail


def test_verify_api_key_invalid_format():
    """Test that invalid format (not Bearer) returns 401"""
    with pytest.raises(HTTPException) as exc_info:
        verify_api_key(authorization="Basic test_key")
    
    assert exc_info.value.status_code == 401
    assert "Invalid Authorization" in exc_info.value.detail


def test_verify_api_key_empty_key():
    """Test that empty key after Bearer returns 401"""
    with pytest.raises(HTTPException) as exc_info:
        verify_api_key(authorization="Bearer ")
    
    assert exc_info.value.status_code == 401
    assert "Empty API key" in exc_info.value.detail


def test_verify_api_key_whitespace_only():
    """Test that whitespace-only key returns 401"""
    with pytest.raises(HTTPException) as exc_info:
        verify_api_key(authorization="Bearer    ")
    
    assert exc_info.value.status_code == 401
    assert "Empty API key" in exc_info.value.detail


@pytest.mark.parametrize("env_value", ["production", "prod", "PRODUCTION", "PROD"])
def test_auth_module_blocks_production_environments(env_value, monkeypatch):
    """
    Test that stub auth module cannot be imported in production-like environments.
    
    Note: This tests the module-level check. In real deployment, the app would
    fail to start if ENVIRONMENT is set to production, preventing any requests.
    """
    import importlib
    import sys
    
    # Set environment before importing
    monkeypatch.setenv("ENVIRONMENT", env_value)
    
    # Remove module from cache if already imported
    if "app.api.auth" in sys.modules:
        del sys.modules["app.api.auth"]
    
    # Attempt to import should raise RuntimeError
    with pytest.raises(RuntimeError) as exc_info:
        import app.api.auth
        importlib.reload(app.api.auth)
    
    assert "production" in str(exc_info.value).lower()
