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
"""Request ID middleware for tracing requests."""

import logging
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware to generate or extract request IDs for tracing.

    This middleware:
    1. Reads the inbound X-Request-ID header or generates a UUID if missing
    2. Stores the request ID in request.state for access in endpoints
    3. Echoes the request ID in the response X-Request-ID header
    4. Logs the request ID for correlation

    If a client provides a request ID that appears to be a collision or invalid,
    the server generates a new one and logs the overwrite.
    """

    REQUEST_ID_HEADER = "X-Request-ID"

    async def dispatch(self, request: Request, call_next) -> Response:
        """Process the request and add request ID handling.

        Args:
            request: The incoming request.
            call_next: The next middleware or endpoint handler.

        Returns:
            Response with X-Request-ID header added.
        """
        # Check for inbound request ID (case-insensitive header lookup)
        inbound_request_id = request.headers.get(self.REQUEST_ID_HEADER, "").strip()

        # Validate and use inbound request ID or generate new one
        if inbound_request_id:
            # Validate that it looks like a reasonable request ID
            # Allow alphanumeric strings with common separators, and reasonable length (128 chars)
            # This accepts UUIDs and other tracing formats like "trace-123-span-456"
            if len(inbound_request_id) <= 128 and all(
                c.isalnum() or c in "-_." for c in inbound_request_id
            ):
                request_id = inbound_request_id
            else:
                # Invalid format - generate new one and log
                request_id = str(uuid.uuid4())
                logger.warning(
                    "Invalid request ID format received, generated new ID",
                    extra={
                        "invalid_request_id": inbound_request_id[:64],  # Truncate for safety
                        "generated_request_id": request_id,
                    },
                )
        else:
            # Generate new UUID for this request
            request_id = str(uuid.uuid4())

        # Store request ID in request state for access in endpoints and dependencies
        request.state.request_id = request_id

        # Log the request with request ID
        logger.info(
            f"{request.method} {request.url.path}",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "client_host": request.client.host if request.client else None,
            },
        )

        # Call the next handler
        response = await call_next(request)

        # Add request ID to response headers
        response.headers[self.REQUEST_ID_HEADER] = request_id

        return response
