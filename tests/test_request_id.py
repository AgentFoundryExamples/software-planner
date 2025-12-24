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
"""Tests for request ID middleware and header handling."""

import uuid
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, Mock

from app.main import get_app
from app.core.config import Settings


@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client that returns valid specs."""
    client = Mock()
    client.generate_specs.return_value = {
        "specs": [
            {
                "purpose": "Test Purpose",
                "vision": "Test Vision",
                "must": ["Must have 1"],
                "dont": ["Don't do 1"],
                "nice": ["Nice to have 1"]
            }
        ]
    }
    return client


@pytest.fixture
def client_no_auth(mock_llm_client):
    """Create test client without authentication."""
    test_settings = Settings(
        planner_api_keys=[],
        planner_api_keys_required=False,
        allowed_origins=["*"],
        cors_wildcard_enabled=True
    )
    
    with patch('app.core.config.settings', test_settings):
        with patch('app.services.store_singleton.get_llm_client', return_value=mock_llm_client):
            app = get_app()
            yield TestClient(app)


class TestRequestIDGeneration:
    """Test cases for automatic request ID generation."""
    
    def test_request_id_generated_when_missing(self, client_no_auth):
        """Test that X-Request-ID is generated when not provided."""
        response = client_no_auth.get("/health")
        
        assert response.status_code == 200
        assert "X-Request-ID" in response.headers
        
        request_id = response.headers["X-Request-ID"]
        # Should be a valid UUID
        try:
            uuid.UUID(request_id)
        except ValueError:
            pytest.fail(f"Generated request ID is not a valid UUID: {request_id}")
    
    def test_request_id_different_for_each_request(self, client_no_auth):
        """Test that each request gets a unique request ID."""
        response1 = client_no_auth.get("/health")
        response2 = client_no_auth.get("/health")
        
        request_id1 = response1.headers["X-Request-ID"]
        request_id2 = response2.headers["X-Request-ID"]
        
        assert request_id1 != request_id2
    
    def test_request_id_present_on_all_endpoints(self, client_no_auth):
        """Test that X-Request-ID is present on all endpoint responses."""
        endpoints = [
            ("/health", "GET"),
            ("/api/v1/models", "GET"),
            ("/", "GET"),
        ]
        
        for path, method in endpoints:
            if method == "GET":
                response = client_no_auth.get(path)
            
            assert "X-Request-ID" in response.headers, f"Missing request ID on {method} {path}"


class TestRequestIDPropagation:
    """Test cases for request ID propagation from client."""
    
    def test_request_id_echoed_when_provided(self, client_no_auth):
        """Test that client-provided request ID is echoed back."""
        client_request_id = str(uuid.uuid4())
        
        response = client_no_auth.get(
            "/health",
            headers={"X-Request-ID": client_request_id}
        )
        
        assert response.status_code == 200
        assert response.headers["X-Request-ID"] == client_request_id
    
    def test_request_id_with_different_uuid_formats(self, client_no_auth):
        """Test that various UUID formats are accepted."""
        test_ids = [
            str(uuid.uuid4()),  # Standard UUID
            str(uuid.uuid4()).upper(),  # Uppercase UUID
            str(uuid.uuid4()).replace("-", ""),  # UUID without dashes
        ]
        
        for request_id in test_ids:
            response = client_no_auth.get(
                "/health",
                headers={"X-Request-ID": request_id}
            )
            
            assert response.status_code == 200
            # Server should accept the ID (may normalize it)
            assert "X-Request-ID" in response.headers
    
    def test_request_id_alphanumeric_accepted(self, client_no_auth):
        """Test that alphanumeric request IDs are accepted."""
        request_id = "req-12345-abcdef"
        
        response = client_no_auth.get(
            "/health",
            headers={"X-Request-ID": request_id}
        )
        
        assert response.status_code == 200
        assert response.headers["X-Request-ID"] == request_id
    
    def test_request_id_with_special_chars_accepted(self, client_no_auth):
        """Test that request IDs with underscores and dots are accepted."""
        request_ids = [
            "req_123.456",
            "trace-id-with-dashes",
            "span.id.with.dots",
        ]
        
        for request_id in request_ids:
            response = client_no_auth.get(
                "/health",
                headers={"X-Request-ID": request_id}
            )
            
            assert response.status_code == 200
            assert response.headers["X-Request-ID"] == request_id


class TestRequestIDValidation:
    """Test cases for request ID validation and rejection."""
    
    def test_invalid_request_id_generates_new_one(self, client_no_auth):
        """Test that invalid request IDs cause server to generate new one."""
        invalid_ids = [
            "id with spaces",  # Spaces not allowed
            "id@with#special",  # Special chars not allowed
            "x" * 200,  # Too long
        ]
        
        for invalid_id in invalid_ids:
            response = client_no_auth.get(
                "/health",
                headers={"X-Request-ID": invalid_id}
            )
            
            assert response.status_code == 200
            returned_id = response.headers["X-Request-ID"]
            # Should have generated a new UUID, not echo the invalid one
            assert returned_id != invalid_id
            # Should be a valid UUID
            try:
                uuid.UUID(returned_id)
            except ValueError:
                pytest.fail(f"Server didn't generate valid UUID for invalid ID: {invalid_id}")
    
    def test_empty_request_id_generates_new_one(self, client_no_auth):
        """Test that empty request ID causes server to generate new one."""
        response = client_no_auth.get(
            "/health",
            headers={"X-Request-ID": ""}
        )
        
        assert response.status_code == 200
        request_id = response.headers["X-Request-ID"]
        # Should have generated a UUID
        try:
            uuid.UUID(request_id)
        except ValueError:
            pytest.fail(f"Server didn't generate valid UUID for empty ID")
    
    def test_whitespace_request_id_generates_new_one(self, client_no_auth):
        """Test that whitespace-only request ID causes server to generate new one."""
        response = client_no_auth.get(
            "/health",
            headers={"X-Request-ID": "   "}
        )
        
        assert response.status_code == 200
        request_id = response.headers["X-Request-ID"]
        # Should have generated a UUID
        try:
            uuid.UUID(request_id)
        except ValueError:
            pytest.fail(f"Server didn't generate valid UUID for whitespace ID")


class TestRequestIDOnWriteEndpoints:
    """Test request ID handling on write endpoints."""
    
    def test_request_id_on_post_plan(self, client_no_auth):
        """Test that POST /plan includes request ID in response."""
        response = client_no_auth.post(
            "/api/v1/plan",
            json={"description": "Build a REST API"}
        )
        
        assert response.status_code == 200
        assert "X-Request-ID" in response.headers
        
        # Should be a valid UUID
        request_id = response.headers["X-Request-ID"]
        try:
            uuid.UUID(request_id)
        except ValueError:
            pytest.fail(f"Invalid request ID on POST /plan: {request_id}")
    
    def test_request_id_on_post_plan_with_client_id(self, client_no_auth):
        """Test that POST /plan echoes client-provided request ID."""
        client_request_id = str(uuid.uuid4())
        
        response = client_no_auth.post(
            "/api/v1/plan",
            json={"description": "Build a REST API"},
            headers={"X-Request-ID": client_request_id}
        )
        
        assert response.status_code == 200
        assert response.headers["X-Request-ID"] == client_request_id
    
    def test_request_id_on_post_plans(self, client_no_auth):
        """Test that POST /plans includes request ID in response."""
        from app.services.job_store import JobStore
        from app.services.store_singleton import get_job_store
        
        # Override job store dependency
        test_app = client_no_auth.app
        mock_job_store = JobStore()
        test_app.dependency_overrides[get_job_store] = lambda: mock_job_store
        
        try:
            response = client_no_auth.post(
                "/api/v1/plans",
                json={"description": "Build a REST API"}
            )
            
            assert response.status_code == 202
            assert "X-Request-ID" in response.headers
            
            # Should be a valid UUID
            request_id = response.headers["X-Request-ID"]
            try:
                uuid.UUID(request_id)
            except ValueError:
                pytest.fail(f"Invalid request ID on POST /plans: {request_id}")
        finally:
            test_app.dependency_overrides.clear()
    
    def test_request_id_on_post_plans_with_client_id(self, client_no_auth):
        """Test that POST /plans echoes client-provided request ID."""
        from app.services.job_store import JobStore
        from app.services.store_singleton import get_job_store
        
        client_request_id = str(uuid.uuid4())
        
        # Override job store dependency
        test_app = client_no_auth.app
        mock_job_store = JobStore()
        test_app.dependency_overrides[get_job_store] = lambda: mock_job_store
        
        try:
            response = client_no_auth.post(
                "/api/v1/plans",
                json={"description": "Build a REST API"},
                headers={"X-Request-ID": client_request_id}
            )
            
            assert response.status_code == 202
            assert response.headers["X-Request-ID"] == client_request_id
        finally:
            test_app.dependency_overrides.clear()


class TestRequestIDOnErrorResponses:
    """Test that request ID is included in error responses."""
    
    def test_request_id_on_404_error(self, client_no_auth):
        """Test that 404 responses include request ID."""
        response = client_no_auth.get("/api/v1/nonexistent")
        
        assert response.status_code == 404
        assert "X-Request-ID" in response.headers
    
    def test_request_id_on_405_error(self, client_no_auth):
        """Test that 405 responses include request ID."""
        response = client_no_auth.post("/health")
        
        assert response.status_code == 405
        assert "X-Request-ID" in response.headers
    
    def test_request_id_on_validation_error(self, client_no_auth):
        """Test that 400/422 validation errors include request ID."""
        response = client_no_auth.post(
            "/api/v1/plan",
            json={"description": ""}  # Empty description
        )
        
        assert response.status_code == 400
        assert "X-Request-ID" in response.headers
    
    def test_request_id_on_malformed_json(self, client_no_auth):
        """Test that malformed JSON errors include request ID."""
        response = client_no_auth.post(
            "/api/v1/plan",
            content="not valid json",
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 422
        assert "X-Request-ID" in response.headers


class TestRequestIDHeaderCaseInsensitivity:
    """Test that request ID header name is case-insensitive."""
    
    def test_lowercase_header_name(self, client_no_auth):
        """Test that lowercase x-request-id header works."""
        client_request_id = str(uuid.uuid4())
        
        response = client_no_auth.get(
            "/health",
            headers={"x-request-id": client_request_id}
        )
        
        assert response.status_code == 200
        # Response should include the request ID
        assert "X-Request-ID" in response.headers
    
    def test_mixed_case_header_name(self, client_no_auth):
        """Test that mixed case X-Request-Id header works."""
        client_request_id = str(uuid.uuid4())
        
        response = client_no_auth.get(
            "/health",
            headers={"X-Request-Id": client_request_id}
        )
        
        assert response.status_code == 200
        assert "X-Request-ID" in response.headers
