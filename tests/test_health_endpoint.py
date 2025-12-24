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
"""Tests for the /health endpoint."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="session")
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


class TestHealthEndpoint:
    """Test cases for the /health endpoint."""

    def test_health_endpoint_returns_ok(self, client):
        """Test that GET /health returns 200 with correct JSON structure and content type."""
        response = client.get("/health")

        assert response.status_code == 200
        assert "application/json" in response.headers.get("content-type", "")

        data = response.json()
        assert data == {"status": "ok"}
        assert len(data) == 1
        assert isinstance(data["status"], str)

    def test_health_endpoint_does_not_accept_post(self, client):
        """Test that POST requests to /health are not allowed."""
        response = client.post("/health")

        # Should return 405 Method Not Allowed
        assert response.status_code == 405

    def test_health_endpoint_does_not_accept_put(self, client):
        """Test that PUT requests to /health are not allowed."""
        response = client.put("/health")

        # Should return 405 Method Not Allowed
        assert response.status_code == 405

    def test_health_endpoint_does_not_accept_delete(self, client):
        """Test that DELETE requests to /health are not allowed."""
        response = client.delete("/health")

        # Should return 405 Method Not Allowed
        assert response.status_code == 405

    def test_health_endpoint_with_query_params_ignored(self, client):
        """Test that query parameters are ignored by /health endpoint."""
        response = client.get("/health?param=value&another=test")

        # Should still work normally
        assert response.status_code == 200
        data = response.json()
        assert data == {"status": "ok"}

    def test_health_endpoint_with_headers(self, client):
        """Test that /health works with various request headers."""
        headers = {"Accept": "application/json", "User-Agent": "TestClient/1.0"}
        response = client.get("/health", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data == {"status": "ok"}
