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
"""Tests for Claude (Anthropic) LLM client implementation."""

import json
from unittest.mock import Mock, patch, MagicMock
import pytest

import anthropic
from app.services.llm_claude import ClaudeClient
from app.services.llm_client import (
    LLMConfigurationError,
    LLMRequestError,
    LLMResponseError,
)


# Valid test response that matches expected schema
VALID_RESPONSE = {
    "specs": [
        {
            "purpose": "Test Purpose",
            "vision": "Test Vision",
            "must": ["requirement1"],
            "dont": ["avoid1"],
            "nice": ["feature1"]
        }
    ]
}


def create_mock_claude_response(content: str, stop_reason: str = "end_turn") -> Mock:
    """Create a mock Claude API response.
    
    Args:
        content: Response content text.
        stop_reason: Completion stop reason.
        
    Returns:
        Mock response object matching Claude API structure.
    """
    response = Mock()
    
    # Claude returns content as list of content blocks
    content_block = Mock()
    content_block.text = content
    response.content = [content_block]
    
    response.usage = Mock()
    response.usage.input_tokens = 50
    response.usage.output_tokens = 100
    response.stop_reason = stop_reason
    
    return response


class TestClaudeClientInitialization:
    """Tests for Claude client initialization."""
    
    @patch('app.services.llm_claude.Anthropic')
    def test_initialization_with_minimal_config(self, mock_anthropic_class):
        """Test initialization with minimal required configuration."""
        client = ClaudeClient(api_key="sk-ant-test", model="claude-sonnet-4.5")
        
        assert client.api_key == "sk-ant-test"
        assert client.model == "claude-sonnet-4.5"
        assert client.base_url is None
        assert client.timeout == 60
        assert client.max_retries == 3
        
        # Verify Anthropic client was initialized
        mock_anthropic_class.assert_called_once_with(
            api_key="sk-ant-test",
            timeout=60,
        )
    
    @patch('app.services.llm_claude.Anthropic')
    def test_initialization_with_full_config(self, mock_anthropic_class):
        """Test initialization with all configuration options."""
        client = ClaudeClient(
            api_key="sk-ant-test",
            model="claude-opus-4",
            base_url="https://custom.api.com",
            timeout=120,
            max_retries=5,
            initial_backoff=2.0,
            max_backoff=20.0,
            backoff_multiplier=3.0,
        )
        
        assert client.api_key == "sk-ant-test"
        assert client.model == "claude-opus-4"
        assert client.base_url == "https://custom.api.com"
        assert client.timeout == 120
        assert client.max_retries == 5
        assert client.initial_backoff == 2.0
        assert client.max_backoff == 20.0
        assert client.backoff_multiplier == 3.0
        
        # Verify Anthropic client was initialized with base_url
        mock_anthropic_class.assert_called_once_with(
            api_key="sk-ant-test",
            timeout=120,
            base_url="https://custom.api.com",
        )
    
    @patch('app.services.llm_claude.Anthropic')
    def test_initialization_invalid_config(self, mock_anthropic_class):
        """Test that invalid configuration raises errors."""
        with pytest.raises(LLMConfigurationError):
            ClaudeClient(
                api_key="sk-ant-test",
                model="claude-sonnet-4.5",
                max_retries=-1
            )


class TestClaudeClientAPICall:
    """Tests for Claude API call functionality."""
    
    @patch('app.services.llm_claude.Anthropic')
    def test_successful_api_call(self, mock_anthropic_class):
        """Test successful API call with valid response."""
        # Setup mock
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client
        
        response_content = json.dumps(VALID_RESPONSE)
        mock_client.messages.create.return_value = create_mock_claude_response(
            response_content
        )
        
        # Create client and call API
        client = ClaudeClient(api_key="sk-ant-test", model="claude-sonnet-4.5")
        result = client.generate_specs("Build a REST API")
        
        # Verify result
        assert "specs" in result
        assert len(result["specs"]) == 1
        assert result["specs"][0]["purpose"] == "Test Purpose"
        
        # Verify API was called correctly
        mock_client.messages.create.assert_called_once()
        call_kwargs = mock_client.messages.create.call_args[1]
        assert call_kwargs["model"] == "claude-sonnet-4.5"
        assert call_kwargs["max_tokens"] == 2000
        assert len(call_kwargs["messages"]) == 1
        assert call_kwargs["messages"][0]["role"] == "user"
        assert call_kwargs["messages"][0]["content"] == "Build a REST API"
    
    @patch('app.services.llm_claude.Anthropic')
    def test_api_call_with_markdown_wrapped_response(self, mock_anthropic_class):
        """Test that markdown-wrapped JSON is properly handled."""
        # Setup mock
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client
        
        response_content = f"```json\n{json.dumps(VALID_RESPONSE)}\n```"
        mock_client.messages.create.return_value = create_mock_claude_response(
            response_content
        )
        
        # Create client and call API
        client = ClaudeClient(api_key="sk-ant-test", model="claude-sonnet-4.5")
        result = client.generate_specs("Build a REST API")
        
        # Verify result was parsed correctly
        assert "specs" in result
        assert len(result["specs"]) == 1
    
    @patch('app.services.llm_claude.Anthropic')
    def test_api_call_authentication_error(self, mock_anthropic_class):
        """Test that authentication errors are not retried."""
        # Setup mock
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client
        
        mock_client.messages.create.side_effect = anthropic.AuthenticationError(
            "Invalid API key",
            response=Mock(status_code=401),
            body=None
        )
        
        # Create client and call API
        client = ClaudeClient(api_key="sk-ant-test", model="claude-sonnet-4.5")
        
        with pytest.raises(LLMConfigurationError) as exc_info:
            client.generate_specs("Build a REST API")
        
        assert "authentication" in str(exc_info.value).lower()
        
        # Verify API was called only once (no retries)
        assert mock_client.messages.create.call_count == 1
    
    @patch('app.services.llm_claude.Anthropic')
    @patch('time.sleep')  # Mock sleep to speed up test
    def test_api_call_rate_limit_with_retry(self, mock_sleep, mock_anthropic_class):
        """Test that rate limit errors trigger retry."""
        # Setup mock
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client
        
        # First call rate limited, second succeeds
        response_content = json.dumps(VALID_RESPONSE)
        mock_client.messages.create.side_effect = [
            anthropic.RateLimitError(
                "Rate limit exceeded",
                response=Mock(status_code=429),
                body=None
            ),
            create_mock_claude_response(response_content),
        ]
        
        # Create client and call API
        client = ClaudeClient(api_key="sk-ant-test", model="claude-sonnet-4.5")
        result = client.generate_specs("Build a REST API")
        
        # Verify result
        assert "specs" in result
        
        # Verify API was called 2 times (1 failure + 1 success)
        assert mock_client.messages.create.call_count == 2
    
    @patch('app.services.llm_claude.Anthropic')
    def test_api_call_empty_content(self, mock_anthropic_class):
        """Test that empty content raises error."""
        # Setup mock
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client
        
        response = Mock()
        response.content = []
        mock_client.messages.create.return_value = response
        
        # Create client and call API
        client = ClaudeClient(api_key="sk-ant-test", model="claude-sonnet-4.5")
        
        with pytest.raises(LLMResponseError) as exc_info:
            client.generate_specs("Build a REST API")
        
        assert "empty" in str(exc_info.value).lower()


class TestClaudeClientRetryLogic:
    """Tests for retry logic and backoff behavior."""
    
    def test_is_retryable_error_rate_limit(self):
        """Test that rate limit errors are identified as retryable."""
        client = ClaudeClient.__new__(ClaudeClient)
        error = anthropic.RateLimitError(
            "Rate limit",
            response=Mock(status_code=429),
            body=None
        )
        assert client._is_retryable_error(error) is True
    
    def test_is_retryable_error_authentication(self):
        """Test that authentication errors are not retryable."""
        client = ClaudeClient.__new__(ClaudeClient)
        error = anthropic.AuthenticationError(
            "Auth failed",
            response=Mock(status_code=401),
            body=None
        )
        assert client._is_retryable_error(error) is False
    
    @patch('app.services.llm_claude.Anthropic')
    @patch('time.sleep')
    def test_exponential_backoff(self, mock_sleep, mock_anthropic_class):
        """Test that backoff increases exponentially."""
        # Setup mock
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client
        
        # All calls fail
        mock_client.messages.create.side_effect = anthropic.APITimeoutError(
            "Timeout"
        )
        
        # Create client with specific backoff settings
        client = ClaudeClient(
            api_key="sk-ant-test",
            model="claude-sonnet-4.5",
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
