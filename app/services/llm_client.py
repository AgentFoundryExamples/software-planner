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
"""Abstract LLM client interface for generating software specifications.

This module provides a provider-agnostic abstraction for LLM-based spec generation.
Implementers should subclass BaseLLMClient and provide concrete implementations
for specific LLM providers (OpenAI, Anthropic, Google, etc.).

The abstraction is designed to:
- Keep the surface provider-agnostic (no SDK imports here)
- Support structured logging without storing secrets
- Define clear error contracts for implementers
- Enforce JSON-only output with typed responses
"""

import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Any, Optional

from app.models.response import PlanResponse


# Default system prompt that enforces the expected JSON output format
DEFAULT_SYSTEM_PROMPT = """You are a software planning assistant. Generate a structured software plan based on the user's description.

Your response MUST be valid JSON only, with no additional text, markdown formatting, or code blocks.

The JSON structure must be:
{
  "specs": [
    {
      "purpose": "string - High-level purpose of this specification",
      "vision": "string - Vision or goal statement",
      "must": ["string array - Must-have requirements"],
      "dont": ["string array - Things to avoid"],
      "nice": ["string array - Nice-to-have features"]
    }
  ]
}

Requirements:
- The top-level object must have a "specs" key containing an array
- Each spec object must include: purpose, vision, must, dont, nice
- must, dont, and nice must be arrays of strings (can be empty arrays)
- Return ONLY the JSON object, no other text

Ensure the response is valid JSON that can be parsed directly."""


logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Base exception for LLM client errors."""
    pass


class LLMConfigurationError(LLMError):
    """Raised when LLM client is misconfigured (missing API key, invalid model, etc.)."""
    pass


class LLMRequestError(LLMError):
    """Raised when an LLM API request fails (timeout, rate limit, API error, etc.)."""
    pass


class LLMResponseError(LLMError):
    """Raised when LLM response cannot be parsed or validated."""
    pass


class BaseLLMClient(ABC):
    """Abstract base class for LLM clients.
    
    Implementers must provide concrete implementations for specific LLM providers.
    This abstraction enforces a consistent interface and error handling contract.
    
    Attributes:
        api_key: API key for the LLM provider (should not be logged).
        model: Model identifier (e.g., 'gpt-5.1', 'claude-sonnet-4.5').
        base_url: Optional base URL for custom endpoints.
        timeout: Request timeout in seconds.
    
    Error Contracts:
        Implementers must raise:
        - LLMConfigurationError: For configuration issues (missing/invalid credentials)
        - LLMRequestError: For API request failures (network, rate limits, etc.)
        - LLMResponseError: For invalid or unparseable responses
    
    Logging Requirements:
        - Log request metadata (model, description length, timestamp) at INFO level
        - Log errors with error type and sanitized message at ERROR level
        - NEVER log API keys or full response content containing sensitive data
        - Log response metadata (token count, latency) at DEBUG level if available
    """
    
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: Optional[str] = None,
        timeout: int = 60
    ):
        """Initialize the LLM client.
        
        Args:
            api_key: API key for the LLM provider.
            model: Model identifier to use.
            base_url: Optional base URL for custom endpoints.
            timeout: Request timeout in seconds.
            
        Raises:
            LLMConfigurationError: If configuration is invalid.
        """
        if not api_key:
            raise LLMConfigurationError("LLM API key is required")
        if not model:
            raise LLMConfigurationError("LLM model identifier is required")
        if timeout < 1:
            raise LLMConfigurationError("LLM timeout must be at least 1 second")
        
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.timeout = timeout
        
        # Log initialization without exposing secrets
        logger.info(
            "Initialized LLM client",
            extra={
                "model": model,
                "base_url": base_url if base_url else "default",
                "timeout": timeout,
                "has_api_key": bool(api_key)
            }
        )
    
    @abstractmethod
    def _call_llm_api(
        self,
        description: str,
        system_prompt: str
    ) -> str:
        """Call the LLM provider's API and return the raw response text.
        
        This is the provider-specific implementation that must be overridden.
        
        Args:
            description: User's project description.
            system_prompt: System prompt to guide LLM behavior.
            
        Returns:
            Raw response text from the LLM.
            
        Raises:
            LLMRequestError: If the API request fails.
        """
        pass
    
    def _parse_response(self, raw_response: str) -> dict[str, Any]:
        """Parse and validate the raw LLM response.
        
        Extracts JSON from the response and validates it has the expected structure.
        
        Args:
            raw_response: Raw text response from the LLM.
            
        Returns:
            Parsed JSON as a dictionary.
            
        Raises:
            LLMResponseError: If response cannot be parsed or is invalid.
        """
        # Try to extract JSON from response (in case LLM wrapped it in markdown)
        response_text = raw_response.strip()
        
        # Remove markdown code blocks if present using regex
        # Matches ```json or ``` at start and ``` at end
        # The final newline before closing backticks is optional
        markdown_pattern = r'^```(?:json)?\s*\n(.*?)\n?```$'
        match = re.search(markdown_pattern, response_text, re.DOTALL)
        if match:
            response_text = match.group(1).strip()
        
        try:
            data = json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.error(
                "Failed to parse LLM response as JSON",
                extra={"error": str(e), "response_length": len(response_text)}
            )
            raise LLMResponseError(f"Invalid JSON response from LLM: {e}")
        
        # Validate structure
        if not isinstance(data, dict):
            raise LLMResponseError("LLM response must be a JSON object")
        
        if "specs" not in data:
            raise LLMResponseError("LLM response missing required 'specs' field")
        
        if not isinstance(data["specs"], list):
            raise LLMResponseError("'specs' field must be an array")
        
        # Validate individual spec objects for clearer error messages
        for idx, spec in enumerate(data["specs"]):
            if not isinstance(spec, dict):
                raise LLMResponseError(f"Spec at index {idx} must be an object")
            
            required_fields = ["purpose", "vision", "must", "dont", "nice"]
            for field in required_fields:
                if field not in spec:
                    raise LLMResponseError(
                        f"Spec at index {idx} missing required field '{field}'"
                    )
            
            # Validate array fields
            for array_field in ["must", "dont", "nice"]:
                if not isinstance(spec[array_field], list):
                    raise LLMResponseError(
                        f"Spec at index {idx}: field '{array_field}' must be an array"
                    )
        
        return data
    
    def generate_specs(
        self,
        description: str,
        system_prompt: Optional[str] = None
    ) -> dict[str, Any]:
        """Generate software specifications from a project description.
        
        This is the main public interface for spec generation. It handles:
        - System prompt defaulting
        - LLM API invocation
        - Response parsing and validation
        - Structured logging
        - Error handling
        
        Args:
            description: Project description provided by the user.
            system_prompt: Optional system prompt override. If None, uses DEFAULT_SYSTEM_PROMPT.
            
        Returns:
            Dictionary with 'specs' key containing list of specification objects.
            Each spec has: purpose, vision, must (list), dont (list), nice (list).
            
        Raises:
            LLMConfigurationError: If client is misconfigured.
            LLMRequestError: If API request fails.
            LLMResponseError: If response is invalid or cannot be parsed.
            
        Example:
            >>> client = ConcreteClient(api_key="...", model="gpt-5.1")
            >>> result = client.generate_specs("Build a REST API for user management")
            >>> print(result["specs"][0]["purpose"])
        """
        # Use default prompt if none provided
        prompt = system_prompt if system_prompt else DEFAULT_SYSTEM_PROMPT
        
        # Validate empty prompt override
        if system_prompt is not None and not system_prompt.strip():
            logger.warning("Empty system_prompt override provided, falling back to default")
            prompt = DEFAULT_SYSTEM_PROMPT
        
        # Log request metadata (not the description itself, which may be sensitive)
        logger.info(
            "Generating specs via LLM",
            extra={
                "model": self.model,
                "description_length": len(description),
                "using_default_prompt": system_prompt is None
            }
        )
        
        try:
            # Call provider-specific implementation
            raw_response = self._call_llm_api(description, prompt)
            
            # Mark that we're now in response processing phase
            processing_response = True
            
            # Parse and validate response
            result = self._parse_response(raw_response)
            
            # Validate result can be converted to PlanResponse
            try:
                PlanResponse.model_validate(result)
            except Exception as e:
                logger.error(
                    "LLM response does not match PlanResponse schema",
                    extra={"error": str(e)}
                )
                raise LLMResponseError(f"Response validation failed: {e}")
            
            logger.info(
                "Successfully generated specs",
                extra={"spec_count": len(result["specs"])}
            )
            
            return result
            
        except LLMError:
            # Re-raise our own exceptions
            raise
        except Exception as e:
            # Wrap unexpected errors with better classification
            error_type = type(e).__name__
            logger.error(
                "Unexpected error during spec generation",
                extra={"error_type": error_type, "error": str(e)}
            )
            # Check if we were processing the response or making the request
            if 'processing_response' in locals() and processing_response:
                raise LLMResponseError(f"Unexpected error processing response: {e}")
            else:
                raise LLMRequestError(f"Unexpected error during request: {e}")


def get_default_system_prompt() -> str:
    """Get the default system prompt for spec generation.
    
    This function provides access to the canonical default prompt that
    enforces JSON-only output with the required structure.
    
    Returns:
        The default system prompt string.
    """
    return DEFAULT_SYSTEM_PROMPT
