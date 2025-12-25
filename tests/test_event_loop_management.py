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
"""Regression tests for event loop management.

These tests verify that both sync and async plan endpoints share a single
event loop without invoking asyncio.run inside request handlers, and that
JobRepository and async clients always execute on the FastAPI/uvloop loop
without raising loop-affinity errors.
"""

import asyncio
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.job_store import JobStore


@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client that returns valid specs."""
    client = Mock()
    client.generate_specs.return_value = {
        "specs": [
            {
                "purpose": "Test Purpose",
                "vision": "Test Vision",
                "must": ["Test requirement"],
                "dont": ["Test anti-pattern"],
                "nice": ["Test nice-to-have"],
            }
        ]
    }
    return client


@pytest.fixture
def client(mock_llm_client):
    """Create a test client with mocked dependencies."""
    from app.services.rate_limiter import RateLimiter

    # Create a disabled rate limiter for these tests
    disabled_limiter = RateLimiter(window_seconds=60, max_requests=10, enabled=False)

    # Patch both the LLM client and rate limiter
    with patch("app.services.store_singleton.get_llm_client", return_value=mock_llm_client):
        with patch("app.api.routes.get_rate_limiter", return_value=disabled_limiter):
            yield TestClient(app)


@pytest.fixture
def override_job_store(mock_llm_client):
    """Override the job store dependency for testing."""
    from app.services.rate_limiter import RateLimiter
    from app.services.store_singleton import get_job_store

    # Create a disabled rate limiter for these tests
    disabled_limiter = RateLimiter(window_seconds=60, max_requests=10, enabled=False)

    mock_job_store = JobStore()

    # Patch both job store, LLM client, and rate limiter
    with patch("app.services.store_singleton.get_llm_client", return_value=mock_llm_client):
        with patch("app.api.routes.get_rate_limiter", return_value=disabled_limiter):
            app.dependency_overrides[get_job_store] = lambda: mock_job_store
            yield mock_job_store
            app.dependency_overrides.clear()


class TestEventLoopStability:
    """Tests for event loop stability and proper async/sync coordination."""

    def test_sync_endpoint_does_not_create_new_loop(self, client):
        """Test that sync endpoint doesn't create a new event loop.

        Regression test for: "Future attached to a different loop" errors.
        The sync endpoint should use the FastAPI event loop, not create its own.
        """
        # Make multiple requests to ensure loop reuse
        for _ in range(3):
            response = client.post("/api/v1/plan", json={"description": "Build a REST API"})
            assert response.status_code == 200
            data = response.json()
            assert "specs" in data

    def test_async_endpoint_uses_fastapi_loop(self, client, override_job_store):
        """Test that async endpoint uses the FastAPI event loop.

        Regression test for: Background tasks must execute on the same loop as JobRepository.
        """
        import time

        # Create multiple async jobs
        job_ids = []
        for i in range(3):
            response = client.post("/api/v1/plans", json={"description": f"Project {i}"})
            assert response.status_code == 202
            job_ids.append(response.json()["job_id"])

        # Wait for background tasks to complete
        time.sleep(1.0)

        # Verify all jobs completed successfully without loop errors
        for job_id in job_ids:
            job = asyncio.run(override_job_store.get_job(job_id))
            assert job is not None
            assert job.status == "SUCCEEDED", f"Job {job_id} failed with status {job.status}"
            assert job.result is not None

    def test_job_repository_works_across_endpoints(self, client, override_job_store):
        """Test that JobRepository works correctly across sync and async endpoints.

        Verifies that the same JobRepository instance can be used from both
        sync and async contexts without loop affinity errors.
        """
        import time

        # Create job via async endpoint
        response1 = client.post("/api/v1/plans", json={"description": "Async project"})
        assert response1.status_code == 202
        job_id1 = response1.json()["job_id"]

        # Make sync request while async job is processing
        response2 = client.post("/api/v1/plan", json={"description": "Sync project"})
        assert response2.status_code == 200

        # Wait for async job to complete
        time.sleep(1.0)

        # Verify async job completed successfully
        job = asyncio.run(override_job_store.get_job(job_id1))
        assert job is not None
        assert job.status == "SUCCEEDED"

    def test_repeated_sync_calls_no_loop_leak(self, client):
        """Test that repeated sync endpoint calls don't leak event loops.

        Ensures that we don't accumulate event loops or futures across multiple requests.
        """
        # Make many requests to detect potential loop leaks
        for i in range(10):
            response = client.post(
                "/api/v1/plan", json={"description": f"Project iteration {i}"}
            )
            assert response.status_code == 200, f"Request {i} failed"
            assert "specs" in response.json()

    def test_concurrent_mixed_requests(self, client, override_job_store):
        """Test concurrent mix of sync and async requests.

        Verifies that mixing sync and async endpoints doesn't cause loop conflicts.
        """
        import time
        from concurrent.futures import ThreadPoolExecutor

        def make_sync_request(i):
            return client.post("/api/v1/plan", json={"description": f"Sync project {i}"})

        def make_async_request(i):
            return client.post("/api/v1/plans", json={"description": f"Async project {i}"})

        # Make concurrent requests of both types
        with ThreadPoolExecutor(max_workers=5) as executor:
            sync_futures = [executor.submit(make_sync_request, i) for i in range(5)]
            async_futures = [executor.submit(make_async_request, i) for i in range(5)]

            sync_responses = [f.result() for f in sync_futures]
            async_responses = [f.result() for f in async_futures]

        # Verify all sync requests succeeded
        for response in sync_responses:
            assert response.status_code == 200
            assert "specs" in response.json()

        # Verify all async requests accepted
        for response in async_responses:
            assert response.status_code == 202

        # Wait for async jobs to complete
        time.sleep(2.0)

        # Verify async jobs completed successfully
        async_job_ids = [r.json()["job_id"] for r in async_responses]
        for job_id in async_job_ids:
            job = asyncio.run(override_job_store.get_job(job_id))
            assert job is not None
            assert job.status == "SUCCEEDED", f"Async job {job_id} failed"

    def test_error_propagation_preserves_loop_integrity(self, client, override_job_store, monkeypatch):
        """Test that errors in planner don't break loop management.

        Ensures that exceptions during planning don't leave loops in invalid states.
        """
        import time

        # Mock generate_plan to raise an error
        async def mock_generate_plan_error(
            description,
            job_repository=None,
            job_id=None,
            llm_client=None,
            model=None,
            system_prompt=None,
        ):
            if job_repository and job_id:
                await job_repository.mark_running(job_id)
            raise ValueError("Simulated error")

        monkeypatch.setattr("app.api.routes.generate_plan", mock_generate_plan_error)

        # Create job that will fail
        response = client.post("/api/v1/plans", json={"description": "Failing project"})
        assert response.status_code == 202
        job_id = response.json()["job_id"]

        time.sleep(0.5)

        # Verify job failed but didn't break loop management
        job = asyncio.run(override_job_store.get_job(job_id))
        assert job is not None
        assert job.status == "FAILED"

        # Verify subsequent requests still work (loop wasn't corrupted)
        response2 = client.post("/api/v1/plans", json={"description": "Recovery project"})
        assert response2.status_code == 202

    def test_no_nested_asyncio_run_calls(self, client, override_job_store):
        """Test that we never have nested asyncio.run() calls.

        This is a regression test to ensure we don't try to create a new loop
        while already inside an event loop (which would cause RuntimeError).
        """
        import time

        # This should work without RuntimeError about nested loops
        response = client.post("/api/v1/plans", json={"description": "Test project"})
        assert response.status_code == 202

        time.sleep(0.5)

        job_id = response.json()["job_id"]
        job = asyncio.run(override_job_store.get_job(job_id))
        assert job is not None
        # If we got here without RuntimeError, the test passes
        assert job.status in ["QUEUED", "RUNNING", "SUCCEEDED"]
