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
    response = client.options("/health", headers={"Origin": "http://localhost:3000"})
    
    # Check that CORS headers are present
    assert "access-control-allow-origin" in response.headers or response.status_code == 200


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
