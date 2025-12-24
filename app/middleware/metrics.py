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
"""Metrics middleware for HTTP request instrumentation."""

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.services.metrics import get_metrics_collector
from app.utils.logging_helpers import log_http_request

logger = logging.getLogger(__name__)


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware for collecting HTTP request metrics and structured logging.

    This middleware:
    - Measures request duration
    - Records HTTP metrics (requests total, duration)
    - Logs HTTP requests with structured context
    - Extracts API key from headers for rate limiting context
    """

    async def dispatch(self, request: Request, call_next):
        """Process request and record metrics.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler in chain

        Returns:
            HTTP response from downstream handlers
        """
        # Record start time
        start_time = time.time()

        # Get request metadata
        method = request.method
        path = request.url.path
        request_id = getattr(request.state, "request_id", "unknown")

        # Extract API key from headers if present (will be hashed for logging)
        api_key = request.headers.get("X-API-Key")

        # Process request
        response = await call_next(request)

        # Calculate duration
        duration = time.time() - start_time

        # Record metrics (wrapped in try-except to prevent middleware failures)
        try:
            metrics = get_metrics_collector()
            metrics.record_http_request(
                endpoint=path, method=method, status=response.status_code, duration=duration
            )
        except Exception as e:
            logger.warning(
                f"Failed to record HTTP metrics: {e}",
                extra={"error": str(e), "error_type": type(e).__name__},
                exc_info=False,
            )

        # Log request with structured context (wrapped in try-except to prevent middleware failures)
        try:
            log_http_request(
                logger=logger,
                method=method,
                endpoint=path,
                status=response.status_code,
                duration=duration,
                request_id=request_id,
                api_key=api_key,
            )
        except Exception as e:
            logger.warning(
                f"Failed to log HTTP request: {e}",
                extra={"error": str(e), "error_type": type(e).__name__},
                exc_info=False,
            )

        return response
