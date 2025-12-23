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
"""Tests for model registry configuration and helpers."""

import os
import pytest
from pydantic import ValidationError

from app.core.config import Settings, ModelConfig
from app.services.model_registry import ModelRegistry, get_model_registry


def test_model_config_basic():
    """Test basic ModelConfig creation."""
    config = ModelConfig(
        provider="openai",
        model_id="gpt-5.1",
        api_key_env="OPENAI_API_KEY",
        enabled=True,
        timeout=60,
        max_retries=3
    )
    
    assert config.provider == "openai"
    assert config.model_id == "gpt-5.1"
    assert config.api_key_env == "OPENAI_API_KEY"
    assert config.enabled is True
    assert config.timeout == 60
    assert config.max_retries == 3
    assert config.base_url is None


def test_model_config_with_base_url():
    """Test ModelConfig with custom base URL."""
    config = ModelConfig(
        provider="openai",
        model_id="gpt-4",
        api_key_env="OPENAI_API_KEY",
        base_url="https://custom.api.com/v1"
    )
    
    assert config.base_url == "https://custom.api.com/v1"


def test_model_config_defaults():
    """Test ModelConfig default values."""
    config = ModelConfig(
        provider="anthropic",
        model_id="claude-sonnet-4.5",
        api_key_env="ANTHROPIC_API_KEY"
    )
    
    assert config.enabled is True
    assert config.timeout == 60
    assert config.max_retries == 3


def test_model_config_invalid_timeout():
    """Test that ModelConfig rejects invalid timeout."""
    with pytest.raises(ValidationError):
        ModelConfig(
            provider="openai",
            model_id="gpt-5.1",
            api_key_env="OPENAI_API_KEY",
            timeout=0
        )


def test_model_config_negative_retries():
    """Test that ModelConfig rejects negative retries."""
    with pytest.raises(ValidationError):
        ModelConfig(
            provider="openai",
            model_id="gpt-5.1",
            api_key_env="OPENAI_API_KEY",
            max_retries=-1
        )


def test_settings_with_empty_registry():
    """Test Settings with no model registry (backward compatibility)."""
    settings = Settings()
    assert settings.models_registry == {}
    assert settings.default_model is None


def test_settings_with_single_model_registry(monkeypatch):
    """Test Settings with a single model in registry."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
    monkeypatch.setenv("MODELS_REGISTRY", """{
        "gpt5": {
            "provider": "openai",
            "model_id": "gpt-5.1",
            "api_key_env": "OPENAI_API_KEY",
            "enabled": true
        }
    }""")
    monkeypatch.setenv("DEFAULT_MODEL", "gpt5")
    
    settings = Settings()
    
    assert len(settings.models_registry) == 1
    assert "gpt5" in settings.models_registry
    assert settings.default_model == "gpt5"
    
    config = settings.models_registry["gpt5"]
    assert config.provider == "openai"
    assert config.model_id == "gpt-5.1"
    assert config.enabled is True


def test_settings_with_multiple_models(monkeypatch):
    """Test Settings with multiple models in registry."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key")
    monkeypatch.setenv("MODELS_REGISTRY", """{
        "gpt5": {
            "provider": "openai",
            "model_id": "gpt-5.1",
            "api_key_env": "OPENAI_API_KEY",
            "enabled": true,
            "timeout": 90
        },
        "claude": {
            "provider": "anthropic",
            "model_id": "claude-sonnet-4.5",
            "api_key_env": "ANTHROPIC_API_KEY",
            "enabled": true,
            "timeout": 60
        }
    }""")
    monkeypatch.setenv("DEFAULT_MODEL", "gpt5")
    
    settings = Settings()
    
    assert len(settings.models_registry) == 2
    assert settings.models_registry["gpt5"].timeout == 90
    assert settings.models_registry["claude"].timeout == 60


def test_settings_validation_no_enabled_models(monkeypatch):
    """Test that validation fails when all models are disabled."""
    monkeypatch.setenv("MODELS_REGISTRY", """{
        "gpt5": {
            "provider": "openai",
            "model_id": "gpt-5.1",
            "api_key_env": "OPENAI_API_KEY",
            "enabled": false
        }
    }""")
    monkeypatch.setenv("DEFAULT_MODEL", "gpt5")
    
    with pytest.raises(ValidationError) as exc_info:
        Settings()
    
    assert "at least one model must be enabled" in str(exc_info.value).lower()


def test_settings_validation_no_default_model(monkeypatch):
    """Test that validation fails when default_model is not specified."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
    monkeypatch.setenv("MODELS_REGISTRY", """{
        "gpt5": {
            "provider": "openai",
            "model_id": "gpt-5.1",
            "api_key_env": "OPENAI_API_KEY",
            "enabled": true
        }
    }""")
    # Not setting DEFAULT_MODEL
    
    with pytest.raises(ValidationError) as exc_info:
        Settings()
    
    assert "default_model must be specified" in str(exc_info.value).lower()


def test_settings_validation_default_model_not_in_registry(monkeypatch):
    """Test that validation fails when default_model doesn't exist."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
    monkeypatch.setenv("MODELS_REGISTRY", """{
        "gpt5": {
            "provider": "openai",
            "model_id": "gpt-5.1",
            "api_key_env": "OPENAI_API_KEY",
            "enabled": true
        }
    }""")
    monkeypatch.setenv("DEFAULT_MODEL", "nonexistent")
    
    with pytest.raises(ValidationError) as exc_info:
        Settings()
    
    assert "not found in registry" in str(exc_info.value).lower()


def test_settings_validation_default_model_disabled(monkeypatch):
    """Test that validation fails when default model is disabled."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
    monkeypatch.setenv("MODELS_REGISTRY", """{
        "gpt5": {
            "provider": "openai",
            "model_id": "gpt-5.1",
            "api_key_env": "OPENAI_API_KEY",
            "enabled": false
        }
    }""")
    monkeypatch.setenv("DEFAULT_MODEL", "gpt5")
    
    with pytest.raises(ValidationError) as exc_info:
        Settings()
    
    # Should fail because all models are disabled
    assert "at least one model must be enabled" in str(exc_info.value).lower()


def test_settings_validation_missing_api_key_env_var(monkeypatch):
    """Test that validation fails when API key env var is missing."""
    # Not setting OPENAI_API_KEY
    monkeypatch.setenv("MODELS_REGISTRY", """{
        "gpt5": {
            "provider": "openai",
            "model_id": "gpt-5.1",
            "api_key_env": "OPENAI_API_KEY",
            "enabled": true
        }
    }""")
    monkeypatch.setenv("DEFAULT_MODEL", "gpt5")
    
    with pytest.raises(ValidationError) as exc_info:
        Settings()
    
    assert "missing or empty api key" in str(exc_info.value).lower()
    assert "OPENAI_API_KEY" in str(exc_info.value)


def test_settings_validation_empty_api_key_env_var(monkeypatch):
    """Test that validation fails when API key env var is empty."""
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("MODELS_REGISTRY", """{
        "gpt5": {
            "provider": "openai",
            "model_id": "gpt-5.1",
            "api_key_env": "OPENAI_API_KEY",
            "enabled": true
        }
    }""")
    monkeypatch.setenv("DEFAULT_MODEL", "gpt5")
    
    with pytest.raises(ValidationError) as exc_info:
        Settings()
    
    assert "missing or empty api key" in str(exc_info.value).lower()


def test_settings_validation_disabled_model_missing_key_ok(monkeypatch):
    """Test that disabled models don't need API keys."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
    # ANTHROPIC_API_KEY is not set, but that's OK because claude is disabled
    monkeypatch.setenv("MODELS_REGISTRY", """{
        "gpt5": {
            "provider": "openai",
            "model_id": "gpt-5.1",
            "api_key_env": "OPENAI_API_KEY",
            "enabled": true
        },
        "claude": {
            "provider": "anthropic",
            "model_id": "claude-sonnet-4.5",
            "api_key_env": "ANTHROPIC_API_KEY",
            "enabled": false
        }
    }""")
    monkeypatch.setenv("DEFAULT_MODEL", "gpt5")
    
    # Should not raise an error
    settings = Settings()
    assert len(settings.models_registry) == 2


def test_settings_validation_unknown_provider(monkeypatch):
    """Test that validation fails with unknown provider."""
    monkeypatch.setenv("UNKNOWN_API_KEY", "test-key")
    monkeypatch.setenv("MODELS_REGISTRY", """{
        "custom": {
            "provider": "unknown_provider",
            "model_id": "custom-model",
            "api_key_env": "UNKNOWN_API_KEY",
            "enabled": true
        }
    }""")
    monkeypatch.setenv("DEFAULT_MODEL", "custom")
    
    with pytest.raises(ValidationError) as exc_info:
        Settings()
    
    assert "unknown provider" in str(exc_info.value).lower()


def test_settings_validation_invalid_timeout_in_registry(monkeypatch):
    """Test that validation fails with invalid timeout in registry."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
    monkeypatch.setenv("MODELS_REGISTRY", """{
        "gpt5": {
            "provider": "openai",
            "model_id": "gpt-5.1",
            "api_key_env": "OPENAI_API_KEY",
            "enabled": true,
            "timeout": 0
        }
    }""")
    monkeypatch.setenv("DEFAULT_MODEL", "gpt5")
    
    with pytest.raises(ValidationError) as exc_info:
        Settings()
    
    # Should fail during ModelConfig validation
    assert "timeout" in str(exc_info.value).lower()


def test_model_registry_get_model_config():
    """Test ModelRegistry.get_model_config()."""
    from app.core.config import settings
    
    # Create test settings with registry
    test_registry = {
        "gpt5": ModelConfig(
            provider="openai",
            model_id="gpt-5.1",
            api_key_env="OPENAI_API_KEY"
        )
    }
    
    # Temporarily override settings
    original_registry = settings.models_registry
    settings.models_registry = test_registry
    
    try:
        registry = ModelRegistry()
        config = registry.get_model_config("gpt5")
        
        assert config is not None
        assert config.model_id == "gpt-5.1"
        
        # Non-existent model
        assert registry.get_model_config("nonexistent") is None
    finally:
        settings.models_registry = original_registry


def test_model_registry_get_enabled_models():
    """Test ModelRegistry.get_enabled_models()."""
    from app.core.config import settings
    
    test_registry = {
        "gpt5": ModelConfig(
            provider="openai",
            model_id="gpt-5.1",
            api_key_env="OPENAI_API_KEY",
            enabled=True
        ),
        "claude": ModelConfig(
            provider="anthropic",
            model_id="claude-sonnet-4.5",
            api_key_env="ANTHROPIC_API_KEY",
            enabled=False
        )
    }
    
    original_registry = settings.models_registry
    settings.models_registry = test_registry
    
    try:
        registry = ModelRegistry()
        enabled = registry.get_enabled_models()
        
        assert len(enabled) == 1
        assert "gpt5" in enabled
        assert "claude" not in enabled
    finally:
        settings.models_registry = original_registry


def test_model_registry_get_disabled_models():
    """Test ModelRegistry.get_disabled_models()."""
    from app.core.config import settings
    
    test_registry = {
        "gpt5": ModelConfig(
            provider="openai",
            model_id="gpt-5.1",
            api_key_env="OPENAI_API_KEY",
            enabled=True
        ),
        "claude": ModelConfig(
            provider="anthropic",
            model_id="claude-sonnet-4.5",
            api_key_env="ANTHROPIC_API_KEY",
            enabled=False
        )
    }
    
    original_registry = settings.models_registry
    settings.models_registry = test_registry
    
    try:
        registry = ModelRegistry()
        disabled = registry.get_disabled_models()
        
        assert len(disabled) == 1
        assert "claude" in disabled
        assert "gpt5" not in disabled
    finally:
        settings.models_registry = original_registry


def test_model_registry_get_default_model():
    """Test ModelRegistry.get_default_model()."""
    from app.core.config import settings
    
    original_default = settings.default_model
    settings.default_model = "gpt5"
    
    try:
        registry = ModelRegistry()
        assert registry.get_default_model() == "gpt5"
    finally:
        settings.default_model = original_default


def test_model_registry_is_model_enabled():
    """Test ModelRegistry.is_model_enabled()."""
    from app.core.config import settings
    
    test_registry = {
        "gpt5": ModelConfig(
            provider="openai",
            model_id="gpt-5.1",
            api_key_env="OPENAI_API_KEY",
            enabled=True
        ),
        "claude": ModelConfig(
            provider="anthropic",
            model_id="claude-sonnet-4.5",
            api_key_env="ANTHROPIC_API_KEY",
            enabled=False
        )
    }
    
    original_registry = settings.models_registry
    settings.models_registry = test_registry
    
    try:
        registry = ModelRegistry()
        
        assert registry.is_model_enabled("gpt5") is True
        assert registry.is_model_enabled("claude") is False
        assert registry.is_model_enabled("nonexistent") is False
    finally:
        settings.models_registry = original_registry


def test_model_registry_get_models_by_provider():
    """Test ModelRegistry.get_models_by_provider()."""
    from app.core.config import settings
    
    test_registry = {
        "gpt5": ModelConfig(
            provider="openai",
            model_id="gpt-5.1",
            api_key_env="OPENAI_API_KEY"
        ),
        "gpt4": ModelConfig(
            provider="openai",
            model_id="gpt-4",
            api_key_env="OPENAI_API_KEY"
        ),
        "claude": ModelConfig(
            provider="anthropic",
            model_id="claude-sonnet-4.5",
            api_key_env="ANTHROPIC_API_KEY"
        )
    }
    
    original_registry = settings.models_registry
    settings.models_registry = test_registry
    
    try:
        registry = ModelRegistry()
        
        openai_models = registry.get_models_by_provider("openai")
        assert len(openai_models) == 2
        assert "gpt5" in openai_models
        assert "gpt4" in openai_models
        
        anthropic_models = registry.get_models_by_provider("anthropic")
        assert len(anthropic_models) == 1
        assert "claude" in anthropic_models
        
        google_models = registry.get_models_by_provider("google")
        assert len(google_models) == 0
    finally:
        settings.models_registry = original_registry


def test_model_registry_has_registry():
    """Test ModelRegistry.has_registry()."""
    from app.core.config import settings
    
    # With empty registry
    original_registry = settings.models_registry
    settings.models_registry = {}
    
    try:
        registry = ModelRegistry()
        assert registry.has_registry() is False
        
        # With non-empty registry
        settings.models_registry = {
            "gpt5": ModelConfig(
                provider="openai",
                model_id="gpt-5.1",
                api_key_env="OPENAI_API_KEY"
            )
        }
        registry = ModelRegistry()
        assert registry.has_registry() is True
    finally:
        settings.models_registry = original_registry


def test_model_registry_get_default_model_config():
    """Test ModelRegistry.get_default_model_config()."""
    from app.core.config import settings
    
    test_registry = {
        "gpt5": ModelConfig(
            provider="openai",
            model_id="gpt-5.1",
            api_key_env="OPENAI_API_KEY"
        )
    }
    
    original_registry = settings.models_registry
    original_default = settings.default_model
    settings.models_registry = test_registry
    settings.default_model = "gpt5"
    
    try:
        registry = ModelRegistry()
        config = registry.get_default_model_config()
        
        assert config is not None
        assert config.model_id == "gpt-5.1"
        
        # Test with no default
        settings.default_model = None
        registry = ModelRegistry()
        assert registry.get_default_model_config() is None
    finally:
        settings.models_registry = original_registry
        settings.default_model = original_default
