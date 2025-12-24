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
"""Tests for CORS configuration and behavior."""

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
def client_with_specific_origins(mock_llm_client):
    """Create test client with specific allowed origins."""
    test_settings = Settings(
        planner_api_keys=[],
        planner_api_keys_required=False,
        allowed_origins=["https://example.com", "https://app.example.com"],
        cors_wildcard_enabled=False,
        allowed_credentials=False,
        allowed_methods=["GET", "POST"],
        allowed_headers=["Content-Type", "X-API-Key", "X-Request-ID"]
    )
    
    with patch('app.core.config.settings', test_settings):
        with patch('app.services.store_singleton.get_llm_client', return_value=mock_llm_client):
            app = get_app()
            yield TestClient(app)


@pytest.fixture
def client_with_wildcard_origins(mock_llm_client):
    """Create test client with wildcard CORS origins."""
    test_settings = Settings(
        planner_api_keys=[],
        planner_api_keys_required=False,
        allowed_origins=["*"],
        cors_wildcard_enabled=True,
        allowed_credentials=False
    )
    
    with patch('app.core.config.settings', test_settings):
        with patch('app.services.store_singleton.get_llm_client', return_value=mock_llm_client):
            app = get_app()
            yield TestClient(app)


class TestCORSAllowedOrigins:
    """Test CORS behavior with allowed origins."""
    
    def test_allowed_origin_in_response(self, client_with_specific_origins):
        """Test that allowed origin is reflected in CORS headers."""
        response = client_with_specific_origins.get(
            "/health",
            headers={"Origin": "https://example.com"}
        )
        
        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers
        assert response.headers["access-control-allow-origin"] == "https://example.com"
    
    def test_second_allowed_origin(self, client_with_specific_origins):
        """Test that second allowed origin works."""
        response = client_with_specific_origins.get(
            "/health",
            headers={"Origin": "https://app.example.com"}
        )
        
        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers
        assert response.headers["access-control-allow-origin"] == "https://app.example.com"
    
    def test_disallowed_origin_rejected(self, client_with_specific_origins):
        """Test that disallowed origin doesn't get CORS headers."""
        response = client_with_specific_origins.get(
            "/health",
            headers={"Origin": "https://evil.com"}
        )
        
        # Request should succeed but without CORS headers
        assert response.status_code == 200
        # CORS middleware won't add allow-origin for disallowed origins
        cors_origin = response.headers.get("access-control-allow-origin")
        # Either no header or it doesn't match the evil origin
        assert cors_origin != "https://evil.com"


class TestCORSPreflightRequests:
    """Test CORS preflight (OPTIONS) requests."""
    
    def test_preflight_for_allowed_origin(self, client_with_specific_origins):
        """Test OPTIONS preflight succeeds for allowed origin."""
        response = client_with_specific_origins.options(
            "/api/v1/plan",
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type,X-API-Key"
            }
        )
        
        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers
        assert response.headers["access-control-allow-origin"] == "https://example.com"
        assert "access-control-allow-methods" in response.headers
        assert "access-control-allow-headers" in response.headers
    
    def test_preflight_for_disallowed_origin(self, client_with_specific_origins):
        """Test OPTIONS preflight for disallowed origin."""
        response = client_with_specific_origins.options(
            "/api/v1/plan",
            headers={
                "Origin": "https://evil.com",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type"
            }
        )
        
        # FastAPI/Starlette returns 200 for OPTIONS but without CORS headers
        assert response.status_code == 200
        cors_origin = response.headers.get("access-control-allow-origin")
        assert cors_origin != "https://evil.com"


class TestCORSExposeHeaders:
    """Test that X-Request-ID is exposed via CORS."""
    
    def test_request_id_exposed_in_cors(self, client_with_specific_origins):
        """Test that X-Request-ID is in Access-Control-Expose-Headers."""
        response = client_with_specific_origins.get(
            "/health",
            headers={"Origin": "https://example.com"}
        )
        
        assert response.status_code == 200
        assert "access-control-expose-headers" in response.headers
        expose_headers = response.headers["access-control-expose-headers"].lower()
        assert "x-request-id" in expose_headers
    
    def test_request_id_accessible_from_browser(self, client_with_specific_origins):
        """Test that X-Request-ID header is present and exposed."""
        response = client_with_specific_origins.get(
            "/health",
            headers={"Origin": "https://example.com"}
        )
        
        assert response.status_code == 200
        # Request ID should be in response headers
        assert "X-Request-ID" in response.headers
        # And should be exposed via CORS
        assert "access-control-expose-headers" in response.headers


class TestCORSWildcardOrigins:
    """Test CORS behavior with wildcard origins."""
    
    def test_wildcard_allows_any_origin(self, client_with_wildcard_origins):
        """Test that wildcard origin allows any domain."""
        test_origins = [
            "https://example.com",
            "https://app.example.com",
            "http://localhost:3000",
            "https://random-domain.org"
        ]
        
        for origin in test_origins:
            response = client_with_wildcard_origins.get(
                "/health",
                headers={"Origin": origin}
            )
            
            assert response.status_code == 200
            assert "access-control-allow-origin" in response.headers
            # With wildcard, typically returns "*"
            cors_origin = response.headers["access-control-allow-origin"]
            assert cors_origin in ["*", origin]


class TestCORSWithoutOriginHeader:
    """Test behavior when Origin header is not present."""
    
    def test_request_without_origin_header(self, client_with_specific_origins):
        """Test that requests without Origin header work normally."""
        response = client_with_specific_origins.get("/health")
        
        # Should succeed - CORS only applies to cross-origin requests
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
    
    def test_post_without_origin_header(self, client_with_specific_origins):
        """Test that POST requests without Origin header work (still need auth if configured)."""
        response = client_with_specific_origins.post(
            "/api/v1/plan",
            json={"description": "Build a REST API"}
        )
        
        # Should succeed (no auth configured in this fixture)
        assert response.status_code == 200
        data = response.json()
        assert "specs" in data


class TestCORSMethodRestrictions:
    """Test CORS method restrictions."""
    
    def test_allowed_methods_in_preflight(self, client_with_specific_origins):
        """Test that allowed methods are reflected in preflight response."""
        response = client_with_specific_origins.options(
            "/api/v1/plan",
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "POST"
            }
        )
        
        assert response.status_code == 200
        assert "access-control-allow-methods" in response.headers
        allowed_methods = response.headers["access-control-allow-methods"].upper()
        assert "POST" in allowed_methods
        assert "GET" in allowed_methods


class TestCORSWithAuthentication:
    """Test CORS behavior combined with authentication."""
    
    @pytest.fixture
    def client_with_cors_and_auth(self, mock_llm_client):
        """Create test client with both CORS and authentication."""
        test_settings = Settings(
            planner_api_keys=["test-key-1"],
            planner_api_keys_required=True,
            allowed_origins=["https://example.com"],
            cors_wildcard_enabled=False
        )
        
        with patch('app.core.config.settings', test_settings):
            with patch('app.services.store_singleton.get_llm_client', return_value=mock_llm_client):
                app = get_app()
                yield TestClient(app)
    
    def test_preflight_does_not_require_auth(self, client_with_cors_and_auth):
        """Test that OPTIONS preflight doesn't require API key."""
        response = client_with_cors_and_auth.options(
            "/api/v1/plan",
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type,X-API-Key"
            }
        )
        
        # Preflight should succeed without API key
        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers
    
    def test_actual_request_requires_auth(self, client_with_cors_and_auth):
        """Test that actual POST request requires API key even with valid origin."""
        response = client_with_cors_and_auth.post(
            "/api/v1/plan",
            json={"description": "Build a REST API"},
            headers={"Origin": "https://example.com"}
        )
        
        # Should fail with 401 - missing API key
        assert response.status_code == 401
    
    def test_request_with_auth_and_cors(self, client_with_cors_and_auth):
        """Test that request with both auth and CORS succeeds."""
        response = client_with_cors_and_auth.post(
            "/api/v1/plan",
            json={"description": "Build a REST API"},
            headers={
                "Origin": "https://example.com",
                "X-API-Key": "test-key-1"
            }
        )
        
        # Should succeed with both valid origin and API key
        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers
        assert response.headers["access-control-allow-origin"] == "https://example.com"


class TestCORSHeaderConfiguration:
    """Test CORS header configuration."""
    
    def test_allowed_headers_reflected(self, client_with_specific_origins):
        """Test that allowed headers are reflected in preflight."""
        response = client_with_specific_origins.options(
            "/api/v1/plan",
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "X-API-Key"
            }
        )
        
        assert response.status_code == 200
        assert "access-control-allow-headers" in response.headers
        allowed_headers = response.headers["access-control-allow-headers"].lower()
        assert "x-api-key" in allowed_headers or "content-type" in allowed_headers
