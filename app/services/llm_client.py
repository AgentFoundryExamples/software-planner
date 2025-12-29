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
import threading
from abc import ABC, abstractmethod
from typing import Any, Optional

from app.models.response import PlanResponse

# Default system prompt that enforces the expected JSON output format
DEFAULT_SYSTEM_PROMPT = """You are tasked with specifying first steps for a software idea. The goal is not to complete a project in 1 iteration but to break it up into a list of specifications for building the software iteratively. You will receive the users software idea and should strictly output a list of specifications in the following json format:
{
 "specs": [
{
"purpose": "what the iteration must accomplish",
"vision": "the vision for what the functionality is",
"must": ["list of requirements that must be accomplished during this iteration this should be specific and detailed about technical details and externally observable behaviors the more detailed the better the iteration will come out"],
"dont": ["list of things the iteration should not do"],
"nice": ["things that would be nice but are not required on this iteration"],
"open_questions": ["optional list field asking clarifying questions for ambiguous input instead of making guesses"],
"assumptions": ["optional list field with any assumptions that weren't clearly defined in the input."]
},
{*next spec*}
]
}
These specifications should be reasonable steps in software development, building very iteratively. Prefer 4-8 specs unless the input requires more to clearly break it down. Assume the project is being created from scratch."""


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

    def __init__(self, api_key: str, model: str, base_url: Optional[str] = None, timeout: int = 60):
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
                "has_api_key": bool(api_key),
            },
        )

    @abstractmethod
    def _call_llm_api(self, description: str, system_prompt: str) -> str:
        """Call the LLM provider's API and return the raw response text.

        This is the provider-specific implementation that must be overridden.

        **JSON Mode Enforcement:**
        Implementations MUST configure their provider's JSON mode enforcement
        to guarantee valid JSON output regardless of system_prompt content.
        This ensures malformed responses are rejected at the provider level
        before reaching the parser.

        For example:
        - OpenAI: Use response_format with json_schema and strict=True
        - Anthropic: Use response_format={"type": "json_object"}
        - Google: Use generationConfig with response_mime_type="application/json"

        Args:
            description: User's project description.
            system_prompt: System prompt to guide LLM behavior.

        Returns:
            Raw response text from the LLM (must be valid JSON).

        Raises:
            LLMRequestError: If the API request fails.
            LLMResponseError: If provider rejects output due to schema violation.
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
        markdown_pattern = r"^```(?:json)?\s*\n(.*?)\n?```$"
        match = re.search(markdown_pattern, response_text, re.DOTALL)
        if match:
            response_text = match.group(1).strip()

        try:
            data = json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.error(
                "Failed to parse LLM response as JSON",
                extra={"error": str(e), "response_length": len(response_text)},
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
                    raise LLMResponseError(f"Spec at index {idx} missing required field '{field}'")

            # Validate array fields
            for array_field in ["must", "dont", "nice"]:
                if not isinstance(spec[array_field], list):
                    raise LLMResponseError(
                        f"Spec at index {idx}: field '{array_field}' must be an array"
                    )

        return data

    def generate_specs(
        self, description: str, system_prompt: Optional[str] = None
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
        # Include system prompt hash for debugging without exposing content
        import hashlib

        prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]

        logger.info(
            "Generating specs via LLM",
            extra={
                "model": self.model,
                "description_length": len(description),
                "using_default_prompt": system_prompt is None,
                "system_prompt_hash": prompt_hash,
                "system_prompt_length": len(prompt),
            },
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
                    "LLM response does not match PlanResponse schema", extra={"error": str(e)}
                )
                raise LLMResponseError(f"Response validation failed: {e}")

            logger.info("Successfully generated specs", extra={"spec_count": len(result["specs"])})

            return result

        except LLMError:
            # Re-raise our own exceptions
            raise
        except Exception as e:
            # Wrap unexpected errors with better classification
            error_type = type(e).__name__
            logger.error(
                "Unexpected error during spec generation",
                extra={"error_type": error_type, "error": str(e)},
            )
            # Check if we were processing the response or making the request
            if "processing_response" in locals() and processing_response:
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


# Global client cache for reusing provider instances
_client_cache: dict[str, BaseLLMClient] = {}
_client_cache_lock = threading.Lock()


def create_llm_client(
    provider: str,
    model_id: str,
    api_key: str,
    base_url: Optional[str] = None,
    timeout: int = 60,
    max_retries: int = 3,
) -> BaseLLMClient:
    """Create an LLM client instance for a specific provider.

    This factory function instantiates the appropriate concrete client
    based on the provider identifier. It handles provider-specific
    initialization and validates configuration.

    Args:
        provider: Provider identifier ('openai', 'anthropic', 'google').
        model_id: Model identifier for the provider.
        api_key: API key for authentication.
        base_url: Optional custom base URL for API endpoint.
        timeout: Request timeout in seconds.
        max_retries: Maximum number of retry attempts.

    Returns:
        Initialized LLM client instance.

    Raises:
        LLMConfigurationError: If provider is unknown or initialization fails.

    Example:
        >>> client = create_llm_client(
        ...     provider='openai',
        ...     model_id='gpt-5.1',
        ...     api_key='sk-...',
        ...     timeout=60
        ... )
    """
    provider_lower = provider.lower()

    # Import providers lazily to avoid circular dependencies
    if provider_lower == "openai":
        from app.services.llm_openai import OpenAIClient

        return OpenAIClient(
            api_key=api_key,
            model=model_id,
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
        )
    elif provider_lower == "anthropic":
        from app.services.llm_claude import ClaudeClient

        return ClaudeClient(
            api_key=api_key,
            model=model_id,
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
        )
    elif provider_lower == "google":
        from app.services.llm_gemini import GeminiClient

        return GeminiClient(
            api_key=api_key,
            model=model_id,
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
        )
    else:
        raise LLMConfigurationError(
            f"Unknown LLM provider: {provider}. " f"Supported providers: openai, anthropic, google"
        )


def get_llm_client_for_model(logical_model_id: str, cache_clients: bool = True) -> BaseLLMClient:
    """Get or create an LLM client for a logical model ID.

    This function is the main routing entry point that:
    1. Fetches model configuration from the registry
    2. Validates the model is enabled
    3. Creates or retrieves a cached client instance
    4. Returns a ready-to-use client with proper configuration

    The function uses a thread-safe cache to reuse client instances for
    the same logical model. This avoids repeated SDK initialization overhead
    and preserves connection pools.

    Args:
        logical_model_id: Logical name of the model from the registry.
        cache_clients: Whether to cache and reuse client instances (default: True).
            Set to False in tests or when dynamic reconfiguration is needed.

    Returns:
        Initialized LLM client instance ready to generate specs.

    Raises:
        LLMConfigurationError: If model is not found, disabled, or misconfigured.

    Example:
        >>> client = get_llm_client_for_model('my-gpt-model')
        >>> result = client.generate_specs("Build a REST API")

    Note:
        This function imports model_registry lazily to avoid circular dependencies
        between core config and service layers.
    """
    # Import here to avoid circular dependency
    import os

    from app.services.model_registry import get_model_registry

    # Get model configuration from registry
    registry = get_model_registry()
    model_config = registry.get_model_config(logical_model_id)

    if model_config is None:
        raise LLMConfigurationError(
            f"Model '{logical_model_id}' not found in registry. "
            f"Check your MODELS_REGISTRY configuration."
        )

    # Enforce enabled flag
    if not model_config.enabled:
        raise LLMConfigurationError(
            f"Model '{logical_model_id}' is disabled. "
            f"Enable it in MODELS_REGISTRY or choose a different model."
        )

    # Check cache if enabled - acquire lock for thread-safe cache access
    if cache_clients:
        # Thread-safe cache lookup with proper locking
        with _client_cache_lock:
            if logical_model_id in _client_cache:
                logger.debug(
                    f"Using cached client for model '{logical_model_id}'",
                    extra={"logical_model": logical_model_id},
                )
                return _client_cache[logical_model_id]
            # If not in cache, continue to create below
            # Lock will be reacquired when caching the new client

    # Get API key from environment variable
    api_key = os.environ.get(model_config.api_key_env, "").strip()
    if not api_key:
        raise LLMConfigurationError(
            f"API key not found for model '{logical_model_id}'. "
            f"Set environment variable {model_config.api_key_env}."
        )

    # Create client instance
    try:
        client = create_llm_client(
            provider=model_config.provider,
            model_id=model_config.model_id,
            api_key=api_key,
            base_url=model_config.base_url,
            timeout=model_config.timeout,
            max_retries=model_config.max_retries,
        )

        # Cache the client if enabled
        if cache_clients:
            with _client_cache_lock:
                _client_cache[logical_model_id] = client

        logger.info(
            f"Created LLM client for model '{logical_model_id}'",
            extra={
                "logical_model": logical_model_id,
                "provider": model_config.provider,
                "model_id": model_config.model_id,
                "timeout": model_config.timeout,
                "max_retries": model_config.max_retries,
            },
        )

        return client

    except LLMConfigurationError:
        # Re-raise configuration errors as-is with context
        raise
    except Exception as e:
        raise LLMConfigurationError(f"Failed to create client for model '{logical_model_id}': {e}")
