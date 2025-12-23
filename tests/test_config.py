"""Tests for core configuration module."""

import os
import pytest
from pydantic import ValidationError
from app.core.config import Settings, settings


def test_settings_default_values():
    """Test that settings have correct default values."""
    test_settings = Settings()
    
    assert test_settings.app_name == "Software Planner API"
    assert test_settings.app_version == "0.1.0"
    assert test_settings.debug is False
    assert test_settings.host == "0.0.0.0"
    assert test_settings.port == 8000
    assert test_settings.api_prefix == "/api/v1"
    assert test_settings.allowed_origins == ["*"]
    assert test_settings.allowed_credentials is False  # Security: False by default with wildcard origins
    assert test_settings.allowed_methods == ["*"]
    assert test_settings.allowed_headers == ["*"]


def test_settings_environment_override(monkeypatch):
    """Test that environment variables override default settings."""
    monkeypatch.setenv("APP_NAME", "Test API")
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("PORT", "9000")
    
    test_settings = Settings()
    
    assert test_settings.app_name == "Test API"
    assert test_settings.debug is True
    assert test_settings.port == 9000


def test_settings_case_insensitive(monkeypatch):
    """Test that environment variables are case-insensitive."""
    monkeypatch.setenv("app_name", "Lower Case API")
    
    test_settings = Settings()
    
    assert test_settings.app_name == "Lower Case API"


def test_settings_extra_fields_ignored(monkeypatch):
    """Test that extra environment variables are ignored."""
    monkeypatch.setenv("UNKNOWN_FIELD", "should be ignored")
    
    # Should not raise an error
    test_settings = Settings()
    assert not hasattr(test_settings, "unknown_field")


def test_global_settings_instance():
    """Test that the global settings instance is available."""
    assert settings is not None
    assert isinstance(settings, Settings)
    assert settings.app_name == "Software Planner API"


def test_settings_no_env_file_required():
    """Test that settings work without .env file."""
    # This test verifies that the app can start without environment variables
    test_settings = Settings()
    
    # Should use all defaults
    assert test_settings.app_name == "Software Planner API"
    assert test_settings.port == 8000


def test_cors_validator_rejects_credentials_with_wildcard():
    """Test that CORS validator rejects credentials=True with wildcard origins."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            allowed_credentials=True,
            allowed_origins=["*"]
        )
    
    assert "allowed_credentials" in str(exc_info.value).lower() or "allowed_origins" in str(exc_info.value).lower()


def test_cors_validator_allows_credentials_with_specific_origins():
    """Test that CORS validator allows credentials=True with specific origins."""
    # This should not raise an error
    test_settings = Settings(
        allowed_credentials=True,
        allowed_origins=["http://localhost:3000", "https://example.com"]
    )
    
    assert test_settings.allowed_credentials is True
    assert "http://localhost:3000" in test_settings.allowed_origins
    assert "https://example.com" in test_settings.allowed_origins
