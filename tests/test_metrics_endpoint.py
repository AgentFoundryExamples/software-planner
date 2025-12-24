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
"""Tests for metrics endpoint."""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.metrics import reset_metrics_collector


@pytest.fixture
def app_with_metrics():
    """Create app with metrics enabled."""
    import os
    from importlib import reload
    from app.core import config
    
    # Enable metrics for this test
    os.environ["PLANNER_METRICS_ENABLED"] = "true"
    
    # Reload config module to pick up environment variable
    reload(config)
    
    # Reset singleton to pick up new config
    reset_metrics_collector()
    
    app = create_app()
    yield app
    
    # Cleanup
    os.environ.pop("PLANNER_METRICS_ENABLED", None)
    reload(config)
    reset_metrics_collector()


@pytest.fixture
def app_without_metrics():
    """Create app with metrics disabled."""
    import os
    from importlib import reload
    from app.core import config
    
    # Ensure metrics are disabled
    os.environ.pop("PLANNER_METRICS_ENABLED", None)
    
    # Reload config module to pick up environment variable
    reload(config)
    
    # Reset singleton to pick up new config
    reset_metrics_collector()
    
    app = create_app()
    yield app
    
    # Cleanup
    reload(config)
    reset_metrics_collector()


def test_metrics_endpoint_enabled(app_with_metrics):
    """Test that metrics endpoint works when metrics are enabled."""
    client = TestClient(app_with_metrics)
    
    response = client.get("/api/v1/metrics")
    
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    
    # Check for Prometheus format
    content = response.text
    assert "# HELP" in content or "# TYPE" in content or "planner_" in content


def test_metrics_endpoint_disabled(app_without_metrics):
    """Test that metrics endpoint returns message when disabled."""
    client = TestClient(app_without_metrics)
    
    response = client.get("/api/v1/metrics")
    
    assert response.status_code == 200
    assert "Metrics collection is disabled" in response.text


def test_metrics_endpoint_collects_http_metrics(app_with_metrics):
    """Test that metrics endpoint includes HTTP metrics."""
    client = TestClient(app_with_metrics)
    
    # Make some requests to generate metrics
    client.get("/health")
    client.get("/api/v1/models")
    
    # Check metrics
    response = client.get("/api/v1/metrics")
    
    assert response.status_code == 200
    content = response.text
    
    # Should have HTTP metrics
    assert "planner_http_requests_total" in content
    assert "planner_http_request_duration_seconds" in content


def test_metrics_do_not_expose_secrets(app_with_metrics):
    """Test that metrics do not expose sensitive data."""
    client = TestClient(app_with_metrics)
    
    # Make some requests
    client.get("/health")
    
    # Get metrics
    response = client.get("/api/v1/metrics")
    
    content = response.text
    
    # Should NOT contain any secrets
    assert "sk-" not in content  # API key prefix
    assert "password" not in content.lower()
    assert "secret" not in content.lower()
    # Allow token in metric names (token_type, tokens_total) but not as standalone text
    assert " token " not in content.lower() and "token:" not in content.lower()
