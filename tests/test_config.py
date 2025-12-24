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


# ============================================================================
# Tests for Security: API Key Authentication
# ============================================================================

def test_planner_api_keys_default_empty():
    """Test that planner_api_keys defaults to empty list."""
    test_settings = Settings()
    assert test_settings.planner_api_keys == []


def test_planner_api_keys_valid_list(monkeypatch):
    """Test that valid API keys can be set."""
    monkeypatch.setenv("PLANNER_API_KEYS", '["key1", "key2", "key3"]')
    test_settings = Settings()
    assert test_settings.planner_api_keys == ["key1", "key2", "key3"]


def test_planner_api_keys_rejects_empty_string():
    """Test that empty string API keys are rejected."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(planner_api_keys=["key1", "", "key3"])
    assert "empty or contain only whitespace" in str(exc_info.value).lower()


def test_planner_api_keys_rejects_whitespace_only():
    """Test that whitespace-only API keys are rejected."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(planner_api_keys=["key1", "   ", "key3"])
    assert "empty or contain only whitespace" in str(exc_info.value).lower()


def test_planner_api_keys_rejects_duplicates():
    """Test that duplicate API keys are rejected."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(planner_api_keys=["key1", "key2", "key1"])
    assert "duplicate" in str(exc_info.value).lower()


def test_planner_api_keys_rejects_duplicates_with_whitespace():
    """Test that duplicate API keys with different whitespace are rejected."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(planner_api_keys=["key1", " key1 "])
    assert "duplicate" in str(exc_info.value).lower()


# ============================================================================
# Tests for Security: Request Bounds
# ============================================================================

def test_planner_request_description_max_chars_default():
    """Test default value for request description max chars."""
    test_settings = Settings()
    assert test_settings.planner_request_description_max_chars == 50000


def test_planner_request_description_max_chars_valid_value(monkeypatch):
    """Test setting valid request description max chars."""
    monkeypatch.setenv("PLANNER_REQUEST_DESCRIPTION_MAX_CHARS", "100000")
    test_settings = Settings()
    assert test_settings.planner_request_description_max_chars == 100000


def test_planner_request_description_max_chars_rejects_zero(monkeypatch):
    """Test that zero is rejected for max chars."""
    monkeypatch.setenv("PLANNER_REQUEST_DESCRIPTION_MAX_CHARS", "0")
    with pytest.raises(ValidationError) as exc_info:
        Settings()
    assert "planner_request_description_max_chars" in str(exc_info.value).lower()


def test_planner_request_description_max_chars_rejects_negative(monkeypatch):
    """Test that negative values are rejected for max chars."""
    monkeypatch.setenv("PLANNER_REQUEST_DESCRIPTION_MAX_CHARS", "-100")
    with pytest.raises(ValidationError) as exc_info:
        Settings()
    assert "planner_request_description_max_chars" in str(exc_info.value).lower()


def test_planner_request_description_max_chars_rejects_extremely_high():
    """Test that extremely high values exceeding LLM limits are rejected."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(planner_request_description_max_chars=600000)
    assert "exceeds reasonable limit" in str(exc_info.value).lower()


# ============================================================================
# Tests for Security: Rate Limiting
# ============================================================================

def test_rate_limit_defaults():
    """Test default values for rate limiting settings."""
    test_settings = Settings()
    assert test_settings.planner_rate_limit_window_seconds == 60
    assert test_settings.planner_rate_limit_max_requests == 10


def test_rate_limit_valid_values(monkeypatch):
    """Test setting valid rate limit values."""
    monkeypatch.setenv("PLANNER_RATE_LIMIT_WINDOW_SECONDS", "120")
    monkeypatch.setenv("PLANNER_RATE_LIMIT_MAX_REQUESTS", "50")
    test_settings = Settings()
    assert test_settings.planner_rate_limit_window_seconds == 120
    assert test_settings.planner_rate_limit_max_requests == 50


def test_rate_limit_window_rejects_zero(monkeypatch):
    """Test that zero is rejected for rate limit window."""
    monkeypatch.setenv("PLANNER_RATE_LIMIT_WINDOW_SECONDS", "0")
    with pytest.raises(ValidationError) as exc_info:
        Settings()
    assert "planner_rate_limit_window_seconds" in str(exc_info.value).lower()


def test_rate_limit_window_rejects_negative(monkeypatch):
    """Test that negative values are rejected for rate limit window."""
    monkeypatch.setenv("PLANNER_RATE_LIMIT_WINDOW_SECONDS", "-60")
    with pytest.raises(ValidationError) as exc_info:
        Settings()
    assert "planner_rate_limit_window_seconds" in str(exc_info.value).lower()


def test_rate_limit_max_requests_rejects_zero(monkeypatch):
    """Test that zero is rejected for max requests."""
    monkeypatch.setenv("PLANNER_RATE_LIMIT_MAX_REQUESTS", "0")
    with pytest.raises(ValidationError) as exc_info:
        Settings()
    assert "planner_rate_limit_max_requests" in str(exc_info.value).lower()


def test_rate_limit_max_requests_rejects_negative(monkeypatch):
    """Test that negative values are rejected for max requests."""
    monkeypatch.setenv("PLANNER_RATE_LIMIT_MAX_REQUESTS", "-10")
    with pytest.raises(ValidationError) as exc_info:
        Settings()
    assert "planner_rate_limit_max_requests" in str(exc_info.value).lower()


# ============================================================================
# Tests for Observability: Metrics
# ============================================================================

def test_planner_metrics_enabled_default():
    """Test that metrics are disabled by default."""
    test_settings = Settings()
    assert test_settings.planner_metrics_enabled is False


def test_planner_metrics_enabled_can_be_enabled(monkeypatch):
    """Test that metrics can be enabled."""
    monkeypatch.setenv("PLANNER_METRICS_ENABLED", "true")
    test_settings = Settings()
    assert test_settings.planner_metrics_enabled is True


# ============================================================================
# Tests for Security: CORS Wildcard Configuration
# ============================================================================

def test_cors_allowed_origins_default():
    """Test default CORS allowed origins."""
    test_settings = Settings()
    assert test_settings.allowed_origins == ["*"]


def test_cors_wildcard_enabled_default():
    """Test that CORS wildcard is enabled by default for backward compatibility."""
    test_settings = Settings()
    assert test_settings.cors_wildcard_enabled is True


def test_cors_wildcard_requires_explicit_toggle():
    """Test that wildcard in origins requires explicit toggle when disabled."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(allowed_origins=["*"], cors_wildcard_enabled=False)
    assert "cors_wildcard_enabled" in str(exc_info.value).lower()
    assert "explicitly" in str(exc_info.value).lower()


def test_cors_wildcard_works_with_toggle_enabled():
    """Test that wildcard works when explicitly enabled."""
    test_settings = Settings(allowed_origins=["*"], cors_wildcard_enabled=True)
    assert test_settings.allowed_origins == ["*"]
    assert test_settings.cors_wildcard_enabled is True


def test_cors_specific_origins_without_wildcard_toggle():
    """Test that specific origins work without wildcard toggle."""
    test_settings = Settings(
        allowed_origins=["https://example.com", "https://app.example.com"],
        cors_wildcard_enabled=False
    )
    assert test_settings.allowed_origins == ["https://example.com", "https://app.example.com"]


def test_cors_mixed_wildcard_requires_toggle():
    """Test that mixed list with wildcard requires toggle."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            allowed_origins=["https://example.com", "*"],
            cors_wildcard_enabled=False
        )
    assert "cors_wildcard_enabled" in str(exc_info.value).lower()


# ============================================================================
# Tests for Helper Methods
# ============================================================================

def test_get_normalized_api_keys_empty():
    """Test normalized API keys with empty list."""
    test_settings = Settings()
    assert test_settings.get_normalized_api_keys() == set()


def test_get_normalized_api_keys_strips_whitespace():
    """Test that normalized API keys strips whitespace."""
    test_settings = Settings(planner_api_keys=["  key1  ", "key2", " key3"])
    normalized = test_settings.get_normalized_api_keys()
    assert normalized == {"key1", "key2", "key3"}


def test_get_rate_limit_config():
    """Test rate limit configuration helper."""
    test_settings = Settings(
        planner_rate_limit_window_seconds=120,
        planner_rate_limit_max_requests=50
    )
    config = test_settings.get_rate_limit_config()
    assert config == {"window_seconds": 120, "max_requests": 50}


def test_is_api_key_valid_with_valid_key():
    """Test API key validation with valid key."""
    test_settings = Settings(planner_api_keys=["key1", "key2"])
    assert test_settings.is_api_key_valid("key1") is True
    assert test_settings.is_api_key_valid("key2") is True


def test_is_api_key_valid_with_invalid_key():
    """Test API key validation with invalid key."""
    test_settings = Settings(planner_api_keys=["key1", "key2"])
    assert test_settings.is_api_key_valid("invalid") is False
    assert test_settings.is_api_key_valid("") is False


def test_is_api_key_valid_with_whitespace():
    """Test API key validation handles whitespace correctly."""
    test_settings = Settings(planner_api_keys=["  key1  ", "key2"])
    assert test_settings.is_api_key_valid("key1") is True
    assert test_settings.is_api_key_valid("  key1  ") is True


def test_is_api_key_valid_with_empty_list():
    """Test API key validation with no keys configured."""
    test_settings = Settings()
    assert test_settings.is_api_key_valid("any-key") is False
