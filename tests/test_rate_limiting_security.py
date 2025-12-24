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
"""Tests for security aspects of rate limiting and IP extraction."""

from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.rate_limiter import RateLimiter
from app.api.dependencies import get_client_ip


class TestClientIPExtraction:
    """Test cases for secure client IP extraction."""
    
    def test_default_ignores_proxy_headers(self):
        """Test that proxy headers are ignored by default for security."""
        # Create a mock request with spoofed proxy headers
        request = Mock()
        request.headers = {
            "X-Forwarded-For": "1.2.3.4, 5.6.7.8",
            "X-Real-IP": "9.10.11.12"
        }
        request.client = Mock()
        request.client.host = "192.168.1.100"
        
        # Mock settings with default (proxy headers not trusted)
        with patch('app.api.dependencies.settings') as mock_settings:
            mock_settings.planner_trust_proxy_headers = False
            
            ip = get_client_ip(request)
            
            # Should use direct connection IP, ignoring spoofed headers
            assert ip == "192.168.1.100"
    
    def test_trusted_proxy_uses_rightmost_ip(self):
        """Test that when proxies are trusted, rightmost IP is used."""
        request = Mock()
        request.headers = {
            "X-Forwarded-For": "1.2.3.4, 5.6.7.8, 9.10.11.12"
        }
        request.client = Mock()
        request.client.host = "192.168.1.100"
        
        # Mock settings with proxy headers trusted
        with patch('app.api.dependencies.settings') as mock_settings:
            mock_settings.planner_trust_proxy_headers = True
            
            ip = get_client_ip(request)
            
            # Should use rightmost IP (closest to us) from X-Forwarded-For
            assert ip == "9.10.11.12"
    
    def test_trusted_proxy_fallback_to_x_real_ip(self):
        """Test X-Real-IP is used when X-Forwarded-For is absent."""
        request = Mock()
        request.headers = {
            "X-Real-IP": "1.2.3.4"
        }
        request.client = Mock()
        request.client.host = "192.168.1.100"
        
        with patch('app.api.dependencies.settings') as mock_settings:
            mock_settings.planner_trust_proxy_headers = True
            
            ip = get_client_ip(request)
            
            assert ip == "1.2.3.4"
    
    def test_always_fallback_to_direct_connection(self):
        """Test direct connection is always used when proxy headers absent."""
        request = Mock()
        request.headers = {}
        request.client = Mock()
        request.client.host = "192.168.1.100"
        
        # Should work regardless of proxy trust setting
        with patch('app.api.dependencies.settings') as mock_settings:
            mock_settings.planner_trust_proxy_headers = False
            assert get_client_ip(request) == "192.168.1.100"
            
            mock_settings.planner_trust_proxy_headers = True
            assert get_client_ip(request) == "192.168.1.100"


class TestEmptyAPIKeyHandling:
    """Test cases for proper empty/whitespace API key handling."""
    
    @pytest.fixture
    def mock_llm_client(self):
        """Create a mock LLM client."""
        client = Mock()
        client.generate_specs.return_value = {
            "specs": [{"purpose": "Test", "vision": "Test", "must": [], "dont": [], "nice": []}]
        }
        return client
    
    @pytest.fixture
    def client_with_rate_limiter(self, mock_llm_client):
        """Create test client with rate limiter."""
        limiter = RateLimiter(window_seconds=60, max_requests=2, enabled=True)
        
        from app.services.job_repository import JobRepository
        from app.models.job import Job
        
        mock_job_repo = Mock(spec=JobRepository)
        mock_job = Mock(spec=Job)
        mock_job.job_id = "test-job"
        mock_job.status = "QUEUED"
        mock_job_repo.create_job.return_value = mock_job
        
        with patch('app.services.store_singleton.get_llm_client', return_value=mock_llm_client):
            with patch('app.api.routes.get_rate_limiter', return_value=limiter):
                with patch('app.api.routes.get_job_store', return_value=mock_job_repo):
                    with patch('app.api.dependencies.settings') as mock_settings:
                        mock_settings.planner_api_keys = ["valid-key"]
                        mock_settings.is_api_key_valid.return_value = True
                        mock_settings.planner_trust_proxy_headers = False
                        yield TestClient(app), limiter
    
    def test_empty_string_api_key_uses_ip_limiting(self, client_with_rate_limiter):
        """Test that empty string API key falls back to IP-based limiting."""
        client, limiter = client_with_rate_limiter
        
        # Make requests with empty string API key
        # They should all be rate limited together based on IP, not per-key
        for i in range(2):
            response = client.post(
                "/api/v1/plan",
                json={"description": f"Test {i}"},
                headers={"X-API-Key": ""}  # Empty string
            )
            assert response.status_code == 200, f"Request {i} failed"
        
        # 3rd request should be rate limited (using IP-based limiting)
        response = client.post(
            "/api/v1/plan",
            json={"description": "Test 3"},
            headers={"X-API-Key": ""}  # Empty string
        )
        assert response.status_code == 429
    
    def test_whitespace_api_key_uses_ip_limiting(self, client_with_rate_limiter):
        """Test that whitespace-only API key falls back to IP-based limiting."""
        client, limiter = client_with_rate_limiter
        
        # Make requests with whitespace API key
        for i in range(2):
            response = client.post(
                "/api/v1/plan",
                json={"description": f"Test {i}"},
                headers={"X-API-Key": "   "}  # Whitespace only
            )
            assert response.status_code == 200, f"Request {i} failed"
        
        # 3rd request should be rate limited
        response = client.post(
            "/api/v1/plan",
            json={"description": "Test 3"},
            headers={"X-API-Key": "   "}
        )
        assert response.status_code == 429


class TestRaceconditionProtection:
    """Test cases for thread safety in bucket creation."""
    
    def test_concurrent_bucket_creation_is_safe(self):
        """Test that concurrent requests creating buckets don't cause race conditions."""
        import threading
        limiter = RateLimiter(window_seconds=60, max_requests=10, enabled=True)
        
        results = []
        errors = []
        lock = threading.Lock()
        
        def make_requests(thread_id):
            try:
                for i in range(5):
                    allowed, _ = limiter.check_rate_limit(
                        api_key=f"thread-{thread_id}-key",
                        request_id=f"req-{thread_id}-{i}"
                    )
                    with lock:
                        results.append((thread_id, i, allowed))
            except Exception as e:
                with lock:
                    errors.append((thread_id, str(e)))
        
        # Create multiple threads making concurrent requests
        threads = []
        for i in range(10):
            thread = threading.Thread(target=make_requests, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # Should have no errors
        assert len(errors) == 0, f"Errors occurred: {errors}"
        
        # Should have 50 results (10 threads * 5 requests each)
        assert len(results) == 50
        
        # All requests should be allowed (each thread has separate key)
        assert all(allowed for _, _, allowed in results)
