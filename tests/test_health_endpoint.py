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


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


class TestHealthEndpoint:
    """Test cases for the /health endpoint."""
    
    def test_health_endpoint_returns_ok(self, client):
        """Test that GET /health returns status ok."""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data == {"status": "ok"}
    
    def test_health_endpoint_response_structure(self, client):
        """Test that /health response has correct structure."""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify it has exactly one key
        assert len(data) == 1
        assert "status" in data
        
        # Verify value is a string
        assert isinstance(data["status"], str)
        assert data["status"] == "ok"
    
    def test_health_endpoint_is_json(self, client):
        """Test that /health returns JSON content type."""
        response = client.get("/health")
        
        assert response.status_code == 200
        assert "application/json" in response.headers.get("content-type", "")
    
    def test_health_endpoint_multiple_calls_consistent(self, client):
        """Test that multiple calls to /health return consistent results."""
        responses = [client.get("/health") for _ in range(3)]
        
        # All should succeed
        for response in responses:
            assert response.status_code == 200
        
        # All should return identical JSON
        json_responses = [r.json() for r in responses]
        assert json_responses[0] == json_responses[1] == json_responses[2]
        assert all(data == {"status": "ok"} for data in json_responses)
    
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
        headers = {
            "Accept": "application/json",
            "User-Agent": "TestClient/1.0"
        }
        response = client.get("/health", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data == {"status": "ok"}
