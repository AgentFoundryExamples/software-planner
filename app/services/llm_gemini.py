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
"""Google Gemini-based LLM client implementation.

This module provides a concrete implementation of BaseLLMClient using Google's Gemini API.
It uses the official Google GenAI Python SDK and implements retry logic for transient failures.

Key features:
- Uses Google GenAI API (recommended for Gemini models)
- Configurable retry logic with exponential backoff for transient errors
- Structured logging without exposing secrets
- Proper error classification and handling
"""

import logging
import time
from typing import Optional

from google import genai
from google.genai import types

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


class GeminiClient(BaseLLMClient):
    """Google Gemini implementation of the LLM client.
    
    This client uses the Google GenAI API to generate specifications.
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
        client: Google GenAI SDK client instance.
        max_retries: Maximum number of retry attempts for transient errors.
        initial_backoff: Initial backoff delay in seconds.
        max_backoff: Maximum backoff delay in seconds.
        backoff_multiplier: Multiplier for exponential backoff.
    
    Example:
        >>> client = GeminiClient(
        ...     api_key="your-api-key",
        ...     model="gemini-3.0-pro",
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
        """Initialize Gemini client.
        
        Args:
            api_key: Google API key.
            model: Model identifier (e.g., 'gemini-3.0-pro', 'gemini-2.0-flash').
            base_url: Optional base URL for custom endpoints (not commonly used with Gemini).
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
        
        # Initialize Google GenAI client
        try:
            # Note: base_url is not directly supported in google-genai SDK
            # If custom endpoint is needed, http_options can be used
            http_options = None
            if base_url:
                logger.warning(
                    "base_url is not directly supported by Google GenAI SDK, ignoring",
                    extra={"base_url": base_url}
                )
            
            self.client = genai.Client(api_key=api_key)
            
            logger.info(
                "Gemini client initialized",
                extra={
                    "model": model,
                    "has_base_url": bool(base_url),
                    "timeout": timeout,
                    "max_retries": max_retries,
                }
            )
        except Exception as e:
            logger.error(
                "Failed to initialize Gemini client",
                extra={"error": str(e), "error_type": type(e).__name__}
            )
            raise LLMConfigurationError(f"Failed to initialize Gemini client: {e}")
    
    def _is_retryable_error(self, error: Exception) -> bool:
        """Determine if an error is retryable.
        
        Retryable errors include:
        - Rate limit errors (429)
        - Server errors (500-599)
        - Timeout errors
        - Service unavailable errors
        
        Non-retryable errors include:
        - Authentication errors (401, 403)
        - Not found errors (404)
        - Invalid request errors (400)
        
        Args:
            error: The exception to check.
            
        Returns:
            True if the error should be retried, False otherwise.
        """
        # First, check for specific status codes if available
        # This is more reliable than string matching
        if hasattr(error, 'code'):
            code = getattr(error, 'code', None)
            if code in [429, 500, 502, 503, 504]:
                return True
            # Non-retryable status codes
            if code in [400, 401, 403, 404]:
                return False
        
        # Check for status in response if available
        if hasattr(error, 'response') and error.response is not None:
            status_code = getattr(error.response, 'status_code', None)
            if status_code in [429, 500, 502, 503, 504]:
                return True
            if status_code in [400, 401, 403, 404]:
                return False
        
        # Fall back to string matching for error types and messages
        # Convert to lowercase for case-insensitive matching
        error_str = str(error).lower()
        error_type = type(error).__name__.lower()
        
        # Check for retryable conditions
        retryable_keywords = [
            'timeout',
            'rate limit',
            'quota',
            'unavailable',
            'deadline',
            'overloaded',
            'resource exhausted',
        ]
        
        for keyword in retryable_keywords:
            if keyword in error_str or keyword in error_type:
                return True
        
        # Check for non-retryable conditions
        non_retryable_keywords = [
            'authentication',
            'auth',
            'permission',
            'forbidden',
            'invalid',
            'not found',
        ]
        
        for keyword in non_retryable_keywords:
            if keyword in error_str or keyword in error_type:
                return False
        
        # Default to non-retryable for unknown errors to avoid infinite loops
        return False
    
    def _call_llm_api(self, description: str, system_prompt: str) -> str:
        """Call Google Gemini API with retry logic.
        
        This method implements exponential backoff retry logic for transient failures.
        It uses Google's GenAI API with the configured model.
        
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
            provider="google",
            model=self.model,
            description_length=len(description)
        )
        
        while retry_count <= self.max_retries:
            try:
                # Log attempt (not on first try to avoid log spam)
                if retry_count > 0:
                    logger.info(
                        "Retrying Gemini API call",
                        extra={
                            "retry_count": retry_count,
                            "max_retries": self.max_retries,
                            "backoff": backoff,
                        }
                    )
                
                # Make the API call using generate_content
                # Combine system prompt and user message for Gemini
                full_prompt = f"{system_prompt}\n\nUser request:\n{description}"
                
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=full_prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.7,  # Balanced creativity
                        max_output_tokens=2000,  # Reasonable limit for spec generation
                    ),
                )
                
                # Extract response content
                if not response.text:
                    logger.error("Gemini API returned empty response")
                    raise LLMResponseError("Gemini API returned empty response")
                
                content_text = response.text
                
                # Log successful response metadata
                elapsed = time.time() - start_time
                
                # Extract token usage if available
                input_tokens = None
                output_tokens = None
                if hasattr(response, 'usage_metadata'):
                    input_tokens = getattr(response.usage_metadata, 'prompt_token_count', None)
                    output_tokens = getattr(response.usage_metadata, 'candidates_token_count', None)
                
                # Record metrics
                from app.services.metrics import get_metrics_collector
                from app.utils.logging_helpers import log_llm_response
                
                metrics = get_metrics_collector()
                metrics.record_llm_request(
                    provider="google",
                    model=self.model,
                    status="success",
                    duration=elapsed,
                    prompt_tokens=input_tokens,
                    completion_tokens=output_tokens
                )
                
                # Log structured response
                log_llm_response(
                    logger=logger,
                    provider="google",
                    model=self.model,
                    duration=elapsed,
                    status="success",
                    prompt_tokens=input_tokens,
                    completion_tokens=output_tokens
                )
                
                logger.info(
                    "Gemini API call succeeded",
                    extra={
                        "model": self.model,
                        "retry_count": retry_count,
                        "latency_ms": int(elapsed * 1000),
                        "response_length": len(content_text),
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                    }
                )
                
                return content_text
                
            except Exception as e:
                last_error = e
                error_str = str(e).lower()
                
                # Check if this is an LLMResponseError (don't retry response parsing errors)
                if isinstance(e, LLMResponseError):
                    logger.error(
                        "Gemini API returned invalid response",
                        extra={"error": str(e)}
                    )
                    raise
                
                # Check for authentication/permission errors (not retryable)
                if any(keyword in error_str for keyword in ['auth', 'permission', 'forbidden', '401', '403']):
                    logger.error(
                        "Gemini authentication/permission error",
                        extra={"error": str(e), "retry_count": retry_count}
                    )
                    raise LLMConfigurationError(
                        f"Gemini authentication failed: {e}. Please check your API key and permissions."
                    )
                
                # Check for not found errors (not retryable)
                if '404' in error_str or 'not found' in error_str:
                    logger.error(
                        "Gemini resource not found",
                        extra={"error": str(e), "model": self.model}
                    )
                    raise LLMConfigurationError(
                        f"Gemini resource not found: {e}. Please check your model name."
                    )
                
                # Check for bad request errors (not retryable)
                if '400' in error_str or 'bad request' in error_str or 'invalid' in error_str:
                    logger.error(
                        "Gemini invalid request",
                        extra={"error": str(e), "retry_count": retry_count}
                    )
                    raise LLMRequestError(
                        f"Gemini invalid request: {e}. Please check your request parameters."
                    )
                
                # Check if error is retryable
                if not self._is_retryable_error(e):
                    logger.error(
                        "Gemini API call failed with non-retryable error",
                        extra={
                            "error": str(e),
                            "error_type": type(e).__name__,
                            "retry_count": retry_count,
                        }
                    )
                    raise LLMRequestError(f"Gemini API request failed: {e}")
                
                # If we've exhausted retries, raise the error
                if retry_count >= self.max_retries:
                    elapsed = time.time() - start_time
                    
                    # Record failure metrics
                    from app.services.metrics import get_metrics_collector
                    from app.utils.logging_helpers import log_llm_response
                    
                    metrics = get_metrics_collector()
                    metrics.record_llm_request(
                        provider="google",
                        model=self.model,
                        status="error",
                        duration=elapsed
                    )
                    
                    # Log structured error
                    log_llm_response(
                        logger=logger,
                        provider="google",
                        model=self.model,
                        duration=elapsed,
                        status="error",
                        error_type=type(e).__name__
                    )
                    
                    logger.error(
                        "Gemini API call failed after all retries",
                        extra={
                            "error": str(e),
                            "error_type": type(e).__name__,
                            "retry_count": retry_count,
                            "total_latency_ms": int(elapsed * 1000),
                        }
                    )
                    raise LLMRequestError(
                        f"Gemini API request failed after {retry_count} retries: {e}"
                    )
                
                # Log retry attempt
                logger.warning(
                    "Gemini API call failed, will retry",
                    extra={
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "retry_count": retry_count,
                        "backoff": backoff,
                    }
                )
                
                # Wait before retrying
                time.sleep(backoff)
                
                # Update backoff for next retry
                backoff = min(backoff * self.backoff_multiplier, self.max_backoff)
                retry_count += 1
        
        # Should never reach here, but just in case
        raise LLMRequestError(
            f"Gemini API request failed after {retry_count} retries: {last_error}"
        )
