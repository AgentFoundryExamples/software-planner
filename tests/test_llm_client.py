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
"""Tests for LLM client abstraction."""

import json
from unittest.mock import patch

import pytest

from app.services.llm_client import (
    DEFAULT_SYSTEM_PROMPT,
    BaseLLMClient,
    LLMConfigurationError,
    LLMError,
    LLMRequestError,
    LLMResponseError,
    get_default_system_prompt,
)


class MockLLMClient(BaseLLMClient):
    """Mock LLM client for testing."""

    def __init__(self, *args, response_text: str = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.response_text = response_text
        self.last_description = None
        self.last_system_prompt = None

    def _call_llm_api(self, description: str, system_prompt: str) -> str:
        """Mock API call that returns configured response."""
        self.last_description = description
        self.last_system_prompt = system_prompt

        if self.response_text is None:
            # Return valid default response
            return json.dumps(
                {
                    "specs": [
                        {
                            "purpose": "Test Purpose",
                            "vision": "Test Vision",
                            "must": ["requirement1", "requirement2"],
                            "dont": ["avoid1"],
                            "nice": ["feature1"],
                        }
                    ]
                }
            )
        return self.response_text


def test_llm_configuration_error_missing_api_key():
    """Test that missing API key raises LLMConfigurationError."""
    with pytest.raises(LLMConfigurationError) as exc_info:
        MockLLMClient(api_key="", model="gpt-5.1")

    assert "api key is required" in str(exc_info.value).lower()


def test_llm_configuration_error_missing_model():
    """Test that missing model raises LLMConfigurationError."""
    with pytest.raises(LLMConfigurationError) as exc_info:
        MockLLMClient(api_key="test-key", model="")

    assert "model" in str(exc_info.value).lower()


def test_llm_configuration_error_invalid_timeout():
    """Test that invalid timeout raises LLMConfigurationError."""
    with pytest.raises(LLMConfigurationError) as exc_info:
        MockLLMClient(api_key="test-key", model="gpt-5.1", timeout=0)

    assert "timeout" in str(exc_info.value).lower()


def test_llm_client_initialization_success():
    """Test successful LLM client initialization."""
    client = MockLLMClient(
        api_key="test-key", model="gpt-5.1", base_url="https://api.example.com", timeout=30
    )

    assert client.api_key == "test-key"
    assert client.model == "gpt-5.1"
    assert client.base_url == "https://api.example.com"
    assert client.timeout == 30


def test_llm_client_initialization_defaults():
    """Test LLM client initialization with defaults."""
    client = MockLLMClient(api_key="test-key", model="gpt-5.1")

    assert client.api_key == "test-key"
    assert client.model == "gpt-5.1"
    assert client.base_url is None
    assert client.timeout == 60


def test_generate_specs_with_valid_response():
    """Test generate_specs with valid LLM response."""
    client = MockLLMClient(api_key="test-key", model="gpt-5.1")

    result = client.generate_specs("Build a REST API")

    assert "specs" in result
    assert isinstance(result["specs"], list)
    assert len(result["specs"]) == 1
    assert result["specs"][0]["purpose"] == "Test Purpose"
    assert result["specs"][0]["vision"] == "Test Vision"
    assert isinstance(result["specs"][0]["must"], list)
    assert isinstance(result["specs"][0]["dont"], list)
    assert isinstance(result["specs"][0]["nice"], list)


def test_generate_specs_uses_default_prompt():
    """Test that generate_specs uses default prompt when none provided."""
    client = MockLLMClient(api_key="test-key", model="gpt-5.1")

    client.generate_specs("Build a REST API")

    assert client.last_system_prompt == DEFAULT_SYSTEM_PROMPT


def test_generate_specs_uses_custom_prompt():
    """Test that generate_specs uses custom prompt when provided."""
    client = MockLLMClient(api_key="test-key", model="gpt-5.1")
    custom_prompt = "Custom system prompt"

    client.generate_specs("Build a REST API", system_prompt=custom_prompt)

    assert client.last_system_prompt == custom_prompt


def test_generate_specs_empty_prompt_falls_back_to_default():
    """Test that empty prompt override falls back to default."""
    client = MockLLMClient(api_key="test-key", model="gpt-5.1")

    client.generate_specs("Build a REST API", system_prompt="   ")

    assert client.last_system_prompt == DEFAULT_SYSTEM_PROMPT


def test_generate_specs_with_invalid_json():
    """Test that invalid JSON response raises LLMResponseError."""
    client = MockLLMClient(api_key="test-key", model="gpt-5.1", response_text="not valid json")

    with pytest.raises(LLMResponseError) as exc_info:
        client.generate_specs("Build a REST API")

    assert "json" in str(exc_info.value).lower()


def test_generate_specs_with_missing_specs_field():
    """Test that response without 'specs' field raises LLMResponseError."""
    client = MockLLMClient(
        api_key="test-key", model="gpt-5.1", response_text=json.dumps({"wrong_field": []})
    )

    with pytest.raises(LLMResponseError) as exc_info:
        client.generate_specs("Build a REST API")

    assert "specs" in str(exc_info.value).lower()


def test_generate_specs_with_markdown_wrapped_json():
    """Test that markdown-wrapped JSON is properly extracted."""
    response_with_markdown = """```json
{
  "specs": [
    {
      "purpose": "Test",
      "vision": "Vision",
      "must": [],
      "dont": [],
      "nice": []
    }
  ]
}
```"""

    client = MockLLMClient(
        api_key="test-key", model="gpt-5.1", response_text=response_with_markdown
    )

    result = client.generate_specs("Build a REST API")

    assert "specs" in result
    assert len(result["specs"]) == 1


def test_generate_specs_with_missing_spec_field():
    """Test that spec missing required field raises clear error."""
    # Missing 'vision' field
    invalid_spec = {"specs": [{"purpose": "Test", "must": [], "dont": [], "nice": []}]}

    client = MockLLMClient(
        api_key="test-key", model="gpt-5.1", response_text=json.dumps(invalid_spec)
    )

    with pytest.raises(LLMResponseError) as exc_info:
        client.generate_specs("Build a REST API")

    assert "vision" in str(exc_info.value).lower()
    assert "missing" in str(exc_info.value).lower()


def test_generate_specs_with_non_array_field():
    """Test that spec with non-array must/dont/nice raises clear error."""
    invalid_spec = {
        "specs": [
            {"purpose": "Test", "vision": "Vision", "must": "not an array", "dont": [], "nice": []}
        ]
    }

    client = MockLLMClient(
        api_key="test-key", model="gpt-5.1", response_text=json.dumps(invalid_spec)
    )

    with pytest.raises(LLMResponseError) as exc_info:
        client.generate_specs("Build a REST API")

    assert "must" in str(exc_info.value).lower()
    assert "array" in str(exc_info.value).lower()


def test_generate_specs_with_empty_specs_array():
    """Test that empty specs array is allowed by the parser."""
    client = MockLLMClient(
        api_key="test-key", model="gpt-5.1", response_text=json.dumps({"specs": []})
    )

    # The _parse_response method should successfully handle an empty specs list.
    # The subsequent PlanResponse model validation will raise the error, which is
    # the expected behavior. This test now correctly expects that validation failure.
    with pytest.raises(LLMResponseError) as exc_info:
        client.generate_specs("Build a REST API")

    # The error should be a validation error from PlanResponse, not a parsing error.
    assert "validation" in str(exc_info.value).lower()
    assert "at least 1 item" in str(exc_info.value)


def test_get_default_system_prompt():
    """Test that get_default_system_prompt returns the default prompt."""
    prompt = get_default_system_prompt()

    assert prompt == DEFAULT_SYSTEM_PROMPT
    assert "specs" in prompt.lower()
    assert "json" in prompt.lower()
    assert "purpose" in prompt
    assert "vision" in prompt
    assert "must" in prompt
    assert "dont" in prompt
    assert "nice" in prompt


def test_default_system_prompt_content():
    """Test that default system prompt has expected content."""
    assert "json" in DEFAULT_SYSTEM_PROMPT.lower()
    assert '"specs"' in DEFAULT_SYSTEM_PROMPT
    assert "purpose" in DEFAULT_SYSTEM_PROMPT
    assert "vision" in DEFAULT_SYSTEM_PROMPT
    assert "must" in DEFAULT_SYSTEM_PROMPT
    assert "dont" in DEFAULT_SYSTEM_PROMPT
    assert "nice" in DEFAULT_SYSTEM_PROMPT
    # Verify it mentions lists (list is the term used in the prompt, not array)
    assert "list" in DEFAULT_SYSTEM_PROMPT.lower()


def test_base_llm_client_is_abstract():
    """Test that BaseLLMClient cannot be instantiated directly."""
    with pytest.raises(TypeError):
        BaseLLMClient(api_key="test-key", model="gpt-5.1")


def test_llm_error_hierarchy():
    """Test that LLM exception hierarchy is properly defined."""
    # All specific errors should inherit from LLMError
    assert issubclass(LLMConfigurationError, LLMError)
    assert issubclass(LLMRequestError, LLMError)
    assert issubclass(LLMResponseError, LLMError)

    # All should inherit from Exception
    assert issubclass(LLMError, Exception)


class TestClientFactory:
    """Tests for create_llm_client factory function."""

    @patch("app.services.llm_openai.OpenAI")
    def test_create_openai_client(self, mock_openai_class):
        """Test creating an OpenAI client via factory."""
        from app.services.llm_client import create_llm_client
        from app.services.llm_openai import OpenAIClient

        # Should successfully create client
        client = create_llm_client(
            provider="openai", model_id="gpt-5.1", api_key="test-key", timeout=30
        )
        assert isinstance(client, OpenAIClient)
        assert client.model == "gpt-5.1"

    def test_create_client_unknown_provider(self):
        """Test that unknown provider raises error."""
        from app.services.llm_client import create_llm_client

        with pytest.raises(LLMConfigurationError) as exc_info:
            create_llm_client(
                provider="unknown-provider", model_id="some-model", api_key="test-key"
            )

        assert "unknown" in str(exc_info.value).lower()
        assert "provider" in str(exc_info.value).lower()

    @patch("app.services.llm_openai.OpenAI")
    def test_create_client_case_insensitive(self, mock_openai_class):
        """Test that provider names are case-insensitive."""
        from app.services.llm_client import create_llm_client

        # Both should create clients successfully
        client1 = create_llm_client(provider="OpenAI", model_id="gpt-5.1", api_key="test-key")
        assert client1.model == "gpt-5.1"

        client2 = create_llm_client(provider="OPENAI", model_id="gpt-5.1", api_key="test-key")
        assert client2.model == "gpt-5.1"


class TestClientRouter:
    """Tests for get_llm_client_for_model router function."""

    def test_router_nonexistent_model(self, monkeypatch):
        """Test that requesting non-existent model raises error."""
        from app.services import model_registry
        from app.services.llm_client import get_llm_client_for_model

        # Reset registry cache
        model_registry._model_registry = None

        # Set empty registry
        monkeypatch.setenv("MODELS_REGISTRY", "{}")

        with pytest.raises(LLMConfigurationError) as exc_info:
            get_llm_client_for_model("nonexistent-model")

        assert "not found" in str(exc_info.value).lower()
        assert "nonexistent-model" in str(exc_info.value)


class TestProviderAdapters:
    """Tests for provider-specific adapter implementations."""

    @patch("app.services.llm_openai.OpenAI")
    def test_openai_adapter_constructs_request_correctly(self, mock_openai_class):
        """Test that OpenAI adapter constructs request with correct parameters."""
        from app.services.llm_openai import OpenAIClient

        # Mock OpenAI Responses API response structure
        mock_client_instance = mock_openai_class.return_value
        mock_response = type(
            "obj",
            (object,),
            {
                "output": [
                    type(
                        "obj",
                        (object,),
                        {
                            "content": json.dumps(
                                {
                                    "specs": [
                                        {
                                            "purpose": "Test",
                                            "vision": "Vision",
                                            "must": [],
                                            "dont": [],
                                            "nice": [],
                                        }
                                    ]
                                }
                            )
                        },
                    )()
                ],
                "usage": type(
                    "obj",
                    (object,),
                    {"input_tokens": 100, "output_tokens": 150, "total_tokens": 250},
                )(),
            },
        )()
        mock_client_instance.responses.create.return_value = mock_response

        client = OpenAIClient(api_key="test-key", model="gpt-4")
        result = client.generate_specs("Build API", system_prompt="Custom prompt")

        # Verify API was called with correct parameters
        assert mock_client_instance.responses.create.called
        call_kwargs = mock_client_instance.responses.create.call_args[1]
        assert call_kwargs["model"] == "gpt-4"
        assert call_kwargs["input"] == "Build API"
        assert call_kwargs["instructions"] == "Custom prompt"

    @patch("app.services.llm_openai.OpenAI")
    def test_openai_adapter_handles_timeout_with_retry(self, mock_openai_class):
        """Test that OpenAI adapter retries on timeout."""
        from openai import APITimeoutError

        from app.services.llm_openai import OpenAIClient

        mock_client_instance = mock_openai_class.return_value
        # First two calls timeout, third succeeds
        mock_response = type(
            "obj",
            (object,),
            {
                "output": [
                    type(
                        "obj",
                        (object,),
                        {
                            "content": json.dumps(
                                {
                                    "specs": [
                                        {
                                            "purpose": "Test",
                                            "vision": "Vision",
                                            "must": [],
                                            "dont": [],
                                            "nice": [],
                                        }
                                    ]
                                }
                            )
                        },
                    )()
                ],
                "usage": type(
                    "obj",
                    (object,),
                    {"input_tokens": 100, "output_tokens": 150, "total_tokens": 250},
                )(),
            },
        )()
        mock_client_instance.responses.create.side_effect = [
            APITimeoutError("Timeout"),
            APITimeoutError("Timeout"),
            mock_response,
        ]

        client = OpenAIClient(
            api_key="test-key",
            model="gpt-4",
            max_retries=3,
            initial_backoff=0.01,  # Very small for testing
        )

        # Should succeed after retries
        with patch("time.sleep"):  # Mock sleep to speed up test
            result = client.generate_specs("Build API")

        assert result is not None
        assert "specs" in result
        # Verify it was called 3 times (2 failures + 1 success)
        assert mock_client_instance.responses.create.call_count == 3

    @patch("app.services.llm_openai.OpenAI")
    def test_openai_adapter_logs_retry_attempts(self, mock_openai_class):
        """Test that OpenAI adapter logs retry attempts without exposing secrets."""
        from openai import APITimeoutError

        from app.services.llm_openai import OpenAIClient

        mock_client_instance = mock_openai_class.return_value
        mock_response = type(
            "obj",
            (object,),
            {
                "output": [
                    type(
                        "obj",
                        (object,),
                        {
                            "content": json.dumps(
                                {
                                    "specs": [
                                        {
                                            "purpose": "Test",
                                            "vision": "Vision",
                                            "must": [],
                                            "dont": [],
                                            "nice": [],
                                        }
                                    ]
                                }
                            )
                        },
                    )()
                ],
                "usage": type(
                    "obj",
                    (object,),
                    {"input_tokens": 100, "output_tokens": 150, "total_tokens": 250},
                )(),
            },
        )()
        mock_client_instance.responses.create.side_effect = [
            APITimeoutError("Timeout"),
            mock_response,
        ]

        client = OpenAIClient(
            api_key="test-key", model="gpt-4", max_retries=2, initial_backoff=0.01
        )

        with patch("time.sleep"):
            with patch("app.services.llm_openai.logger") as mock_logger:
                result = client.generate_specs("Build API")

                # Verify retry was logged
                assert mock_logger.info.called
                # Verify API key is not in any log call
                for call in mock_logger.info.call_args_list:
                    args_str = str(call)
                    assert "test-key" not in args_str

    @patch("app.services.llm_openai.OpenAI")
    def test_openai_adapter_handles_malformed_response(self, mock_openai_class):
        """Test that OpenAI adapter handles malformed provider payloads."""
        from app.services.llm_openai import OpenAIClient

        mock_client_instance = mock_openai_class.return_value
        # Return response with invalid JSON
        mock_response = type(
            "obj",
            (object,),
            {
                "output": [type("obj", (object,), {"content": "not valid json at all"})()],
                "usage": type(
                    "obj",
                    (object,),
                    {"input_tokens": 100, "output_tokens": 150, "total_tokens": 250},
                )(),
            },
        )()
        mock_client_instance.responses.create.return_value = mock_response

        client = OpenAIClient(api_key="test-key", model="gpt-4")

        with pytest.raises(LLMResponseError) as exc_info:
            client.generate_specs("Build API")

        # Should raise error about JSON parsing
        assert "json" in str(exc_info.value).lower() or "invalid" in str(exc_info.value).lower()

    @patch("app.services.llm_openai.OpenAI")
    def test_openai_adapter_timeout_exhausts_retries(self, mock_openai_class):
        """Test that OpenAI adapter raises error after exhausting retries."""
        from openai import APITimeoutError

        from app.services.llm_openai import OpenAIClient

        mock_client_instance = mock_openai_class.return_value
        # All retries timeout
        mock_client_instance.responses.create.side_effect = APITimeoutError("Timeout")

        client = OpenAIClient(
            api_key="test-key", model="gpt-4", max_retries=2, initial_backoff=0.01
        )

        with patch("time.sleep"):
            with pytest.raises(LLMRequestError) as exc_info:
                client.generate_specs("Build API")

        # The error message includes "timed out" which contains "timeout"
        error_msg = str(exc_info.value).lower()
        assert "timed out" in error_msg or "timeout" in error_msg
        # Should have tried 3 times (initial + 2 retries)
        assert mock_client_instance.responses.create.call_count == 3
