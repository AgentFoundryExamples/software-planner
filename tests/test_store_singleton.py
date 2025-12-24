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
"""Tests for store singleton module."""

from unittest.mock import Mock, patch

import pytest

from app.services.llm_client import LLMConfigurationError
from app.services.llm_openai import OpenAIClient
from app.services.store_singleton import _llm_client, get_llm_client


class TestGetLLMClient:
    """Tests for get_llm_client factory function."""

    def setup_method(self):
        """Reset global LLM client before each test."""
        import app.services.store_singleton

        app.services.store_singleton._llm_client = None

    @patch("app.services.store_singleton.settings")
    @patch("app.services.store_singleton.OpenAIClient")
    def test_get_llm_client_creates_client(self, mock_client_class, mock_settings):
        """Test that get_llm_client creates a client from settings."""
        # Setup settings
        mock_settings.llm_api_key = "sk-test-key"
        mock_settings.llm_model = "gpt-5.1"
        mock_settings.llm_base_url = "https://api.example.com"
        mock_settings.llm_timeout = 90

        # Mock client instance
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        # Get client
        client = get_llm_client()

        # Verify client was created with correct settings
        mock_client_class.assert_called_once_with(
            api_key="sk-test-key",
            model="gpt-5.1",
            base_url="https://api.example.com",
            timeout=90,
        )

        # Verify returned client is the mock
        assert client is mock_client

    @patch("app.services.store_singleton.settings")
    @patch("app.services.store_singleton.OpenAIClient")
    def test_get_llm_client_singleton_behavior(self, mock_client_class, mock_settings):
        """Test that get_llm_client returns the same instance on subsequent calls."""
        # Setup settings
        mock_settings.llm_api_key = "sk-test-key"
        mock_settings.llm_model = "gpt-5.1"
        mock_settings.llm_base_url = None
        mock_settings.llm_timeout = 60

        # Mock client instance
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        # Get client twice
        client1 = get_llm_client()
        client2 = get_llm_client()

        # Verify same instance returned
        assert client1 is client2

        # Verify client was only created once
        mock_client_class.assert_called_once()

    @patch("app.services.store_singleton.settings")
    def test_get_llm_client_missing_api_key(self, mock_settings):
        """Test that missing API key raises LLMConfigurationError."""
        # Setup settings with empty API key
        mock_settings.llm_api_key = ""
        mock_settings.llm_model = "gpt-5.1"

        # Try to get client
        with pytest.raises(LLMConfigurationError) as exc_info:
            get_llm_client()

        assert "api key" in str(exc_info.value).lower()

    @patch("app.services.store_singleton.settings")
    @patch("app.services.store_singleton.OpenAIClient")
    def test_get_llm_client_initialization_error(self, mock_client_class, mock_settings):
        """Test that client initialization errors are handled."""
        # Setup settings
        mock_settings.llm_api_key = "sk-test-key"
        mock_settings.llm_model = "gpt-5.1"
        mock_settings.llm_base_url = None
        mock_settings.llm_timeout = 60

        # Mock client to raise error
        mock_client_class.side_effect = Exception("OpenAI SDK error")

        # Try to get client
        with pytest.raises(LLMConfigurationError) as exc_info:
            get_llm_client()

        assert "failed to initialize" in str(exc_info.value).lower()

    @patch("app.services.store_singleton.settings")
    @patch("app.services.store_singleton.OpenAIClient")
    def test_get_llm_client_reraises_configuration_error(self, mock_client_class, mock_settings):
        """Test that LLMConfigurationError is re-raised as-is."""
        # Setup settings
        mock_settings.llm_api_key = "sk-test-key"
        mock_settings.llm_model = "gpt-5.1"
        mock_settings.llm_base_url = None
        mock_settings.llm_timeout = 60

        # Mock client to raise LLMConfigurationError
        original_error = LLMConfigurationError("Invalid model")
        mock_client_class.side_effect = original_error

        # Try to get client
        with pytest.raises(LLMConfigurationError) as exc_info:
            get_llm_client()

        # Verify it's the same error (not wrapped)
        assert exc_info.value is original_error
