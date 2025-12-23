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
"""Tests for the GET /models endpoint."""

import os
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from app.main import get_app
from app.core.config import ModelConfig, Settings
from app.services.model_registry import ModelRegistry


@pytest.fixture
def mock_registry_with_models():
    """Create a mock model registry with test models."""
    registry = MagicMock(spec=ModelRegistry)
    
    test_models = {
        "test-gpt-model": ModelConfig(
            provider="openai",
            model_id="gpt-5.1",
            api_key_env="TEST_OPENAI_KEY",
            enabled=True,
            timeout=60,
            max_retries=3
        ),
        "test-claude-model": ModelConfig(
            provider="anthropic",
            model_id="claude-sonnet-4.5",
            api_key_env="TEST_ANTHROPIC_KEY",
            enabled=True,
            timeout=90,
            max_retries=5
        ),
        "test-gemini-model": ModelConfig(
            provider="google",
            model_id="gemini-3.0-pro",
            api_key_env="TEST_GOOGLE_KEY",
            enabled=False,
            timeout=45,
            max_retries=3
        )
    }
    
    enabled_models = {k: v for k, v in test_models.items() if v.enabled}
    
    registry.get_enabled_models.return_value = enabled_models
    registry.get_model_config.side_effect = lambda name: test_models.get(name)
    registry.has_registry.return_value = True
    
    return registry


@pytest.fixture
def mock_registry_empty():
    """Create a mock model registry with no models."""
    registry = MagicMock(spec=ModelRegistry)
    registry.get_enabled_models.return_value = {}
    registry.get_model_config.return_value = None
    registry.has_registry.return_value = False
    return registry


@pytest.fixture
def client_with_models(mock_registry_with_models):
    """Create test client with mocked model registry."""
    with patch("app.services.model_registry.get_model_registry", return_value=mock_registry_with_models):
        app = get_app()
        client = TestClient(app)
        yield client


@pytest.fixture
def client_with_no_models(mock_registry_empty):
    """Create test client with empty model registry."""
    with patch("app.services.model_registry.get_model_registry", return_value=mock_registry_empty):
        app = get_app()
        client = TestClient(app)
        yield client


class TestModelsEndpoint:
    """Tests for the GET /models endpoint."""
    
    def test_list_models_returns_enabled_models(self, client_with_models):
        """Test that GET /models returns only enabled models."""
        response = client_with_models.get("/api/v1/models")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "models" in data
        assert len(data["models"]) == 2  # Only 2 enabled models
        
        # Check that disabled model is not included
        model_names = [m["logical_name"] for m in data["models"]]
        assert "test-gpt-model" in model_names
        assert "test-claude-model" in model_names
        assert "test-gemini-model" not in model_names
    
    def test_list_models_includes_all_metadata_fields(self, client_with_models):
        """Test that each model includes all required metadata fields."""
        response = client_with_models.get("/api/v1/models")
        
        assert response.status_code == 200
        data = response.json()
        
        for model in data["models"]:
            # Required top-level fields
            assert "logical_name" in model
            assert "provider" in model
            assert "model_id" in model
            assert "enabled" in model
            assert "timeout" in model
            assert "max_retries" in model
            assert "description" in model
            assert "metadata" in model
            
            # Required metadata fields
            assert "approximate_max_context" in model["metadata"]
            assert "supports_streaming" in model["metadata"]
            
            # Validate types
            assert isinstance(model["logical_name"], str)
            assert isinstance(model["provider"], str)
            assert isinstance(model["model_id"], str)
            assert isinstance(model["enabled"], bool)
            assert isinstance(model["timeout"], int)
            assert isinstance(model["max_retries"], int)
            assert isinstance(model["description"], str)
            assert isinstance(model["metadata"]["approximate_max_context"], int)
            assert isinstance(model["metadata"]["supports_streaming"], bool)
    
    def test_list_models_gpt5_metadata(self, client_with_models):
        """Test metadata for GPT-5 model."""
        response = client_with_models.get("/api/v1/models")
        
        assert response.status_code == 200
        data = response.json()
        
        gpt_model = next(m for m in data["models"] if m["logical_name"] == "test-gpt-model")
        
        assert gpt_model["provider"] == "openai"
        assert gpt_model["model_id"] == "gpt-5.1"
        assert gpt_model["enabled"] is True
        assert gpt_model["timeout"] == 60
        assert gpt_model["max_retries"] == 3
        assert "OpenAI" in gpt_model["description"]
        assert gpt_model["metadata"]["approximate_max_context"] == 128000
        assert gpt_model["metadata"]["supports_streaming"] is False
    
    def test_list_models_claude_metadata(self, client_with_models):
        """Test metadata for Claude model."""
        response = client_with_models.get("/api/v1/models")
        
        assert response.status_code == 200
        data = response.json()
        
        claude_model = next(m for m in data["models"] if m["logical_name"] == "test-claude-model")
        
        assert claude_model["provider"] == "anthropic"
        assert claude_model["model_id"] == "claude-sonnet-4.5"
        assert claude_model["enabled"] is True
        assert claude_model["timeout"] == 90
        assert claude_model["max_retries"] == 5
        assert "Anthropic" in claude_model["description"]
        assert claude_model["metadata"]["approximate_max_context"] == 200000
        assert claude_model["metadata"]["supports_streaming"] is False
    
    def test_list_models_empty_when_no_models_enabled(self, client_with_no_models):
        """Test that GET /models returns empty list when no models are enabled."""
        response = client_with_no_models.get("/api/v1/models")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "models" in data
        assert data["models"] == []
    
    def test_list_models_does_not_leak_api_keys(self, client_with_models):
        """Test that API keys are not exposed in the response."""
        response = client_with_models.get("/api/v1/models")
        
        assert response.status_code == 200
        data = response.json()
        
        # Convert entire response to string to check for key leakage
        response_str = str(data).lower()
        
        # Ensure no API key patterns or env var names are leaked
        assert "sk-test-key" not in response_str
        assert "sk-ant-test-key" not in response_str
        assert "test_openai_key" not in response_str
        assert "test_anthropic_key" not in response_str
        assert "test_google_key" not in response_str
        
        # Check that api_key_env is not in any model
        for model in data["models"]:
            assert "api_key_env" not in model
            assert "api_key" not in model
    
    def test_list_models_does_not_expose_full_base_url(self, client_with_models):
        """Test that full base URLs are not exposed, only presence indicator."""
        response = client_with_models.get("/api/v1/models")
        
        assert response.status_code == 200
        data = response.json()
        
        for model in data["models"]:
            # base_url field should not be directly present
            assert "base_url" not in model
            
            # If a custom base URL is set, only has_custom_base_url should be indicated
            if "has_custom_base_url" in model.get("metadata", {}):
                assert isinstance(model["metadata"]["has_custom_base_url"], bool)
    
    def test_list_models_endpoint_uses_get_method(self, client_with_models):
        """Test that the endpoint only accepts GET requests."""
        # GET should work
        response = client_with_models.get("/api/v1/models")
        assert response.status_code == 200
        
        # POST should fail
        response = client_with_models.post("/api/v1/models")
        assert response.status_code == 405
        
        # PUT should fail
        response = client_with_models.put("/api/v1/models")
        assert response.status_code == 405
        
        # DELETE should fail
        response = client_with_models.delete("/api/v1/models")
        assert response.status_code == 405
    
    def test_list_models_response_structure_is_consistent(self, client_with_models):
        """Test that response structure matches documented format."""
        response = client_with_models.get("/api/v1/models")
        
        assert response.status_code == 200
        data = response.json()
        
        # Top-level structure
        assert isinstance(data, dict)
        assert "models" in data
        assert isinstance(data["models"], list)
        
        # Each model has consistent structure
        for model in data["models"]:
            assert isinstance(model, dict)
            assert len(model) >= 8  # At least 8 required fields
    
    def test_list_models_handles_multiple_providers(self, client_with_models):
        """Test that models from different providers are all returned."""
        response = client_with_models.get("/api/v1/models")
        
        assert response.status_code == 200
        data = response.json()
        
        providers = {m["provider"] for m in data["models"]}
        
        # Should have both openai and anthropic (gemini is disabled)
        assert "openai" in providers
        assert "anthropic" in providers
    
    def test_list_models_serializes_efficiently(self, client_with_models):
        """Test that response is reasonably sized and efficient."""
        response = client_with_models.get("/api/v1/models")
        
        assert response.status_code == 200
        
        # Check that response is not excessively large
        # Each model should be < 1KB in JSON format
        content_length = len(response.content)
        num_models = len(response.json()["models"])
        
        # Very generous upper bound: 2KB per model
        assert content_length < num_models * 2048
    
    def test_list_models_returns_json_content_type(self, client_with_models):
        """Test that response has correct content type."""
        response = client_with_models.get("/api/v1/models")
        
        assert response.status_code == 200
        assert "application/json" in response.headers.get("content-type", "")


class TestModelsEndpointContextWindowEstimates:
    """Tests for approximate_max_context estimates."""
    
    def test_gpt5_context_window(self):
        """Test GPT-5 models have correct context window estimate."""
        from app.api.routes import _get_approximate_max_context
        
        assert _get_approximate_max_context("openai", "gpt-5.1") == 128000
        assert _get_approximate_max_context("openai", "gpt-5.0") == 128000
        assert _get_approximate_max_context("openai", "gpt-5-turbo") == 128000
    
    def test_gpt4_turbo_context_window(self):
        """Test GPT-4 Turbo has correct context window estimate."""
        from app.api.routes import _get_approximate_max_context
        
        assert _get_approximate_max_context("openai", "gpt-4-turbo") == 128000
        assert _get_approximate_max_context("openai", "gpt-4-1106-preview") == 128000
        assert _get_approximate_max_context("openai", "gpt-4-turbo-preview") == 128000
    
    def test_gpt4_base_context_window(self):
        """Test GPT-4 base has correct context window estimate."""
        from app.api.routes import _get_approximate_max_context
        
        assert _get_approximate_max_context("openai", "gpt-4") == 8192
        assert _get_approximate_max_context("openai", "gpt-4-0613") == 8192
    
    def test_gpt4_32k_context_window(self):
        """Test GPT-4 32K variant has correct context window estimate."""
        from app.api.routes import _get_approximate_max_context
        
        assert _get_approximate_max_context("openai", "gpt-4-32k") == 32768
        assert _get_approximate_max_context("openai", "gpt-4-32k-0613") == 32768
    
    def test_claude_context_window(self):
        """Test Claude models have correct context window estimate."""
        from app.api.routes import _get_approximate_max_context
        
        assert _get_approximate_max_context("anthropic", "claude-4-opus") == 200000
        assert _get_approximate_max_context("anthropic", "claude-3-sonnet") == 200000
        assert _get_approximate_max_context("anthropic", "claude-sonnet-4.5") == 200000
        assert _get_approximate_max_context("anthropic", "opus-3") == 200000
    
    def test_gemini_context_window(self):
        """Test Gemini models have correct context window estimate."""
        from app.api.routes import _get_approximate_max_context
        
        assert _get_approximate_max_context("google", "gemini-3.0-pro") == 1000000
        assert _get_approximate_max_context("google", "gemini-2.0-flash") == 1000000
        assert _get_approximate_max_context("google", "gemini-1.5-pro") == 1000000
    
    def test_unknown_provider_context_window(self):
        """Test unknown providers get conservative default."""
        from app.api.routes import _get_approximate_max_context
        
        assert _get_approximate_max_context("unknown-provider", "some-model") == 8192
    
    def test_unknown_openai_model_gets_default(self):
        """Test unknown OpenAI models get provider default."""
        from app.api.routes import _get_approximate_max_context
        
        assert _get_approximate_max_context("openai", "gpt-3.5-turbo") == 16384
        assert _get_approximate_max_context("openai", "unknown-model") == 16384
    
    def test_prefix_matching_avoids_false_positives(self):
        """Test that prefix matching doesn't match substrings incorrectly."""
        from app.api.routes import _get_approximate_max_context
        
        # Model with gpt-5 in the middle shouldn't match gpt-5 prefix
        # Since we use startswith, "my-gpt-5-custom" won't match "gpt-5" prefix
        assert _get_approximate_max_context("openai", "my-gpt-5-custom") == 16384  # Gets default
        
        # But "gpt-5-custom" should match
        assert _get_approximate_max_context("openai", "gpt-5-custom") == 128000


class TestModelsEndpointDescriptions:
    """Tests for model descriptions."""
    
    def test_gpt5_description(self):
        """Test GPT-5 models have appropriate descriptions."""
        from app.api.routes import _get_model_description
        
        desc = _get_model_description("openai", "gpt-5.1")
        assert "OpenAI" in desc
        assert "gpt-5.1" in desc
        assert "reasoning" in desc.lower() or "performance" in desc.lower()
    
    def test_gpt4_turbo_description(self):
        """Test GPT-4 Turbo has appropriate description."""
        from app.api.routes import _get_model_description
        
        desc = _get_model_description("openai", "gpt-4-turbo")
        assert "OpenAI" in desc
        assert "gpt-4-turbo" in desc
        assert "fast" in desc.lower() or "turbo" in desc.lower()
    
    def test_claude_opus_description(self):
        """Test Claude Opus has appropriate description."""
        from app.api.routes import _get_model_description
        
        desc = _get_model_description("anthropic", "claude-4-opus")
        assert "Anthropic" in desc
        assert "opus" in desc.lower()
        assert "capable" in desc.lower() or "complex" in desc.lower()
    
    def test_claude_sonnet_description(self):
        """Test Claude Sonnet has appropriate description."""
        from app.api.routes import _get_model_description
        
        desc = _get_model_description("anthropic", "claude-sonnet-4.5")
        assert "Anthropic" in desc
        assert "sonnet" in desc.lower()
        assert "balanced" in desc.lower() or "performance" in desc.lower()
    
    def test_gemini_pro_description(self):
        """Test Gemini Pro has appropriate description."""
        from app.api.routes import _get_model_description
        
        desc = _get_model_description("google", "gemini-3.0-pro")
        assert "Google" in desc
        assert "pro" in desc.lower()
    
    def test_unknown_model_description(self):
        """Test unknown models get basic description."""
        from app.api.routes import _get_model_description
        
        desc = _get_model_description("unknown", "mystery-model")
        assert "unknown" in desc
        assert "mystery-model" in desc
    
    def test_prefix_matching_for_descriptions(self):
        """Test that description prefix matching works correctly."""
        from app.api.routes import _get_model_description
        
        # Test that startswith is used for OpenAI models
        desc1 = _get_model_description("openai", "gpt-5-custom")
        assert "Latest generation" in desc1
        
        # Model with gpt-5 not at start should get generic description
        desc2 = _get_model_description("openai", "my-gpt-5-model")
        assert desc2 == "OpenAI my-gpt-5-model"  # Generic format
