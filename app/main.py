"""FastAPI application factory and main entrypoint."""

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings


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
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "Validation error",
                "status_code": status.HTTP_422_UNPROCESSABLE_ENTITY,
                "details": exc.errors(),
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
        return {
            "status": "healthy",
            "app_name": settings.app_name,
            "version": settings.app_version
        }
    
    # Root endpoint
    @app.get("/")
    async def root():
        """Root endpoint with API information."""
        return {
            "message": f"Welcome to {settings.app_name}",
            "version": settings.app_version,
            "docs": f"{settings.api_prefix}/docs"
        }
    
    # Future API routes will be registered here
    # Example: app.include_router(some_router, prefix=settings.api_prefix)
    
    return app


def get_app() -> FastAPI:
    """Get or create the FastAPI application instance.
    
    This function allows for lazy initialization of the app instance.
    
    Returns:
        FastAPI: The configured FastAPI application instance.
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
