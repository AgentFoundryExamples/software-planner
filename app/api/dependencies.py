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
"""FastAPI dependencies for authentication and common request handling."""

import logging
from typing import Optional
from fastapi import Header, HTTPException, Request, status

from app.core.config import settings

logger = logging.getLogger(__name__)


def require_api_key(
    request: Request,
    x_api_key: Optional[str] = Header(None, description="API key for authentication")
) -> str:
    """Validate API key from X-API-Key header.
    
    This dependency validates the API key and provides authentication for
    protected endpoints. It uses the standardized error response format
    defined in the global exception handlers.
    
    Args:
        request: The incoming request (for accessing request_id from state).
        x_api_key: The API key from X-API-Key header (case-insensitive header name).
        
    Returns:
        The validated API key (not stripped - must match exactly).
        
    Raises:
        HTTPException: 401 if header is missing, 403 if key is invalid.
        
    Note:
        Uses constant-time comparison to prevent timing attacks.
        Never logs the API key value, only the request ID.
        Keys must match exactly (no whitespace stripping) to prevent rate-limiting
        or logging bypass by adding/removing whitespace while still authenticating.
    """
    # Get request ID from request state for logging
    request_id = getattr(request.state, "request_id", "unknown")
    
    # Check if any API keys are configured
    if not settings.planner_api_keys:
        # No API keys configured - allow request but log warning
        # This maintains backward compatibility for deployments without auth
        logger.debug(
            "API key authentication skipped - no keys configured",
            extra={"request_id": request_id}
        )
        return ""
    
    # API keys are configured - require authentication
    if x_api_key is None:
        logger.warning(
            "Authentication failed: Missing X-API-Key header",
            extra={"request_id": request_id}
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header"
        )
    
    # Validate the API key using constant-time comparison
    if not settings.is_api_key_valid(x_api_key):
        logger.warning(
            "Authentication failed: Invalid API key",
            extra={"request_id": request_id}
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key"
        )
    
    # Authentication successful
    logger.debug(
        "Authentication successful",
        extra={"request_id": request_id}
    )
    
    return x_api_key


def get_request_id(request: Request) -> str:
    """Get the request ID from the request state.
    
    This is a convenience dependency for accessing the request ID
    that was set by the RequestIDMiddleware.
    
    Args:
        request: The incoming request.
        
    Returns:
        The request ID string.
    """
    return getattr(request.state, "request_id", "unknown")
