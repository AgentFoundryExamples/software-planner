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
"""Tests for FastAPI application."""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app, app


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


def test_create_app():
    """Test that create_app returns a FastAPI instance."""
    test_app = create_app()
    assert test_app is not None
    assert hasattr(test_app, "router")


def test_app_attributes():
    """Test that app has correct attributes."""
    assert app.title == "Software Planner API"
    assert app.version == "0.1.0"
    assert app.debug is False


def test_health_check(client):
    """Test the health check endpoint."""
    response = client.get("/health")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["app_name"] == "Software Planner API"
    assert data["version"] == "0.1.0"


def test_root_endpoint(client):
    """Test the root endpoint."""
    response = client.get("/")
    
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "Software Planner API" in data["message"]
    assert data["version"] == "0.1.0"
    assert data["docs"] == "/api/v1/docs"


def test_docs_available(client):
    """Test that API documentation is available."""
    response = client.get("/api/v1/docs")
    assert response.status_code == 200


def test_openapi_schema(client):
    """Test that OpenAPI schema is available."""
    response = client.get("/api/v1/openapi.json")
    
    assert response.status_code == 200
    schema = response.json()
    assert "openapi" in schema
    assert schema["info"]["title"] == "Software Planner API"
    assert schema["info"]["version"] == "0.1.0"


def test_cors_headers(client):
    """Test that CORS headers are properly configured."""
    origin = "http://localhost:3000"
    # Use GET request instead of OPTIONS since the endpoint doesn't define OPTIONS
    response = client.get("/health", headers={"Origin": origin})
    
    assert response.status_code == 200
    # With default settings (allow_origins=["*"]), the header should be "*"
    assert response.headers.get("access-control-allow-origin") == "*"


def test_nonexistent_endpoint(client):
    """Test that nonexistent endpoints return 404."""
    response = client.get("/nonexistent")
    
    assert response.status_code == 404


def test_app_starts_without_routes():
    """Test that app can be created even without any API routes registered."""
    test_app = create_app()
    
    # Should not fail even though no routes are registered yet
    assert test_app is not None
    
    # Test client should work
    test_client = TestClient(test_app)
    response = test_client.get("/health")
    assert response.status_code == 200


def test_get_app_function():
    """Test that get_app function works correctly."""
    from app.main import get_app
    
    test_app = get_app()
    assert test_app is not None
    assert hasattr(test_app, "router")


def test_http_exception_handler(client):
    """Test that HTTP exceptions return consistent JSON responses."""
    response = client.get("/nonexistent")
    
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert "status_code" in data
    assert data["status_code"] == 404


def test_validation_error_handler():
    """Test that validation errors return detailed error information."""
    from fastapi import FastAPI, Query
    from fastapi.testclient import TestClient
    
    test_app = create_app()
    
    # Add a test endpoint that requires validation
    @test_app.get("/test-validation")
    async def test_validation_endpoint(required_param: int = Query(...)):
        return {"value": required_param}
    
    test_client = TestClient(test_app)
    
    # Call without required parameter
    response = test_client.get("/test-validation")
    
    assert response.status_code == 422
    data = response.json()
    assert "error" in data
    assert "status_code" in data
    assert "details" in data
    assert data["status_code"] == 422


def test_general_exception_handler():
    """Test that unexpected exceptions return generic error response."""
    test_app = create_app()
    
    # Add a test endpoint that raises an exception
    @test_app.get("/test-error")
    async def test_error_endpoint():
        raise RuntimeError("Test error")
    
    # Use raise_server_exceptions=False to catch the exception in the handler
    test_client = TestClient(test_app, raise_server_exceptions=False)
    
    response = test_client.get("/test-error")
    
    assert response.status_code == 500
    data = response.json()
    assert "error" in data
    assert data["error"] == "Internal server error"
    assert data["status_code"] == 500
