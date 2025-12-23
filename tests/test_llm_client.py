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
import pytest
from app.services.llm_client import (
    BaseLLMClient,
    LLMError,
    LLMConfigurationError,
    LLMRequestError,
    LLMResponseError,
    get_default_system_prompt,
    DEFAULT_SYSTEM_PROMPT
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
            return json.dumps({
                "specs": [
                    {
                        "purpose": "Test Purpose",
                        "vision": "Test Vision",
                        "must": ["requirement1", "requirement2"],
                        "dont": ["avoid1"],
                        "nice": ["feature1"]
                    }
                ]
            })
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
        api_key="test-key",
        model="gpt-5.1",
        base_url="https://api.example.com",
        timeout=30
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
    client = MockLLMClient(
        api_key="test-key",
        model="gpt-5.1",
        response_text="not valid json"
    )
    
    with pytest.raises(LLMResponseError) as exc_info:
        client.generate_specs("Build a REST API")
    
    assert "json" in str(exc_info.value).lower()


def test_generate_specs_with_missing_specs_field():
    """Test that response without 'specs' field raises LLMResponseError."""
    client = MockLLMClient(
        api_key="test-key",
        model="gpt-5.1",
        response_text=json.dumps({"wrong_field": []})
    )
    
    with pytest.raises(LLMResponseError) as exc_info:
        client.generate_specs("Build a REST API")
    
    assert "specs" in str(exc_info.value).lower()


def test_generate_specs_with_empty_specs_array():
    """Test that empty specs array raises LLMResponseError."""
    client = MockLLMClient(
        api_key="test-key",
        model="gpt-5.1",
        response_text=json.dumps({"specs": []})
    )
    
    with pytest.raises(LLMResponseError) as exc_info:
        client.generate_specs("Build a REST API")
    
    assert "at least one" in str(exc_info.value).lower()


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
        api_key="test-key",
        model="gpt-5.1",
        response_text=response_with_markdown
    )
    
    result = client.generate_specs("Build a REST API")
    
    assert "specs" in result
    assert len(result["specs"]) == 1


def test_generate_specs_with_invalid_schema():
    """Test that response not matching PlanResponse schema raises error."""
    # Missing required 'vision' field
    invalid_spec = {
        "specs": [
            {
                "purpose": "Test",
                "must": [],
                "dont": [],
                "nice": []
            }
        ]
    }
    
    client = MockLLMClient(
        api_key="test-key",
        model="gpt-5.1",
        response_text=json.dumps(invalid_spec)
    )
    
    with pytest.raises(LLMResponseError) as exc_info:
        client.generate_specs("Build a REST API")
    
    assert "validation" in str(exc_info.value).lower()


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
    assert "JSON" in DEFAULT_SYSTEM_PROMPT
    assert '"specs"' in DEFAULT_SYSTEM_PROMPT
    assert "purpose" in DEFAULT_SYSTEM_PROMPT
    assert "vision" in DEFAULT_SYSTEM_PROMPT
    assert "must" in DEFAULT_SYSTEM_PROMPT
    assert "dont" in DEFAULT_SYSTEM_PROMPT
    assert "nice" in DEFAULT_SYSTEM_PROMPT
    # Verify it mentions arrays
    assert "array" in DEFAULT_SYSTEM_PROMPT.lower()


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
