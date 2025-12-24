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
"""FastAPI application factory and main entrypoint."""

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.routes import router as plan_router
from app.core.config import settings
from app.middleware import RequestIDMiddleware
from app.models.error import ErrorCode, create_error_response
from app.services.store_singleton import get_job_store

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        FastAPI: Configured FastAPI application instance.
    """
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        docs_url=f"{settings.api_prefix}/docs",
        redoc_url=f"{settings.api_prefix}/redoc",
        openapi_url=f"{settings.api_prefix}/openapi.json",
    )

    # Add request ID middleware (must be added before other middleware)
    app.add_middleware(RequestIDMiddleware)

    # Add metrics middleware for observability
    from app.middleware.metrics import MetricsMiddleware

    app.add_middleware(MetricsMiddleware)

    # Configure CORS
    # Note: allow_credentials should only be True when allowed_origins is not ["*"]
    # This can be configured via environment variables
    # Expose X-Request-ID header so clients can read it from responses
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=settings.allowed_credentials,
        allow_methods=settings.allowed_methods,
        allow_headers=settings.allowed_headers,
        expose_headers=["X-Request-ID"],
    )

    # Global exception handlers for consistent error responses
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        """Handle HTTP exceptions with consistent JSON responses."""
        # Get request ID from middleware
        request_id = getattr(request.state, "request_id", None)

        # Check if detail is already a standardized error response
        if isinstance(exc.detail, dict) and "error" in exc.detail:
            # Already formatted, just return it
            # Update request_id if not present
            if "request_id" not in exc.detail["error"] and request_id:
                exc.detail["error"]["request_id"] = request_id
            return JSONResponse(
                status_code=exc.status_code,
                content=exc.detail,
                headers=exc.headers if hasattr(exc, "headers") else None,
            )

        # Map status code to error code
        if exc.status_code == 401:
            code = ErrorCode.MISSING_AUTH
        elif exc.status_code == 403:
            code = ErrorCode.INVALID_AUTH
        elif exc.status_code == 404:
            code = ErrorCode.NOT_FOUND
        elif exc.status_code == 429:
            code = ErrorCode.RATE_LIMIT_EXCEEDED
        elif exc.status_code >= 500:
            code = ErrorCode.INTERNAL_ERROR
        else:
            code = ErrorCode.VALIDATION_ERROR

        error_response = create_error_response(
            code=code,
            message=exc.detail if isinstance(exc.detail, str) else str(exc.detail),
            request_id=request_id,
        )

        return JSONResponse(
            status_code=exc.status_code,
            content=error_response,
            headers=exc.headers if hasattr(exc, "headers") else None,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Handle request validation errors with detailed information."""
        # Get request ID from middleware
        request_id = getattr(request.state, "request_id", None)

        # Check if any error is a ValueError (custom validation)
        # Return 400 for custom validation errors, 422 for schema/type errors
        errors = exc.errors()

        # Clean error details to ensure JSON serializability
        cleaned_errors = []
        is_custom_validation = False

        for err in errors:
            error_type = err.get("type", "")

            # Check if this is a custom validation error (ValueError from field_validator)
            if error_type == "value_error":
                is_custom_validation = True

            cleaned_err = {
                "loc": err.get("loc", []),
                "msg": err.get("msg", ""),
                "type": error_type,
            }

            # Only add input if it's JSON serializable (and not too large)
            input_val = err.get("input")
            if input_val is not None and isinstance(input_val, (str, int, float, bool, type(None))):
                if isinstance(input_val, str) and len(input_val) <= 100:
                    cleaned_err["input"] = input_val
                elif not isinstance(input_val, str):
                    cleaned_err["input"] = input_val

            cleaned_errors.append(cleaned_err)

        # Determine error code based on validation type
        # NOTE: We use string matching on error messages to map to specific error codes.
        # This is pragmatic given Pydantic's ValidationError API which doesn't expose
        # custom error types. Alternative approaches (custom exception hierarchy, error
        # context) would require more invasive changes to Pydantic's validation flow.
        # If validation messages change significantly, these mappings may need updates.
        if is_custom_validation:
            # Check all error messages to find the most specific error code.
            # The order of checks determines priority.
            all_error_msgs = " ".join(err.get("msg", "").lower() for err in errors)

            if (
                "exceeds" in all_error_msgs
                or "too large" in all_error_msgs
                or "maximum length" in all_error_msgs
            ):
                code = ErrorCode.PAYLOAD_TOO_LARGE
            elif "control character" in all_error_msgs or "null byte" in all_error_msgs:
                code = ErrorCode.INVALID_DESCRIPTION
            elif "empty" in all_error_msgs or "whitespace" in all_error_msgs:
                code = ErrorCode.INVALID_DESCRIPTION
            else:
                code = ErrorCode.VALIDATION_ERROR
        else:
            # Schema/type errors
            if any("missing" in err.get("type", "") for err in errors):
                code = ErrorCode.MISSING_FIELD
            elif any("type" in err.get("type", "") for err in errors):
                code = ErrorCode.INVALID_TYPE
            else:
                code = ErrorCode.MALFORMED_REQUEST

        status_code = (
            status.HTTP_400_BAD_REQUEST
            if is_custom_validation
            else status.HTTP_422_UNPROCESSABLE_ENTITY
        )

        # Build details dict
        details = {"validation_errors": cleaned_errors}

        error_response = create_error_response(
            code=code, message="Validation error", details=details, request_id=request_id
        )

        return JSONResponse(
            status_code=status_code,
            content=error_response,
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Handle unexpected exceptions with generic error response."""
        # Get request ID from middleware
        request_id = getattr(request.state, "request_id", None)

        # Log the error with request ID for debugging
        logger.error(
            f"Unhandled exception: {exc}",
            extra={
                "request_id": request_id,
                "error_type": type(exc).__name__,
                "path": request.url.path if hasattr(request, "url") else None,
            },
            exc_info=True,
        )

        error_response = create_error_response(
            code=ErrorCode.INTERNAL_ERROR, message="Internal server error", request_id=request_id
        )

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response,
        )

    # Health check endpoint
    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "ok"}

    # Root endpoint
    @app.get("/")
    async def root():
        """Root endpoint with API information."""
        return {
            "message": f"Welcome to {settings.app_name}",
            "version": settings.app_version,
            "docs": f"{settings.api_prefix}/docs",
        }

    # Register API routes
    app.include_router(plan_router, prefix=settings.api_prefix, tags=["planning"])

    # Startup event handler
    @app.on_event("startup")
    async def startup_event():
        """Handle application startup - recover stuck jobs."""
        logger.info("Application startup - recovering stuck jobs")
        try:
            job_repo = get_job_store()
            recovered_count = await job_repo.recover_stuck_jobs()
            if recovered_count > 0:
                logger.warning(
                    f"Recovered {recovered_count} stuck jobs on startup",
                    extra={"recovered_count": recovered_count},
                )
        except Exception as e:
            logger.error(
                f"Failed to recover stuck jobs on startup: {e}",
                extra={"error": str(e), "error_type": type(e).__name__},
                exc_info=True,
            )
            # Don't fail startup if recovery fails

    return app


def get_app() -> FastAPI:
    """Create a new FastAPI application instance.

    This function creates a fresh application instance each time it's called,
    which is useful for testing or when you need isolated app instances.
    For production use with the global app instance, see the `app` variable below.

    Returns:
        FastAPI: A new configured FastAPI application instance.
    """
    return create_app()


# Create application instance
# Note: For production with multiple workers, consider using application factories
# rather than a global instance to avoid shared state issues.
app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        reload_dirs=["app"],
    )
