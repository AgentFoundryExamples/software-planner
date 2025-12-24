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


def get_client_ip(request: Request) -> Optional[str]:
    """Extract the client IP address from the request.
    
    This function attempts to extract the real client IP address,
    considering proxy headers like X-Forwarded-For and X-Real-IP only
    when the application is configured to trust proxies.
    
    Priority order when proxies are trusted:
    1. X-Forwarded-For (rightmost trusted IP in chain)
    2. X-Real-IP
    3. request.client.host (direct connection)
    
    When proxies are not trusted (default), only uses direct connection IP.
    
    Args:
        request: The incoming request.
        
    Returns:
        Client IP address as a string, or None if unavailable.
        
    Security Note:
        Proxy headers (X-Forwarded-For, X-Real-IP) can be spoofed by clients.
        By default, this function does NOT trust proxy headers to prevent
        IP spoofing attacks that could bypass rate limiting.
        
        To enable proxy header trust (only if behind a trusted proxy/load balancer),
        set PLANNER_TRUST_PROXY_HEADERS=true in environment configuration.
        
        When proxy headers are trusted, we use the rightmost IP in X-Forwarded-For
        that is outside our trusted proxy ranges as the client IP. This prevents
        clients from injecting fake IPs at the beginning of the chain.
    """
    # Check if we should trust proxy headers
    trust_proxy = getattr(settings, 'planner_trust_proxy_headers', False)
    
    if trust_proxy:
        # Trust proxy headers - use X-Forwarded-For or X-Real-IP
        # For X-Forwarded-For, we take the rightmost IP that is not a known proxy
        # This prevents clients from spoofing by adding fake IPs to the left
        x_forwarded_for = request.headers.get("X-Forwarded-For", "").strip()
        if x_forwarded_for:
            # Split by comma and take rightmost IP (closest to us in the chain)
            # In a proper deployment, this should be the last untrusted IP
            ips = [ip.strip() for ip in x_forwarded_for.split(",") if ip.strip()]
            if ips:
                # Use the rightmost IP as it's closest to our server
                # In production with trusted proxies, consider implementing
                # trusted proxy IP ranges and selecting the rightmost untrusted IP
                client_ip = ips[-1]
                if client_ip:
                    return client_ip
        
        # Check X-Real-IP header (alternative proxy header)
        x_real_ip = request.headers.get("X-Real-IP", "").strip()
        if x_real_ip:
            return x_real_ip
    
    # Always fall back to direct connection IP (most secure)
    # This is used when:
    # 1. Proxy headers are not trusted (default)
    # 2. Proxy headers are trusted but not present
    if request.client and request.client.host:
        return request.client.host
    
    return None
