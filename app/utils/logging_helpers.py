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
"""Logging helpers for structured observability.

This module provides utilities for structured logging with security-aware
field sanitization. It ensures sensitive data (API keys, prompts, secrets)
is never logged while maintaining useful context for debugging and monitoring.
"""

import hashlib
import logging
from typing import Optional, Dict, Any


def hash_api_key(api_key: Optional[str]) -> Optional[str]:
    """Hash an API key for safe logging.
    
    Creates a SHA-256 hash of the API key and returns the first 16 characters.
    This provides a stable identifier for rate limiting and debugging without
    exposing the actual key.
    
    Args:
        api_key: The API key to hash, or None
        
    Returns:
        First 16 characters of SHA-256 hash, or None if input is None
        
    Example:
        >>> hash_api_key("sk-secret-key-12345")
        "a1b2c3d4e5f6g7h8"
    """
    if api_key is None or not api_key:
        return None
    
    return hashlib.sha256(api_key.encode('utf-8')).hexdigest()[:16]


def create_structured_log_context(
    request_id: Optional[str] = None,
    job_id: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    status: Optional[str] = None,
    error_type: Optional[str] = None,
    **extra_fields
) -> Dict[str, Any]:
    """Create a structured logging context dictionary.
    
    Builds a dictionary of log fields with common observability attributes.
    Automatically hashes API keys and excludes None values.
    
    Args:
        request_id: Optional request identifier
        job_id: Optional job identifier
        api_key: Optional API key (will be hashed)
        model: Optional model name
        status: Optional status string
        error_type: Optional error type
        **extra_fields: Additional custom fields
        
    Returns:
        Dictionary of non-None log fields with hashed API key
        
    Example:
        >>> context = create_structured_log_context(
        ...     request_id="req-123",
        ...     job_id="job-456",
        ...     api_key="sk-secret",
        ...     custom_field="value"
        ... )
        >>> logger.info("Processing request", extra=context)
    """
    context = {}
    
    if request_id is not None:
        context['request_id'] = request_id
    
    if job_id is not None:
        context['job_id'] = job_id
    
    if api_key is not None:
        context['api_key_hash'] = hash_api_key(api_key)
    
    if model is not None:
        context['model'] = model
    
    if status is not None:
        context['status'] = status
    
    if error_type is not None:
        context['error_type'] = error_type
    
    # Add extra fields, filtering out None values
    for key, value in extra_fields.items():
        if value is not None:
            context[key] = value
    
    return context


def log_job_transition(
    logger: logging.Logger,
    job_id: str,
    from_status: Optional[str],
    to_status: str,
    **extra_fields
):
    """Log a job status transition with structured context.
    
    Args:
        logger: Logger instance to use
        job_id: Job identifier
        from_status: Previous status (None for initial creation)
        to_status: New status
        **extra_fields: Additional custom fields
    """
    context = create_structured_log_context(
        job_id=job_id,
        from_status=from_status,
        to_status=to_status,
        **extra_fields
    )
    
    if from_status:
        logger.info(f"Job {job_id} transitioned: {from_status} -> {to_status}", extra=context)
    else:
        logger.info(f"Job {job_id} created with status: {to_status}", extra=context)


def log_llm_request(
    logger: logging.Logger,
    provider: str,
    model: str,
    description_length: int,
    request_id: Optional[str] = None,
    job_id: Optional[str] = None,
    **extra_fields
):
    """Log an LLM API request with structured context.
    
    Logs request metadata without exposing the actual prompt content.
    
    Args:
        logger: Logger instance to use
        provider: LLM provider name
        model: Model identifier
        description_length: Length of description in characters
        request_id: Optional request identifier
        job_id: Optional job identifier
        **extra_fields: Additional custom fields
    """
    context = create_structured_log_context(
        request_id=request_id,
        job_id=job_id,
        model=model,
        provider=provider,
        description_length=description_length,
        **extra_fields
    )
    
    logger.info(f"LLM request started: {provider}/{model}", extra=context)


def log_llm_response(
    logger: logging.Logger,
    provider: str,
    model: str,
    duration: float,
    status: str,
    request_id: Optional[str] = None,
    job_id: Optional[str] = None,
    prompt_tokens: Optional[int] = None,
    completion_tokens: Optional[int] = None,
    **extra_fields
):
    """Log an LLM API response with structured context.
    
    Logs response metadata including latency and token counts without
    exposing the actual response content.
    
    Args:
        logger: Logger instance to use
        provider: LLM provider name
        model: Model identifier
        duration: Request duration in seconds
        status: Response status (success, error, timeout)
        request_id: Optional request identifier
        job_id: Optional job identifier
        prompt_tokens: Optional prompt token count
        completion_tokens: Optional completion token count
        **extra_fields: Additional custom fields
    """
    context = create_structured_log_context(
        request_id=request_id,
        job_id=job_id,
        model=model,
        provider=provider,
        duration_seconds=duration,
        status=status,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        **extra_fields
    )
    
    logger.info(f"LLM request completed: {provider}/{model} ({status})", extra=context)


def log_http_request(
    logger: logging.Logger,
    method: str,
    endpoint: str,
    status: int,
    duration: float,
    request_id: Optional[str] = None,
    api_key: Optional[str] = None,
    **extra_fields
):
    """Log an HTTP request with structured context.
    
    Args:
        logger: Logger instance to use
        method: HTTP method (GET, POST, etc.)
        endpoint: API endpoint path
        status: HTTP status code
        duration: Request duration in seconds
        request_id: Optional request identifier
        api_key: Optional API key (will be hashed)
        **extra_fields: Additional custom fields
    """
    context = create_structured_log_context(
        request_id=request_id,
        api_key=api_key,
        method=method,
        endpoint=endpoint,
        status=status,
        duration_seconds=duration,
        **extra_fields
    )
    
    logger.info(f"{method} {endpoint} {status}", extra=context)
