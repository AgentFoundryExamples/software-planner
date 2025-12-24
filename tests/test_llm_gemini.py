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
"""Tests for Gemini (Google) LLM client implementation."""

import json
from unittest.mock import MagicMock, Mock, patch

import pytest

from app.services.llm_client import LLMConfigurationError, LLMRequestError, LLMResponseError
from app.services.llm_gemini import GeminiClient

# Valid test response that matches expected schema
VALID_RESPONSE = {
    "specs": [
        {
            "purpose": "Test Purpose",
            "vision": "Test Vision",
            "must": ["requirement1"],
            "dont": ["avoid1"],
            "nice": ["feature1"],
        }
    ]
}


def create_mock_gemini_response(content: str) -> Mock:
    """Create a mock Gemini API response.

    Args:
        content: Response content text.

    Returns:
        Mock response object matching Gemini API structure.
    """
    response = Mock()
    response.text = content

    # Mock usage metadata
    usage_metadata = Mock()
    usage_metadata.prompt_token_count = 50
    usage_metadata.candidates_token_count = 100
    response.usage_metadata = usage_metadata

    return response


class TestGeminiClientInitialization:
    """Tests for Gemini client initialization."""

    @patch("app.services.llm_gemini.genai.Client")
    def test_initialization_with_minimal_config(self, mock_genai_class):
        """Test initialization with minimal required configuration."""
        client = GeminiClient(api_key="test-api-key", model="gemini-3.0-pro")

        assert client.api_key == "test-api-key"
        assert client.model == "gemini-3.0-pro"
        assert client.base_url is None
        assert client.timeout == 60
        assert client.max_retries == 3

        # Verify GenAI client was initialized
        mock_genai_class.assert_called_once_with(api_key="test-api-key")

    @patch("app.services.llm_gemini.genai.Client")
    def test_initialization_with_full_config(self, mock_genai_class):
        """Test initialization with all configuration options."""
        client = GeminiClient(
            api_key="test-api-key",
            model="gemini-2.0-flash",
            base_url="https://custom.api.com",  # Will be ignored with warning
            timeout=120,
            max_retries=5,
            initial_backoff=2.0,
            max_backoff=20.0,
            backoff_multiplier=3.0,
        )

        assert client.api_key == "test-api-key"
        assert client.model == "gemini-2.0-flash"
        assert client.timeout == 120
        assert client.max_retries == 5

    @patch("app.services.llm_gemini.genai.Client")
    def test_initialization_invalid_config(self, mock_genai_class):
        """Test that invalid configuration raises errors."""
        with pytest.raises(LLMConfigurationError):
            GeminiClient(api_key="test-api-key", model="gemini-3.0-pro", max_retries=-1)


class TestGeminiClientAPICall:
    """Tests for Gemini API call functionality."""

    @patch("app.services.llm_gemini.genai.Client")
    def test_successful_api_call(self, mock_genai_class):
        """Test successful API call with valid response."""
        # Setup mock
        mock_client = Mock()
        mock_genai_class.return_value = mock_client

        response_content = json.dumps(VALID_RESPONSE)
        mock_client.models.generate_content.return_value = create_mock_gemini_response(
            response_content
        )

        # Create client and call API
        client = GeminiClient(api_key="test-api-key", model="gemini-3.0-pro")
        result = client.generate_specs("Build a REST API")

        # Verify result
        assert "specs" in result
        assert len(result["specs"]) == 1
        assert result["specs"][0]["purpose"] == "Test Purpose"

        # Verify API was called correctly
        mock_client.models.generate_content.assert_called_once()
        call_kwargs = mock_client.models.generate_content.call_args[1]
        assert call_kwargs["model"] == "gemini-3.0-pro"
        assert "Build a REST API" in call_kwargs["contents"]

    @patch("app.services.llm_gemini.genai.Client")
    def test_api_call_with_markdown_wrapped_response(self, mock_genai_class):
        """Test that markdown-wrapped JSON is properly handled."""
        # Setup mock
        mock_client = Mock()
        mock_genai_class.return_value = mock_client

        response_content = f"```json\n{json.dumps(VALID_RESPONSE)}\n```"
        mock_client.models.generate_content.return_value = create_mock_gemini_response(
            response_content
        )

        # Create client and call API
        client = GeminiClient(api_key="test-api-key", model="gemini-3.0-pro")
        result = client.generate_specs("Build a REST API")

        # Verify result was parsed correctly
        assert "specs" in result
        assert len(result["specs"]) == 1

    @patch("app.services.llm_gemini.genai.Client")
    def test_api_call_authentication_error(self, mock_genai_class):
        """Test that authentication errors are not retried."""
        # Setup mock
        mock_client = Mock()
        mock_genai_class.return_value = mock_client

        mock_client.models.generate_content.side_effect = Exception("401: Authentication failed")

        # Create client and call API
        client = GeminiClient(api_key="test-api-key", model="gemini-3.0-pro")

        with pytest.raises(LLMConfigurationError) as exc_info:
            client.generate_specs("Build a REST API")

        assert "authentication" in str(exc_info.value).lower()

        # Verify API was called only once (no retries)
        assert mock_client.models.generate_content.call_count == 1

    @patch("app.services.llm_gemini.genai.Client")
    @patch("time.sleep")  # Mock sleep to speed up test
    def test_api_call_rate_limit_with_retry(self, mock_sleep, mock_genai_class):
        """Test that rate limit errors trigger retry."""
        # Setup mock
        mock_client = Mock()
        mock_genai_class.return_value = mock_client

        # First call rate limited, second succeeds
        response_content = json.dumps(VALID_RESPONSE)
        mock_client.models.generate_content.side_effect = [
            Exception("429: Rate limit exceeded"),
            create_mock_gemini_response(response_content),
        ]

        # Create client and call API
        client = GeminiClient(api_key="test-api-key", model="gemini-3.0-pro")
        result = client.generate_specs("Build a REST API")

        # Verify result
        assert "specs" in result

        # Verify API was called 2 times (1 failure + 1 success)
        assert mock_client.models.generate_content.call_count == 2

    @patch("app.services.llm_gemini.genai.Client")
    def test_api_call_empty_response(self, mock_genai_class):
        """Test that empty response raises error."""
        # Setup mock
        mock_client = Mock()
        mock_genai_class.return_value = mock_client

        response = Mock()
        response.text = None
        mock_client.models.generate_content.return_value = response

        # Create client and call API
        client = GeminiClient(api_key="test-api-key", model="gemini-3.0-pro")

        with pytest.raises(LLMResponseError) as exc_info:
            client.generate_specs("Build a REST API")

        assert "empty" in str(exc_info.value).lower()


class TestGeminiClientRetryLogic:
    """Tests for retry logic and backoff behavior."""

    def test_is_retryable_error_rate_limit(self):
        """Test that rate limit errors are identified as retryable."""
        client = GeminiClient.__new__(GeminiClient)
        error = Exception("429: Rate limit exceeded")
        assert client._is_retryable_error(error) is True

    def test_is_retryable_error_timeout(self):
        """Test that timeout errors are identified as retryable."""
        client = GeminiClient.__new__(GeminiClient)
        error = Exception("Request timeout")
        assert client._is_retryable_error(error) is True

    def test_is_retryable_error_authentication(self):
        """Test that authentication errors are not retryable."""
        client = GeminiClient.__new__(GeminiClient)
        error = Exception("401: Authentication failed")
        # Will be caught by auth check in _call_llm_api, not _is_retryable_error
        assert client._is_retryable_error(error) is False

    @patch("app.services.llm_gemini.genai.Client")
    @patch("time.sleep")
    def test_exponential_backoff(self, mock_sleep, mock_genai_class):
        """Test that backoff increases exponentially."""
        # Setup mock
        mock_client = Mock()
        mock_genai_class.return_value = mock_client

        # All calls fail with timeout
        mock_client.models.generate_content.side_effect = Exception("Timeout error")

        # Create client with specific backoff settings
        client = GeminiClient(
            api_key="test-api-key",
            model="gemini-3.0-pro",
            max_retries=3,
            initial_backoff=1.0,
            backoff_multiplier=2.0,
            max_backoff=10.0,
        )

        with pytest.raises(LLMRequestError):
            client.generate_specs("Build a REST API")

        # Verify backoff progression: 1.0, 2.0, 4.0
        assert mock_sleep.call_count == 3
        sleep_calls = [call[0][0] for call in mock_sleep.call_args_list]
        assert sleep_calls[0] == 1.0
        assert sleep_calls[1] == 2.0
        assert sleep_calls[2] == 4.0

    @patch("app.services.llm_gemini.genai.Client")
    @patch("time.sleep")
    def test_server_error_retry(self, mock_sleep, mock_genai_class):
        """Test that 5xx server errors trigger retry."""
        # Setup mock
        mock_client = Mock()
        mock_genai_class.return_value = mock_client

        # First call server error, second succeeds
        response_content = json.dumps(VALID_RESPONSE)
        mock_client.models.generate_content.side_effect = [
            Exception("503: Service unavailable"),
            create_mock_gemini_response(response_content),
        ]

        # Create client and call API
        client = GeminiClient(api_key="test-api-key", model="gemini-3.0-pro")
        result = client.generate_specs("Build a REST API")

        # Verify result
        assert "specs" in result

        # Verify API was called 2 times (1 failure + 1 success)
        assert mock_client.models.generate_content.call_count == 2
