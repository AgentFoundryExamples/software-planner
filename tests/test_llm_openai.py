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
"""Tests for OpenAI LLM client implementation."""

import json
from unittest.mock import MagicMock, Mock, patch

import openai
import pytest

from app.services.llm_client import LLMConfigurationError, LLMRequestError, LLMResponseError
from app.services.llm_openai import OpenAIClient

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


def create_mock_openai_response(content: str) -> Mock:
    """Create a mock OpenAI Responses API response.

    Args:
        content: Response content text.

    Returns:
        Mock response object matching OpenAI Responses API structure.
    """
    response = Mock()

    # Responses API returns 'output' array instead of 'choices'
    output_item = Mock()
    output_item.role = "assistant"
    output_item.content = content  # Can be string or array of content items

    response.output = [output_item]

    # Usage structure is similar
    response.usage = Mock()
    response.usage.input_tokens = 50
    response.usage.output_tokens = 50
    response.usage.total_tokens = 100

    return response


class TestOpenAIClientInitialization:
    """Tests for OpenAI client initialization."""

    @patch("app.services.llm_openai.OpenAI")
    def test_initialization_with_minimal_config(self, mock_openai_class):
        """Test initialization with minimal required configuration."""
        client = OpenAIClient(api_key="sk-test", model="gpt-5.1")

        assert client.api_key == "sk-test"
        assert client.model == "gpt-5.1"
        assert client.base_url is None
        assert client.timeout == 60
        assert client.max_retries == 3

        # Verify OpenAI client was initialized
        mock_openai_class.assert_called_once_with(
            api_key="sk-test",
            timeout=60,
        )

    @patch("app.services.llm_openai.OpenAI")
    def test_initialization_with_full_config(self, mock_openai_class):
        """Test initialization with all configuration options."""
        client = OpenAIClient(
            api_key="sk-test",
            model="gpt-5.1",
            base_url="https://custom.api.com/v1",
            timeout=120,
            max_retries=5,
            initial_backoff=2.0,
            max_backoff=20.0,
            backoff_multiplier=3.0,
        )

        assert client.api_key == "sk-test"
        assert client.model == "gpt-5.1"
        assert client.base_url == "https://custom.api.com/v1"
        assert client.timeout == 120
        assert client.max_retries == 5
        assert client.initial_backoff == 2.0
        assert client.max_backoff == 20.0
        assert client.backoff_multiplier == 3.0

        # Verify OpenAI client was initialized with base_url
        mock_openai_class.assert_called_once_with(
            api_key="sk-test",
            timeout=120,
            base_url="https://custom.api.com/v1",
        )

    @patch("app.services.llm_openai.OpenAI")
    def test_initialization_invalid_max_retries(self, mock_openai_class):
        """Test that negative max_retries raises error."""
        with pytest.raises(LLMConfigurationError) as exc_info:
            OpenAIClient(api_key="sk-test", model="gpt-5.1", max_retries=-1)
        assert "max_retries" in str(exc_info.value).lower()

    @patch("app.services.llm_openai.OpenAI")
    def test_initialization_invalid_backoff(self, mock_openai_class):
        """Test that invalid backoff configuration raises error."""
        with pytest.raises(LLMConfigurationError) as exc_info:
            OpenAIClient(api_key="sk-test", model="gpt-5.1", initial_backoff=0.0)
        assert "backoff" in str(exc_info.value).lower()

    @patch("app.services.llm_openai.OpenAI")
    def test_initialization_invalid_backoff_range(self, mock_openai_class):
        """Test that max_backoff < initial_backoff raises error."""
        with pytest.raises(LLMConfigurationError) as exc_info:
            OpenAIClient(api_key="sk-test", model="gpt-5.1", initial_backoff=10.0, max_backoff=5.0)
        assert "max_backoff" in str(exc_info.value).lower()

    @patch("app.services.llm_openai.OpenAI")
    def test_initialization_invalid_multiplier(self, mock_openai_class):
        """Test that backoff_multiplier < 1.0 raises error."""
        with pytest.raises(LLMConfigurationError) as exc_info:
            OpenAIClient(api_key="sk-test", model="gpt-5.1", backoff_multiplier=0.5)
        assert "multiplier" in str(exc_info.value).lower()

    @patch("app.services.llm_openai.OpenAI")
    def test_initialization_openai_error(self, mock_openai_class):
        """Test that OpenAI initialization errors are handled."""
        mock_openai_class.side_effect = Exception("OpenAI SDK error")

        with pytest.raises(LLMConfigurationError) as exc_info:
            OpenAIClient(api_key="sk-test", model="gpt-5.1")

        assert "failed to initialize" in str(exc_info.value).lower()


class TestOpenAIClientAPICall:
    """Tests for OpenAI API call functionality."""

    @patch("app.services.llm_openai.OpenAI")
    def test_successful_api_call(self, mock_openai_class):
        """Test successful API call with valid response."""
        # Setup mock
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        response_content = json.dumps(VALID_RESPONSE)
        mock_client.responses.create.return_value = create_mock_openai_response(response_content)

        # Create client and call API
        client = OpenAIClient(api_key="sk-test", model="gpt-5.1")
        result = client.generate_specs("Build a REST API")

        # Verify result
        assert "specs" in result
        assert len(result["specs"]) == 1
        assert result["specs"][0]["purpose"] == "Test Purpose"

        # Verify API was called correctly with Responses API
        mock_client.responses.create.assert_called_once()
        call_args = mock_client.responses.create.call_args
        assert call_args[1]["model"] == "gpt-5.1"
        assert "instructions" in call_args[1]
        assert "input" in call_args[1]
        assert call_args[1]["input"] == "Build a REST API"

    @patch("app.services.llm_openai.OpenAI")
    def test_api_call_with_markdown_wrapped_response(self, mock_openai_class):
        """Test that markdown-wrapped JSON is properly handled."""
        # Setup mock
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        response_content = f"```json\n{json.dumps(VALID_RESPONSE)}\n```"
        mock_client.responses.create.return_value = create_mock_openai_response(response_content)

        # Create client and call API
        client = OpenAIClient(api_key="sk-test", model="gpt-5.1")
        result = client.generate_specs("Build a REST API")

        # Verify result was parsed correctly
        assert "specs" in result
        assert len(result["specs"]) == 1

    @patch("app.services.llm_openai.OpenAI")
    def test_api_call_authentication_error(self, mock_openai_class):
        """Test that authentication errors are not retried."""
        # Setup mock
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        mock_client.responses.create.side_effect = openai.AuthenticationError(
            "Invalid API key", response=Mock(status_code=401), body=None
        )

        # Create client and call API
        client = OpenAIClient(api_key="sk-test", model="gpt-5.1")

        with pytest.raises(LLMConfigurationError) as exc_info:
            client.generate_specs("Build a REST API")

        assert "authentication" in str(exc_info.value).lower()

        # Verify API was called only once (no retries)
        assert mock_client.responses.create.call_count == 1

    @patch("app.services.llm_openai.OpenAI")
    def test_api_call_not_found_error(self, mock_openai_class):
        """Test that not found errors are not retried."""
        # Setup mock
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        mock_client.responses.create.side_effect = openai.NotFoundError(
            "Model not found", response=Mock(status_code=404), body=None
        )

        # Create client and call API
        client = OpenAIClient(api_key="sk-test", model="gpt-5.1")

        with pytest.raises(LLMConfigurationError) as exc_info:
            client.generate_specs("Build a REST API")

        assert "not found" in str(exc_info.value).lower()

        # Verify API was called only once (no retries)
        assert mock_client.responses.create.call_count == 1

    @patch("app.services.llm_openai.OpenAI")
    def test_api_call_bad_request_error(self, mock_openai_class):
        """Test that bad request errors are not retried."""
        # Setup mock
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        mock_client.responses.create.side_effect = openai.BadRequestError(
            "Invalid request", response=Mock(status_code=400), body=None
        )

        # Create client and call API
        client = OpenAIClient(api_key="sk-test", model="gpt-5.1")

        with pytest.raises(LLMRequestError) as exc_info:
            client.generate_specs("Build a REST API")

        assert "invalid request" in str(exc_info.value).lower()

        # Verify API was called only once (no retries)
        assert mock_client.responses.create.call_count == 1

    @patch("app.services.llm_openai.OpenAI")
    @patch("time.sleep")  # Mock sleep to speed up test
    def test_api_call_timeout_with_retry(self, mock_sleep, mock_openai_class):
        """Test that timeout errors trigger retry."""
        # Setup mock
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        # First two calls timeout, third succeeds
        response_content = json.dumps(VALID_RESPONSE)
        mock_client.responses.create.side_effect = [
            openai.APITimeoutError("Request timeout"),
            openai.APITimeoutError("Request timeout"),
            create_mock_openai_response(response_content),
        ]

        # Create client and call API
        client = OpenAIClient(api_key="sk-test", model="gpt-5.1")
        result = client.generate_specs("Build a REST API")

        # Verify result
        assert "specs" in result

        # Verify API was called 3 times (2 failures + 1 success)
        assert mock_client.responses.create.call_count == 3

        # Verify sleep was called for backoff
        assert mock_sleep.call_count == 2

    @patch("app.services.llm_openai.OpenAI")
    @patch("time.sleep")  # Mock sleep to speed up test
    def test_api_call_rate_limit_with_retry(self, mock_sleep, mock_openai_class):
        """Test that rate limit errors trigger retry."""
        # Setup mock
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        # First call rate limited, second succeeds
        response_content = json.dumps(VALID_RESPONSE)
        mock_client.responses.create.side_effect = [
            openai.RateLimitError("Rate limit exceeded", response=Mock(status_code=429), body=None),
            create_mock_openai_response(response_content),
        ]

        # Create client and call API
        client = OpenAIClient(api_key="sk-test", model="gpt-5.1")
        result = client.generate_specs("Build a REST API")

        # Verify result
        assert "specs" in result

        # Verify API was called 2 times (1 failure + 1 success)
        assert mock_client.responses.create.call_count == 2

    @patch("app.services.llm_openai.OpenAI")
    @patch("time.sleep")  # Mock sleep to speed up test
    def test_api_call_5xx_error_with_retry(self, mock_sleep, mock_openai_class):
        """Test that 5xx errors trigger retry."""
        # Setup mock
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        # Create a proper InternalServerError
        response_content = json.dumps(VALID_RESPONSE)
        mock_client.responses.create.side_effect = [
            openai.InternalServerError(
                "Internal server error", response=Mock(status_code=500), body=None
            ),
            create_mock_openai_response(response_content),
        ]

        # Create client and call API
        client = OpenAIClient(api_key="sk-test", model="gpt-5.1")
        result = client.generate_specs("Build a REST API")

        # Verify result
        assert "specs" in result

        # Verify API was called 2 times (1 failure + 1 success)
        assert mock_client.responses.create.call_count == 2

    @patch("app.services.llm_openai.OpenAI")
    @patch("time.sleep")  # Mock sleep to speed up test
    def test_api_call_exhausted_retries(self, mock_sleep, mock_openai_class):
        """Test that errors after exhausted retries raise LLMRequestError."""
        # Setup mock
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        # All calls fail with timeout
        mock_client.responses.create.side_effect = openai.APITimeoutError("Request timeout")

        # Create client with 2 max retries
        client = OpenAIClient(api_key="sk-test", model="gpt-5.1", max_retries=2)

        with pytest.raises(LLMRequestError) as exc_info:
            client.generate_specs("Build a REST API")

        assert "failed after 2 retries" in str(exc_info.value).lower()

        # Verify API was called 3 times (initial + 2 retries)
        assert mock_client.responses.create.call_count == 3

    @patch("app.services.llm_openai.OpenAI")
    def test_api_call_empty_choices(self, mock_openai_class):
        """Test that empty output raises error."""
        # Setup mock
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        response = Mock()
        response.output = []
        mock_client.responses.create.return_value = response

        # Create client and call API
        client = OpenAIClient(api_key="sk-test", model="gpt-5.1")

        with pytest.raises(LLMResponseError) as exc_info:
            client.generate_specs("Build a REST API")

        assert "empty output" in str(exc_info.value).lower()

    @patch("app.services.llm_openai.OpenAI")
    def test_api_call_empty_content(self, mock_openai_class):
        """Test that empty content raises error."""
        # Setup mock
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        response = Mock()
        output_item = Mock()
        output_item.content = None
        response.output = [output_item]
        mock_client.responses.create.return_value = response

        # Create client and call API
        client = OpenAIClient(api_key="sk-test", model="gpt-5.1")

        with pytest.raises(LLMResponseError) as exc_info:
            client.generate_specs("Build a REST API")

        assert "empty content" in str(exc_info.value).lower()


class TestOpenAIClientRetryLogic:
    """Tests for retry logic and backoff behavior."""

    def test_is_retryable_error_timeout(self):
        """Test that timeout errors are identified as retryable."""
        client = OpenAIClient.__new__(OpenAIClient)
        error = openai.APITimeoutError("Timeout")
        assert client._is_retryable_error(error) is True

    def test_is_retryable_error_rate_limit(self):
        """Test that rate limit errors are identified as retryable."""
        client = OpenAIClient.__new__(OpenAIClient)
        error = openai.RateLimitError("Rate limit", response=Mock(status_code=429), body=None)
        assert client._is_retryable_error(error) is True

    def test_is_retryable_error_connection(self):
        """Test that connection errors are identified as retryable."""
        client = OpenAIClient.__new__(OpenAIClient)
        error = openai.APIConnectionError(request=Mock())
        assert client._is_retryable_error(error) is True

    def test_is_retryable_error_server_error(self):
        """Test that internal server errors are identified as retryable."""
        client = OpenAIClient.__new__(OpenAIClient)
        error = openai.InternalServerError(
            "Server error", response=Mock(status_code=500), body=None
        )
        assert client._is_retryable_error(error) is True

    def test_is_retryable_error_authentication(self):
        """Test that authentication errors are not retryable."""
        client = OpenAIClient.__new__(OpenAIClient)
        error = openai.AuthenticationError("Auth failed", response=Mock(status_code=401), body=None)
        assert client._is_retryable_error(error) is False

    def test_is_retryable_error_bad_request(self):
        """Test that bad request errors are not retryable."""
        client = OpenAIClient.__new__(OpenAIClient)
        error = openai.BadRequestError("Bad request", response=Mock(status_code=400), body=None)
        assert client._is_retryable_error(error) is False

    @patch("app.services.llm_openai.OpenAI")
    @patch("time.sleep")
    def test_exponential_backoff(self, mock_sleep, mock_openai_class):
        """Test that backoff increases exponentially."""
        # Setup mock
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        # All calls fail
        mock_client.responses.create.side_effect = openai.APITimeoutError("Timeout")

        # Create client with specific backoff settings
        client = OpenAIClient(
            api_key="sk-test",
            model="gpt-5.1",
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

    @patch("app.services.llm_openai.OpenAI")
    @patch("time.sleep")
    def test_max_backoff_limit(self, mock_sleep, mock_openai_class):
        """Test that backoff is capped at max_backoff."""
        # Setup mock
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        # All calls fail
        mock_client.responses.create.side_effect = openai.APITimeoutError("Timeout")

        # Create client with low max_backoff
        client = OpenAIClient(
            api_key="sk-test",
            model="gpt-5.1",
            max_retries=3,
            initial_backoff=5.0,
            backoff_multiplier=2.0,
            max_backoff=6.0,  # Cap at 6 seconds
        )

        with pytest.raises(LLMRequestError):
            client.generate_specs("Build a REST API")

        # Verify backoff is capped: 5.0, 6.0 (capped), 6.0 (capped)
        sleep_calls = [call[0][0] for call in mock_sleep.call_args_list]
        assert sleep_calls[0] == 5.0
        assert sleep_calls[1] == 6.0
        assert sleep_calls[2] == 6.0


class TestOpenAIClientEdgeCases:
    """Tests for edge cases and error scenarios."""

    @patch("app.services.llm_openai.OpenAI")
    def test_non_json_response(self, mock_openai_class):
        """Test that non-JSON responses raise appropriate error."""
        # Setup mock
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        mock_client.responses.create.return_value = create_mock_openai_response("This is not JSON")

        # Create client and call API
        client = OpenAIClient(api_key="sk-test", model="gpt-5.1")

        with pytest.raises(LLMResponseError) as exc_info:
            client.generate_specs("Build a REST API")

        assert "json" in str(exc_info.value).lower()

    @patch("app.services.llm_openai.OpenAI")
    def test_multi_part_content_response(self, mock_openai_class):
        """Test that multi-part content arrays are concatenated correctly."""
        # Setup mock
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        # Create response with content as an array of parts
        response = Mock()
        output_item = Mock()

        # Mock content parts
        part1 = Mock()
        part1.text = '{"specs": ['
        part2 = Mock()
        part2.text = json.dumps(
            {
                "purpose": "Test Purpose",
                "vision": "Test Vision",
                "must": ["requirement1"],
                "dont": ["avoid1"],
                "nice": ["feature1"],
            }
        )
        part3 = Mock()
        part3.text = "]}"

        output_item.content = [part1, part2, part3]
        response.output = [output_item]
        response.usage = Mock()
        response.usage.input_tokens = 50
        response.usage.output_tokens = 50

        mock_client.responses.create.return_value = response

        # Create client and call API
        client = OpenAIClient(api_key="sk-test", model="gpt-5.1")
        result = client.generate_specs("Build a REST API")

        # Verify result was parsed correctly
        assert "specs" in result
        assert len(result["specs"]) == 1
        assert result["specs"][0]["purpose"] == "Test Purpose"

    @patch("app.services.llm_openai.OpenAI")
    def test_multi_part_content_with_dicts(self, mock_openai_class):
        """Test that multi-part content with dict format is handled correctly."""
        # Setup mock
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        # Create response with content as an array of dict parts
        response = Mock()
        output_item = Mock()

        # Mock content parts as dicts
        output_item.content = [
            {"text": '{"specs": ['},
            {
                "text": json.dumps(
                    {
                        "purpose": "Test Purpose",
                        "vision": "Test Vision",
                        "must": ["requirement1"],
                        "dont": ["avoid1"],
                        "nice": ["feature1"],
                    }
                )
            },
            {"text": "]}"},
        ]
        response.output = [output_item]
        response.usage = Mock()
        response.usage.input_tokens = 50
        response.usage.output_tokens = 50

        mock_client.responses.create.return_value = response

        # Create client and call API
        client = OpenAIClient(api_key="sk-test", model="gpt-5.1")
        result = client.generate_specs("Build a REST API")

        # Verify result was parsed correctly
        assert "specs" in result
        assert len(result["specs"]) == 1
        assert result["specs"][0]["purpose"] == "Test Purpose"

    @patch("app.services.llm_openai.OpenAI")
    def test_unsupported_content_type(self, mock_openai_class):
        """Test that unsupported content types are handled gracefully."""
        # Setup mock
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        # Create response with unexpected content type
        response = Mock()
        output_item = Mock()
        output_item.content = 12345  # Numeric content (unsupported)
        response.output = [output_item]
        response.usage = Mock()
        response.usage.input_tokens = 50
        response.usage.output_tokens = 50

        mock_client.responses.create.return_value = response

        # Create client and call API
        client = OpenAIClient(api_key="sk-test", model="gpt-5.1")

        with pytest.raises(LLMResponseError) as exc_info:
            client.generate_specs("Build a REST API")

        assert "empty content" in str(exc_info.value).lower()

    @patch("app.services.llm_openai.OpenAI")
    def test_zero_retries(self, mock_openai_class):
        """Test client with max_retries=0 doesn't retry."""
        # Setup mock
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        mock_client.responses.create.side_effect = openai.APITimeoutError("Timeout")

        # Create client with no retries
        client = OpenAIClient(api_key="sk-test", model="gpt-5.1", max_retries=0)

        with pytest.raises(LLMRequestError):
            client.generate_specs("Build a REST API")

        # Verify API was called only once
        assert mock_client.responses.create.call_count == 1
