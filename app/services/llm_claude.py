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
"""Anthropic Claude-based LLM client implementation.

This module provides a concrete implementation of BaseLLMClient using Anthropic's API.
It uses the official Anthropic Python SDK and implements retry logic for transient failures.

Key features:
- Uses Anthropic Messages API (recommended for Claude models)
- Configurable retry logic with exponential backoff for transient errors
- Structured logging without exposing secrets
- Proper error classification and handling
"""

import logging
import time
from typing import Optional

import anthropic
from anthropic import Anthropic

from app.services.llm_client import (
    BaseLLMClient,
    LLMConfigurationError,
    LLMRequestError,
    LLMResponseError,
)

logger = logging.getLogger(__name__)

# Retry configuration
MAX_RETRIES = 3
INITIAL_BACKOFF = 1.0  # seconds
MAX_BACKOFF = 10.0  # seconds
BACKOFF_MULTIPLIER = 2.0


class ClaudeClient(BaseLLMClient):
    """Anthropic Claude implementation of the LLM client.

    This client uses the Anthropic Messages API to generate specifications.
    It implements retry logic for transient failures and provides structured logging.

    **Important**: This client uses synchronous calls with blocking sleep for retry backoff.
    If using in async contexts (e.g., FastAPI async endpoints), consider running the
    client calls in a thread pool executor to avoid blocking the event loop:

        >>> import asyncio
        >>> from concurrent.futures import ThreadPoolExecutor
        >>> executor = ThreadPoolExecutor()
        >>> result = await asyncio.get_event_loop().run_in_executor(
        ...     executor, client.generate_specs, "Build a REST API"
        ... )

    Attributes:
        client: Anthropic SDK client instance.
        max_retries: Maximum number of retry attempts for transient errors.
        initial_backoff: Initial backoff delay in seconds.
        max_backoff: Maximum backoff delay in seconds.
        backoff_multiplier: Multiplier for exponential backoff.

    Example:
        >>> client = ClaudeClient(
        ...     api_key="sk-ant-...",
        ...     model="claude-sonnet-4.5",
        ...     timeout=60
        ... )
        >>> result = client.generate_specs("Build a REST API")
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: Optional[str] = None,
        timeout: int = 60,
        max_retries: int = MAX_RETRIES,
        initial_backoff: float = INITIAL_BACKOFF,
        max_backoff: float = MAX_BACKOFF,
        backoff_multiplier: float = BACKOFF_MULTIPLIER,
    ):
        """Initialize Claude client.

        Args:
            api_key: Anthropic API key.
            model: Model identifier (e.g., 'claude-sonnet-4.5', 'claude-opus-4').
            base_url: Optional base URL for custom endpoints.
            timeout: Request timeout in seconds.
            max_retries: Maximum number of retry attempts.
            initial_backoff: Initial backoff delay in seconds.
            max_backoff: Maximum backoff delay in seconds.
            backoff_multiplier: Multiplier for exponential backoff.

        Raises:
            LLMConfigurationError: If configuration is invalid.
        """
        # Initialize base class (validates api_key, model, timeout)
        super().__init__(api_key, model, base_url, timeout)

        # Validate retry configuration
        if max_retries < 0:
            raise LLMConfigurationError("max_retries must be non-negative")
        if initial_backoff <= 0:
            raise LLMConfigurationError("initial_backoff must be positive")
        if max_backoff < initial_backoff:
            raise LLMConfigurationError("max_backoff must be >= initial_backoff")
        if backoff_multiplier < 1.0:
            raise LLMConfigurationError("backoff_multiplier must be >= 1.0")

        self.max_retries = max_retries
        self.initial_backoff = initial_backoff
        self.max_backoff = max_backoff
        self.backoff_multiplier = backoff_multiplier

        # Initialize Anthropic client
        try:
            client_kwargs = {
                "api_key": api_key,
                "timeout": timeout,
            }
            if base_url:
                client_kwargs["base_url"] = base_url

            self.client = Anthropic(**client_kwargs)

            logger.info(
                "Claude client initialized",
                extra={
                    "model": model,
                    "has_base_url": bool(base_url),
                    "timeout": timeout,
                    "max_retries": max_retries,
                },
            )
        except Exception as e:
            logger.error(
                "Failed to initialize Claude client",
                extra={"error": str(e), "error_type": type(e).__name__},
            )
            raise LLMConfigurationError(f"Failed to initialize Claude client: {e}")

    def _is_retryable_error(self, error: Exception) -> bool:
        """Determine if an error is retryable.

        Retryable errors include:
        - Rate limit errors (429)
        - Server errors (500-599)
        - Timeout errors
        - Connection errors

        Non-retryable errors include:
        - Authentication errors (401)
        - Permission errors (403)
        - Not found errors (404)
        - Invalid request errors (400)

        Args:
            error: The exception to check.

        Returns:
            True if the error should be retried, False otherwise.
        """
        # Check for Anthropic-specific error types that are documented as retryable
        return isinstance(
            error,
            (
                anthropic.APITimeoutError,
                anthropic.RateLimitError,
                anthropic.APIConnectionError,
                anthropic.InternalServerError,
            ),
        )

    def _call_llm_api(self, description: str, system_prompt: str) -> str:
        """Call Anthropic API with retry logic.

        This method implements exponential backoff retry logic for transient failures.
        It uses Anthropic's Messages API with the configured model.

        Args:
            description: User's project description.
            system_prompt: System prompt to guide LLM behavior.

        Returns:
            Raw response text from the LLM.

        Raises:
            LLMConfigurationError: If API key is invalid or missing.
            LLMRequestError: If the API request fails after retries.
        """
        retry_count = 0
        backoff = self.initial_backoff
        last_error = None

        start_time = time.time()

        # Log LLM request start
        from app.utils.logging_helpers import log_llm_request

        log_llm_request(
            logger=logger,
            provider="anthropic",
            model=self.model,
            description_length=len(description),
        )

        while retry_count <= self.max_retries:
            try:
                # Log attempt (not on first try to avoid log spam)
                if retry_count > 0:
                    logger.info(
                        "Retrying Claude API call",
                        extra={
                            "retry_count": retry_count,
                            "max_retries": self.max_retries,
                            "backoff": backoff,
                        },
                    )

                # Make the API call using Messages API with JSON mode enforcement
                # response_format enforces strict JSON output
                # This is a beta feature in Anthropic SDK
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=4096,  # Reasonable limit for spec generation
                    system=system_prompt,
                    messages=[
                        {"role": "user", "content": description},
                    ],
                    temperature=0.7,  # Balanced creativity
                    # Enable JSON mode to enforce structured output
                    # This parameter tells Claude to always return valid JSON
                    response_format={"type": "json_object"},
                )

                # Extract response content
                if not response.content:
                    logger.error("Claude API returned empty content")
                    raise LLMResponseError("Claude API returned empty content")

                # Claude returns content as a list of content blocks
                # We'll concatenate all text blocks
                content_text = ""
                for block in response.content:
                    if hasattr(block, "text"):
                        content_text += block.text

                if not content_text:
                    logger.error("Claude API returned no text content")
                    raise LLMResponseError("Claude API returned no text content")

                # Log successful response metadata
                elapsed = time.time() - start_time
                # Extract token usage
                prompt_tokens = response.usage.input_tokens if response.usage else None
                completion_tokens = response.usage.output_tokens if response.usage else None

                # Record metrics
                from app.services.metrics import get_metrics_collector
                from app.utils.logging_helpers import log_llm_response

                metrics = get_metrics_collector()
                metrics.record_llm_request(
                    provider="anthropic",
                    model=self.model,
                    status="success",
                    duration=elapsed,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                )

                # Log structured response
                log_llm_response(
                    logger=logger,
                    provider="anthropic",
                    model=self.model,
                    duration=elapsed,
                    status="success",
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                )

                logger.info(
                    "Claude API call succeeded",
                    extra={
                        "model": self.model,
                        "retry_count": retry_count,
                        "latency_ms": int(elapsed * 1000),
                        "response_length": len(content_text),
                        "input_tokens": response.usage.input_tokens if response.usage else None,
                        "output_tokens": response.usage.output_tokens if response.usage else None,
                        "stop_reason": response.stop_reason,
                    },
                )

                return content_text

            except anthropic.AuthenticationError as e:
                # Authentication errors are not retryable
                logger.error(
                    "Claude authentication failed",
                    extra={"error": str(e), "retry_count": retry_count},
                )
                raise LLMConfigurationError(
                    f"Claude authentication failed: {e}. Please check your API key."
                )

            except anthropic.NotFoundError as e:
                # Model not found or endpoint not found - not retryable
                logger.error(
                    "Claude resource not found", extra={"error": str(e), "model": self.model}
                )
                raise LLMConfigurationError(
                    f"Claude resource not found: {e}. Please check your model name or endpoint."
                )

            except anthropic.PermissionDeniedError as e:
                # Permission errors are not retryable
                logger.error(
                    "Claude permission denied", extra={"error": str(e), "retry_count": retry_count}
                )
                raise LLMConfigurationError(
                    f"Claude permission denied: {e}. Please check your API key permissions."
                )

            except anthropic.BadRequestError as e:
                # Invalid request - check if it's a JSON mode error
                # Anthropic error responses may include type information in the body
                error_type = None
                if hasattr(e, "body") and isinstance(e.body, dict):
                    error_type = e.body.get("type")

                error_msg = str(e)

                # More specific detection for JSON format violations
                # Check for error type and message content to reduce false positives
                is_json_error = (
                    (error_type == "invalid_request_error" and "json" in error_msg.lower())
                    or "response_format" in error_msg.lower()
                    or ("response" in error_msg.lower() and "format" in error_msg.lower())
                )

                if is_json_error:
                    logger.error(
                        "Claude JSON format validation failed",
                        extra={
                            "error": str(e),
                            "retry_count": retry_count,
                            "error_type": error_type,
                        },
                    )
                    raise LLMResponseError(
                        f"Claude rejected response due to JSON format violation: {e}. "
                        f"The model output was not valid JSON."
                    )
                else:
                    logger.error(
                        "Claude invalid request",
                        extra={"error": str(e), "retry_count": retry_count},
                    )
                    raise LLMRequestError(
                        f"Claude invalid request: {e}. Please check your request parameters."
                    )

            except Exception as e:
                last_error = e

                # Check if this is an LLMResponseError (don't retry response parsing errors)
                if isinstance(e, LLMResponseError):
                    logger.error("Claude API returned invalid response", extra={"error": str(e)})
                    raise

                # Check if error is retryable
                if not self._is_retryable_error(e):
                    logger.error(
                        "Claude API call failed with non-retryable error",
                        extra={
                            "error": str(e),
                            "error_type": type(e).__name__,
                            "retry_count": retry_count,
                        },
                    )
                    raise LLMRequestError(f"Claude API request failed: {e}")

                # If we've exhausted retries, raise the error
                if retry_count >= self.max_retries:
                    elapsed = time.time() - start_time

                    # Record failure metrics
                    from app.services.metrics import get_metrics_collector
                    from app.utils.logging_helpers import log_llm_response

                    metrics = get_metrics_collector()
                    metrics.record_llm_request(
                        provider="anthropic", model=self.model, status="error", duration=elapsed
                    )

                    # Log structured error
                    log_llm_response(
                        logger=logger,
                        provider="anthropic",
                        model=self.model,
                        duration=elapsed,
                        status="error",
                        error_type=type(e).__name__,
                    )

                    logger.error(
                        "Claude API call failed after all retries",
                        extra={
                            "error": str(e),
                            "error_type": type(e).__name__,
                            "retry_count": retry_count,
                            "total_latency_ms": int(elapsed * 1000),
                        },
                    )
                    raise LLMRequestError(
                        f"Claude API request failed after {retry_count} retries: {e}"
                    )

                # Log retry attempt
                logger.warning(
                    "Claude API call failed, will retry",
                    extra={
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "retry_count": retry_count,
                        "backoff": backoff,
                    },
                )

                # Wait before retrying
                time.sleep(backoff)

                # Update backoff for next retry
                backoff = min(backoff * self.backoff_multiplier, self.max_backoff)
                retry_count += 1

        # Should never reach here, but just in case
        raise LLMRequestError(
            f"Claude API request failed after {retry_count} retries: {last_error}"
        )
