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

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.routes import router as plan_router
from app.core.config import settings
from app.services.job_store import JobStore


# Global job store instance
job_store = JobStore()


def get_job_store() -> JobStore:
    """Get the global job store instance for dependency injection.
    
    Returns:
        JobStore: The global job store instance.
    """
    return job_store


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
    
    # Configure CORS
    # Note: allow_credentials should only be True when allowed_origins is not ["*"]
    # This can be configured via environment variables
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=settings.allowed_credentials,
        allow_methods=settings.allowed_methods,
        allow_headers=settings.allowed_headers,
    )
    
    # Global exception handlers for consistent error responses
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        """Handle HTTP exceptions with consistent JSON responses."""
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.detail,
                "status_code": exc.status_code,
            },
        )
    
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Handle request validation errors with detailed information."""
        # Check if any error is a ValueError (custom validation)
        # Return 400 for custom validation errors, 422 for schema/type errors
        errors = exc.errors()
        
        # Clean error details to ensure JSON serializability
        cleaned_errors = []
        for err in errors:
            cleaned_err = {
                "loc": err.get("loc", []),
                "msg": err.get("msg", ""),
                "type": err.get("type", ""),
            }
            # Only add input if it's JSON serializable (and not too large)
            input_val = err.get("input")
            if input_val is not None and isinstance(input_val, (str, int, float, bool, type(None))):
                if isinstance(input_val, str) and len(input_val) <= 100:
                    cleaned_err["input"] = input_val
                elif not isinstance(input_val, str):
                    cleaned_err["input"] = input_val
            cleaned_errors.append(cleaned_err)
        
        is_custom_validation = any(
            err.get("type") == "value_error" for err in errors
        )
        
        status_code = status.HTTP_400_BAD_REQUEST if is_custom_validation else status.HTTP_422_UNPROCESSABLE_ENTITY
        
        return JSONResponse(
            status_code=status_code,
            content={
                "error": "Validation error",
                "status_code": status_code,
                "details": cleaned_errors,
            },
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Handle unexpected exceptions with generic error response."""
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Internal server error",
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            },
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
            "docs": f"{settings.api_prefix}/docs"
        }
    
    # Register API routes
    app.include_router(plan_router, prefix=settings.api_prefix, tags=["planning"])
    
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
