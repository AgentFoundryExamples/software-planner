# Copyright 2025 John Brosnihan
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
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


def test_llm_settings_default_values():
    """Test that LLM settings have correct default values."""
    test_settings = Settings()
    
    assert test_settings.llm_api_key == ""
    assert test_settings.llm_model == "gpt-4"
    assert test_settings.llm_base_url is None
    assert test_settings.llm_timeout == 60
    assert test_settings.llm_system_prompt is None


def test_llm_settings_environment_override(monkeypatch):
    """Test that LLM environment variables override default settings."""
    monkeypatch.setenv("LLM_API_KEY", "test-key-123")
    monkeypatch.setenv("LLM_MODEL", "claude-sonnet-4.5")
    monkeypatch.setenv("LLM_BASE_URL", "https://api.example.com")
    monkeypatch.setenv("LLM_TIMEOUT", "90")
    monkeypatch.setenv("LLM_SYSTEM_PROMPT", "Custom prompt")
    
    test_settings = Settings()
    
    assert test_settings.llm_api_key == "test-key-123"
    assert test_settings.llm_model == "claude-sonnet-4.5"
    assert test_settings.llm_base_url == "https://api.example.com"
    assert test_settings.llm_timeout == 90
    assert test_settings.llm_system_prompt == "Custom prompt"


def test_llm_timeout_validation_minimum(monkeypatch):
    """Test that LLM timeout must be at least 1 second."""
    monkeypatch.setenv("LLM_TIMEOUT", "0")
    
    with pytest.raises(ValidationError) as exc_info:
        Settings()
    
    assert "llm_timeout" in str(exc_info.value).lower()


def test_llm_settings_case_insensitive(monkeypatch):
    """Test that LLM environment variables are case-insensitive."""
    monkeypatch.setenv("llm_api_key", "lowercase-key")
    monkeypatch.setenv("llm_model", "lowercase-model")
    
    test_settings = Settings()
    
    assert test_settings.llm_api_key == "lowercase-key"
    assert test_settings.llm_model == "lowercase-model"


def test_llm_base_url_optional(monkeypatch):
    """Test that LLM base URL is optional."""
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MODEL", "gpt-5.1")
    # Not setting LLM_BASE_URL
    
    test_settings = Settings()
    
    assert test_settings.llm_base_url is None


def test_llm_system_prompt_optional(monkeypatch):
    """Test that LLM system prompt override is optional."""
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MODEL", "gpt-5.1")
    # Not setting LLM_SYSTEM_PROMPT
    
    test_settings = Settings()
    
    assert test_settings.llm_system_prompt is None


def test_llm_settings_without_api_key_allowed():
    """Test that settings can be created without API key for non-LLM usage."""
    # This should not raise an error - API key is optional at config level
    # It will be validated when trying to use LLM features
    test_settings = Settings()
    
    assert test_settings.llm_api_key == ""
    assert test_settings.llm_model == "gpt-4"
