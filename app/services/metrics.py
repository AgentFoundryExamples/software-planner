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
"""Metrics collection and exposition for observability.

This module provides Prometheus-compatible metrics for tracking:
- HTTP request totals by endpoint and status code
- Job lifecycle transitions (queued, running, succeeded, failed)
- LLM call latency and failures by provider/model

Metrics are disabled by default and must be enabled via config.
"""

import logging
from typing import Optional
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry, generate_latest, CONTENT_TYPE_LATEST

logger = logging.getLogger(__name__)


class MetricsCollector:
    """Centralized metrics collector using Prometheus client library.
    
    This class manages all application metrics and provides a clean interface
    for incrementing counters, recording histograms, and generating reports.
    
    Metrics are organized by category:
    - HTTP: Request counts and durations by endpoint/status
    - Jobs: Status transition counts and processing duration
    - LLM: API call latency, token usage, and error rates
    
    All metrics are disabled by default and can be toggled via the enabled flag.
    When disabled, all metric operations become no-ops for zero overhead.
    """
    
    def __init__(self, enabled: bool = False, registry: Optional[CollectorRegistry] = None):
        """Initialize metrics collector.
        
        Args:
            enabled: Whether metrics collection is enabled. Defaults to False.
            registry: Optional custom registry for testing. Defaults to global registry.
        """
        self.enabled = enabled
        self.registry = registry if registry is not None else CollectorRegistry()
        
        # Initialize metrics only if enabled
        if self.enabled:
            self._init_http_metrics()
            self._init_job_metrics()
            self._init_llm_metrics()
            logger.info("Metrics collection enabled")
        else:
            logger.info("Metrics collection disabled")
    
    def _init_http_metrics(self):
        """Initialize HTTP request metrics."""
        self.http_requests_total = Counter(
            'planner_http_requests_total',
            'Total HTTP requests by endpoint and status',
            ['endpoint', 'status', 'method'],
            registry=self.registry
        )
        
        self.http_request_duration_seconds = Histogram(
            'planner_http_request_duration_seconds',
            'HTTP request duration in seconds',
            ['endpoint', 'method'],
            registry=self.registry,
            buckets=(0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0)
        )
    
    def _init_job_metrics(self):
        """Initialize job lifecycle metrics."""
        self.job_status_total = Counter(
            'planner_job_status_total',
            'Total jobs by status transition',
            ['status'],
            registry=self.registry
        )
        
        self.job_duration_seconds = Histogram(
            'planner_job_duration_seconds',
            'Job processing duration in seconds',
            ['status'],
            registry=self.registry,
            buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0)
        )
        
        self.jobs_in_progress = Gauge(
            'planner_jobs_in_progress',
            'Number of jobs currently in progress',
            registry=self.registry
        )
    
    def _init_llm_metrics(self):
        """Initialize LLM client metrics."""
        self.llm_requests_total = Counter(
            'planner_llm_requests_total',
            'Total LLM API requests by provider, model, and status',
            ['provider', 'model', 'status'],
            registry=self.registry
        )
        
        self.llm_request_duration_seconds = Histogram(
            'planner_llm_request_duration_seconds',
            'LLM API request duration in seconds',
            ['provider', 'model'],
            registry=self.registry,
            buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0)
        )
        
        self.llm_tokens_total = Counter(
            'planner_llm_tokens_total',
            'Total tokens consumed by LLM requests',
            ['provider', 'model', 'token_type'],
            registry=self.registry
        )
    
    # HTTP metrics methods
    
    def record_http_request(self, endpoint: str, method: str, status: int, duration: float):
        """Record an HTTP request with status and duration.
        
        Args:
            endpoint: API endpoint path (e.g., '/api/v1/plans')
            method: HTTP method (e.g., 'GET', 'POST')
            status: HTTP status code (e.g., 200, 404, 500)
            duration: Request duration in seconds
        """
        if not self.enabled:
            return
        
        self.http_requests_total.labels(
            endpoint=endpoint,
            status=str(status),
            method=method
        ).inc()
        
        self.http_request_duration_seconds.labels(
            endpoint=endpoint,
            method=method
        ).observe(duration)
    
    # Job metrics methods
    
    def record_job_status(self, status: str):
        """Record a job status transition.
        
        Args:
            status: Job status (QUEUED, RUNNING, SUCCEEDED, FAILED)
        """
        if not self.enabled:
            return
        
        self.job_status_total.labels(status=status).inc()
    
    def record_job_duration(self, status: str, duration: float):
        """Record job processing duration.
        
        Args:
            status: Final job status (SUCCEEDED or FAILED)
            duration: Processing duration in seconds
        """
        if not self.enabled:
            return
        
        self.job_duration_seconds.labels(status=status).observe(duration)
    
    def increment_jobs_in_progress(self):
        """Increment the gauge for jobs currently processing."""
        if not self.enabled:
            return
        
        self.jobs_in_progress.inc()
    
    def decrement_jobs_in_progress(self):
        """Decrement the gauge for jobs currently processing."""
        if not self.enabled:
            return
        
        self.jobs_in_progress.dec()
    
    # LLM metrics methods
    
    def record_llm_request(
        self,
        provider: str,
        model: str,
        status: str,
        duration: float,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None
    ):
        """Record an LLM API request with latency and token usage.
        
        Args:
            provider: LLM provider (openai, anthropic, google)
            model: Model identifier
            status: Request status (success, error, timeout)
            duration: Request duration in seconds
            prompt_tokens: Optional number of tokens in prompt
            completion_tokens: Optional number of tokens in completion
        """
        if not self.enabled:
            return
        
        self.llm_requests_total.labels(
            provider=provider,
            model=model,
            status=status
        ).inc()
        
        self.llm_request_duration_seconds.labels(
            provider=provider,
            model=model
        ).observe(duration)
        
        # Record token usage if available
        if prompt_tokens is not None:
            self.llm_tokens_total.labels(
                provider=provider,
                model=model,
                token_type='prompt'
            ).inc(prompt_tokens)
        
        if completion_tokens is not None:
            self.llm_tokens_total.labels(
                provider=provider,
                model=model,
                token_type='completion'
            ).inc(completion_tokens)
    
    # Metrics exposition
    
    def generate_metrics(self) -> bytes:
        """Generate Prometheus-formatted metrics output.
        
        Returns:
            Bytes containing Prometheus-formatted metrics data.
        """
        if not self.enabled:
            return b"# Metrics collection is disabled\n"
        
        return generate_latest(self.registry)
    
    def get_content_type(self) -> str:
        """Get the content type for metrics output.
        
        Returns:
            Content type string for Prometheus metrics.
        """
        return CONTENT_TYPE_LATEST


# Global singleton instance
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """Get or create the global metrics collector instance.
    
    Returns:
        MetricsCollector singleton instance.
    """
    global _metrics_collector
    
    if _metrics_collector is None:
        # Import here to avoid circular dependency
        from app.core.config import settings
        _metrics_collector = MetricsCollector(enabled=settings.planner_metrics_enabled)
    
    return _metrics_collector


def reset_metrics_collector():
    """Reset the global metrics collector.
    
    This is primarily used for testing to ensure clean state between tests.
    """
    global _metrics_collector
    _metrics_collector = None
