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
"""Tests for API key authentication."""

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
def client_with_api_keys(mock_llm_client):
    """Create test client with API keys configured."""
    test_settings = Settings(
        planner_api_keys=["test-key-1234567890", "test-key-0987654321"],
        planner_api_keys_required=True,
        planner_api_key_min_length=16,
        allowed_origins=["*"],
        cors_wildcard_enabled=True
    )
    
    with patch('app.core.config.settings', test_settings):
        with patch('app.api.dependencies.settings', test_settings):
            with patch('app.services.store_singleton.get_llm_client', return_value=mock_llm_client):
                app = get_app()
                yield TestClient(app)


@pytest.fixture
def client_without_api_keys(mock_llm_client):
    """Create test client without API keys configured."""
    test_settings = Settings(
        planner_api_keys=[],
        planner_api_keys_required=False,
        allowed_origins=["*"],
        cors_wildcard_enabled=True
    )
    
    with patch('app.core.config.settings', test_settings):
        with patch('app.api.dependencies.settings', test_settings):
            with patch('app.services.store_singleton.get_llm_client', return_value=mock_llm_client):
                app = get_app()
                yield TestClient(app)


class TestAPIKeyAuthentication:
    """Test cases for API key authentication."""
    
    def test_post_plan_with_valid_api_key(self, client_with_api_keys):
        """Test that POST /plan succeeds with valid API key."""
        response = client_with_api_keys.post(
            "/api/v1/plan",
            json={"description": "Build a REST API"},
            headers={"X-API-Key": "test-key-1234567890"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "specs" in data
    
    def test_post_plan_with_second_valid_api_key(self, client_with_api_keys):
        """Test that POST /plan succeeds with second configured API key."""
        response = client_with_api_keys.post(
            "/api/v1/plan",
            json={"description": "Build a REST API"},
            headers={"X-API-Key": "test-key-0987654321"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "specs" in data
    
    def test_post_plan_without_api_key(self, client_with_api_keys):
        """Test that POST /plan returns 401 when API key is missing."""
        response = client_with_api_keys.post(
            "/api/v1/plan",
            json={"description": "Build a REST API"}
        )
        
        assert response.status_code == 401
        data = response.json()
        assert "error" in data or "detail" in data
        assert data.get("detail") == "Missing X-API-Key header" or "Missing" in str(data)
    
    def test_post_plan_with_invalid_api_key(self, client_with_api_keys):
        """Test that POST /plan returns 403 with invalid API key."""
        response = client_with_api_keys.post(
            "/api/v1/plan",
            json={"description": "Build a REST API"},
            headers={"X-API-Key": "invalid-key"}
        )
        
        assert response.status_code == 403
        data = response.json()
        assert "error" in data or "detail" in data
        assert data.get("detail") == "Invalid API key" or "Invalid" in str(data)
    
    def test_post_plan_with_empty_api_key(self, client_with_api_keys):
        """Test that POST /plan returns 403 with empty API key."""
        response = client_with_api_keys.post(
            "/api/v1/plan",
            json={"description": "Build a REST API"},
            headers={"X-API-Key": ""}
        )
        
        # Empty string is passed to validation, so returns 403 not 401
        assert response.status_code == 403
        data = response.json()
        assert "error" in data or "detail" in data
    
    def test_post_plan_with_whitespace_api_key(self, client_with_api_keys):
        """Test that POST /plan returns 403 with whitespace-only API key."""
        response = client_with_api_keys.post(
            "/api/v1/plan",
            json={"description": "Build a REST API"},
            headers={"X-API-Key": "   "}
        )
        
        assert response.status_code == 403
        data = response.json()
        assert "error" in data or "detail" in data


class TestAPIKeyAuthenticationAsync:
    """Test cases for API key authentication on async endpoint."""
    
    def test_post_plans_with_valid_api_key(self, client_with_api_keys):
        """Test that POST /plans succeeds with valid API key."""
        from app.services.job_store import JobStore
        from app.services.store_singleton import get_job_store
        
        # Get the app and override the job store dependency
        test_app = client_with_api_keys.app
        mock_job_store = JobStore()
        test_app.dependency_overrides[get_job_store] = lambda: mock_job_store
        
        try:
            response = client_with_api_keys.post(
                "/api/v1/plans",
                json={"description": "Build a REST API"},
                headers={"X-API-Key": "test-key-1234567890"}
            )
            
            assert response.status_code == 202
            data = response.json()
            assert "job_id" in data
            assert data["status"] == "QUEUED"
        finally:
            test_app.dependency_overrides.clear()
    
    def test_post_plans_without_api_key(self, client_with_api_keys):
        """Test that POST /plans returns 401 when API key is missing."""
        response = client_with_api_keys.post(
            "/api/v1/plans",
            json={"description": "Build a REST API"}
        )
        
        assert response.status_code == 401
        data = response.json()
        assert "error" in data or "detail" in data
    
    def test_post_plans_with_invalid_api_key(self, client_with_api_keys):
        """Test that POST /plans returns 403 with invalid API key."""
        response = client_with_api_keys.post(
            "/api/v1/plans",
            json={"description": "Build a REST API"},
            headers={"X-API-Key": "wrong-key"}
        )
        
        assert response.status_code == 403
        data = response.json()
        assert "error" in data or "detail" in data


class TestAuthenticationBackwardCompatibility:
    """Test backward compatibility when no API keys are configured."""
    
    def test_post_plan_without_configured_keys(self, client_without_api_keys):
        """Test that POST /plan works when no API keys are configured."""
        response = client_without_api_keys.post(
            "/api/v1/plan",
            json={"description": "Build a REST API"}
        )
        
        # Should succeed without authentication when no keys configured
        assert response.status_code == 200
        data = response.json()
        assert "specs" in data
    
    def test_post_plan_with_key_when_none_configured(self, client_without_api_keys):
        """Test that POST /plan ignores API key when none are configured."""
        response = client_without_api_keys.post(
            "/api/v1/plan",
            json={"description": "Build a REST API"},
            headers={"X-API-Key": "any-key"}
        )
        
        # Should succeed - authentication is bypassed when no keys configured
        assert response.status_code == 200
        data = response.json()
        assert "specs" in data


class TestAPIKeyHeaderHandling:
    """Test edge cases for API key header handling."""
    
    def test_api_key_with_leading_trailing_spaces(self, client_with_api_keys):
        """Test that API keys with leading/trailing spaces are handled correctly."""
        response = client_with_api_keys.post(
            "/api/v1/plan",
            json={"description": "Build a REST API"},
            headers={"X-API-Key": "  test-key-1234567890  "}
        )
        
        # Should succeed - spaces should be stripped
        assert response.status_code == 200
        data = response.json()
        assert "specs" in data
    
    def test_api_key_case_sensitivity(self, client_with_api_keys):
        """Test that API keys are case-sensitive."""
        response = client_with_api_keys.post(
            "/api/v1/plan",
            json={"description": "Build a REST API"},
            headers={"X-API-Key": "TEST-KEY-1234567890"}  # Wrong case
        )
        
        # Should fail - keys are case-sensitive
        assert response.status_code == 403
        data = response.json()
        assert "error" in data or "detail" in data
    
    def test_header_name_case_insensitivity(self, client_with_api_keys):
        """Test that header name is case-insensitive (HTTP standard)."""
        response = client_with_api_keys.post(
            "/api/v1/plan",
            json={"description": "Build a REST API"},
            headers={"x-api-key": "test-key-1234567890"}  # Lowercase header name
        )
        
        # Should succeed - HTTP headers are case-insensitive
        assert response.status_code == 200
        data = response.json()
        assert "specs" in data
    
    def test_header_name_mixed_case(self, client_with_api_keys):
        """Test that header name with mixed case works."""
        response = client_with_api_keys.post(
            "/api/v1/plan",
            json={"description": "Build a REST API"},
            headers={"X-Api-Key": "test-key-1234567890"}  # Mixed case
        )
        
        # Should succeed - HTTP headers are case-insensitive
        assert response.status_code == 200
        data = response.json()
        assert "specs" in data


class TestReadEndpointsNoAuth:
    """Test that read endpoints don't require authentication."""
    
    def test_get_models_no_auth_required(self, client_with_api_keys):
        """Test that GET /models doesn't require authentication."""
        response = client_with_api_keys.get("/api/v1/models")
        
        # Should succeed without authentication
        assert response.status_code == 200
    
    def test_get_health_no_auth_required(self, client_with_api_keys):
        """Test that GET /health doesn't require authentication."""
        response = client_with_api_keys.get("/health")
        
        # Should succeed without authentication
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
