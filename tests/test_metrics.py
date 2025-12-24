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
"""Tests for metrics collection service."""

import pytest
from prometheus_client import CollectorRegistry

from app.services.metrics import MetricsCollector, reset_metrics_collector


class TestMetricsCollector:
    """Tests for MetricsCollector class."""
    
    def test_metrics_disabled_by_default(self):
        """Test that metrics are disabled by default."""
        metrics = MetricsCollector(enabled=False)
        
        assert not metrics.enabled
        
        # Operations should be no-ops
        metrics.record_http_request("/test", "GET", 200, 1.0)
        metrics.record_job_status("QUEUED")
        metrics.record_llm_request("openai", "gpt-4", "success", 2.5)
        
        # Should not raise any errors
    
    def test_metrics_enabled(self):
        """Test that metrics can be enabled."""
        registry = CollectorRegistry()
        metrics = MetricsCollector(enabled=True, registry=registry)
        
        assert metrics.enabled
        assert metrics.http_requests_total is not None
        assert metrics.job_status_total is not None
        assert metrics.llm_requests_total is not None
    
    def test_record_http_request(self):
        """Test recording HTTP request metrics."""
        registry = CollectorRegistry()
        metrics = MetricsCollector(enabled=True, registry=registry)
        
        # Record some requests
        metrics.record_http_request("/api/v1/plans", "POST", 202, 0.5)
        metrics.record_http_request("/api/v1/plans", "POST", 202, 0.6)
        metrics.record_http_request("/api/v1/plans", "GET", 200, 0.1)
        
        # Get metrics output
        output = metrics.generate_metrics().decode('utf-8')
        
        # Verify counter was incremented
        assert 'planner_http_requests_total' in output
        assert 'endpoint="/api/v1/plans"' in output
        assert 'method="POST"' in output
        assert 'status="202"' in output
    
    def test_record_job_status(self):
        """Test recording job status transitions."""
        registry = CollectorRegistry()
        metrics = MetricsCollector(enabled=True, registry=registry)
        
        # Record job transitions
        metrics.record_job_status("QUEUED")
        metrics.record_job_status("RUNNING")
        metrics.record_job_status("SUCCEEDED")
        metrics.record_job_status("FAILED")
        
        # Get metrics output
        output = metrics.generate_metrics().decode('utf-8')
        
        # Verify counters
        assert 'planner_job_status_total{status="QUEUED"}' in output
        assert 'planner_job_status_total{status="RUNNING"}' in output
        assert 'planner_job_status_total{status="SUCCEEDED"}' in output
        assert 'planner_job_status_total{status="FAILED"}' in output
    
    def test_record_job_duration(self):
        """Test recording job processing duration."""
        registry = CollectorRegistry()
        metrics = MetricsCollector(enabled=True, registry=registry)
        
        # Record durations
        metrics.record_job_duration("SUCCEEDED", 5.5)
        metrics.record_job_duration("FAILED", 2.3)
        
        # Get metrics output
        output = metrics.generate_metrics().decode('utf-8')
        
        # Verify histogram exists
        assert 'planner_job_duration_seconds' in output
        assert 'status="SUCCEEDED"' in output
        assert 'status="FAILED"' in output
    
    def test_jobs_in_progress_gauge(self):
        """Test jobs in progress gauge."""
        registry = CollectorRegistry()
        metrics = MetricsCollector(enabled=True, registry=registry)
        
        # Increment and decrement
        metrics.increment_jobs_in_progress()
        metrics.increment_jobs_in_progress()
        metrics.decrement_jobs_in_progress()
        
        # Get metrics output
        output = metrics.generate_metrics().decode('utf-8')
        
        # Verify gauge
        assert 'planner_jobs_in_progress' in output
    
    def test_record_llm_request(self):
        """Test recording LLM request metrics."""
        registry = CollectorRegistry()
        metrics = MetricsCollector(enabled=True, registry=registry)
        
        # Record LLM requests
        metrics.record_llm_request(
            provider="openai",
            model="gpt-4",
            status="success",
            duration=3.5,
            prompt_tokens=100,
            completion_tokens=150
        )
        metrics.record_llm_request(
            provider="anthropic",
            model="claude-sonnet-4.5",
            status="error",
            duration=1.2
        )
        
        # Get metrics output
        output = metrics.generate_metrics().decode('utf-8')
        
        # Verify LLM metrics
        assert 'planner_llm_requests_total' in output
        assert 'provider="openai"' in output
        assert 'model="gpt-4"' in output
        assert 'status="success"' in output
        assert 'provider="anthropic"' in output
        assert 'status="error"' in output
        
        # Verify token metrics
        assert 'planner_llm_tokens_total' in output
        assert 'token_type="prompt"' in output
        assert 'token_type="completion"' in output
    
    def test_metrics_disabled_returns_message(self):
        """Test that disabled metrics return a message."""
        metrics = MetricsCollector(enabled=False)
        
        output = metrics.generate_metrics().decode('utf-8')
        
        assert "Metrics collection is disabled" in output
    
    def test_content_type(self):
        """Test that correct content type is returned."""
        metrics = MetricsCollector(enabled=True)
        
        content_type = metrics.get_content_type()
        
        assert "text/plain" in content_type


class TestMetricsGlobal:
    """Tests for global metrics singleton."""
    
    def setup_method(self):
        """Reset metrics before each test."""
        reset_metrics_collector()
    
    def teardown_method(self):
        """Reset metrics after each test."""
        reset_metrics_collector()
    
    def test_get_metrics_collector_singleton(self):
        """Test that get_metrics_collector returns singleton."""
        from app.services.metrics import get_metrics_collector
        
        metrics1 = get_metrics_collector()
        metrics2 = get_metrics_collector()
        
        assert metrics1 is metrics2
    
    def test_reset_metrics_collector(self):
        """Test that reset_metrics_collector works."""
        from app.services.metrics import get_metrics_collector
        
        metrics1 = get_metrics_collector()
        reset_metrics_collector()
        metrics2 = get_metrics_collector()
        
        assert metrics1 is not metrics2
