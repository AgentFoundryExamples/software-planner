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
"""Tests for the GET /plans and GET /plans/{job_id} polling endpoints."""

import asyncio
import time
from datetime import datetime, timezone
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
                "purpose": "Core API Development",
                "vision": "Build a robust and scalable REST API",
                "must": ["Implement RESTful endpoints", "Add validation"],
                "dont": ["Skip validation", "Expose errors"],
                "nice": ["Add rate limiting", "Include logging"],
            }
        ]
    }
    return client


@pytest.fixture
def client(mock_llm_client):
    """Create a test client for the FastAPI app with mocked LLM client."""
    # Patch the get_llm_client at the source to return our mock
    with patch("app.services.store_singleton.get_llm_client", return_value=mock_llm_client):
        yield TestClient(app)


@pytest.fixture
def mock_job_store():
    """Create a mock job store for testing."""
    return JobStore()


@pytest.fixture
def override_job_store(mock_job_store, mock_llm_client):
    """Override the job store dependency for testing."""
    from app.services.store_singleton import get_job_store

    # Patch both job store and LLM client
    with patch("app.services.store_singleton.get_llm_client", return_value=mock_llm_client):
        app.dependency_overrides[get_job_store] = lambda: mock_job_store
        yield mock_job_store
        app.dependency_overrides.clear()


class TestGetJobStatusEndpoint:
    """Test cases for GET /plans/{job_id} endpoint."""

    def test_get_pending_job(self, client, override_job_store):
        """Test getting status of a pending job."""
        # Create a pending job
        job = asyncio.run(override_job_store.create_job(description="Test description"))

        response = client.get(f"/api/v1/plans/{job.job_id}")

        assert response.status_code == 200
        data = response.json()

        assert data["job_id"] == job.job_id
        assert data["status"] == "QUEUED"
        assert "created_at" in data
        assert "updated_at" in data
        assert data["result"] is None
        assert "error" not in data

    def test_get_succeeded_job(self, client, override_job_store):
        """Test getting status of a succeeded job with result."""
        # Create a job and update it to succeeded status with result
        job = asyncio.run(override_job_store.create_job(description="Test description"))
        result = {
            "specs": [
                {
                    "purpose": "Test Purpose",
                    "vision": "Test Vision",
                    "must": ["Requirement 1"],
                    "dont": ["Avoid 1"],
                    "nice": ["Nice to have 1"],
                }
            ]
        }
        asyncio.run(override_job_store.mark_succeeded(job.job_id, result))

        response = client.get(f"/api/v1/plans/{job.job_id}")

        assert response.status_code == 200
        data = response.json()

        assert data["job_id"] == job.job_id
        assert data["status"] == "SUCCEEDED"
        assert data["result"] == result
        assert "error" not in data

    def test_get_failed_job(self, client, override_job_store):
        """Test getting status of a failed job with error."""
        # Create a job and update it to failed status with error
        job = asyncio.run(override_job_store.create_job(description="Test description"))
        error = {"error": "Planning failed", "type": "ValueError"}
        asyncio.run(override_job_store.mark_failed(job.job_id, error))

        response = client.get(f"/api/v1/plans/{job.job_id}")

        assert response.status_code == 200
        data = response.json()

        assert data["job_id"] == job.job_id
        assert data["status"] == "FAILED"
        assert data["result"] is None
        assert data["error"] == error

    def test_get_running_job(self, client, override_job_store):
        """Test getting status of a running job."""
        # Create a job and update it to running status
        job = asyncio.run(override_job_store.create_job(description="Test description"))
        asyncio.run(override_job_store.mark_running(job.job_id))

        response = client.get(f"/api/v1/plans/{job.job_id}")

        assert response.status_code == 200
        data = response.json()

        assert data["job_id"] == job.job_id
        assert data["status"] == "RUNNING"
        assert data["result"] is None
        assert "error" not in data

    def test_get_nonexistent_job_returns_404(self, client, override_job_store):
        """Test that requesting a non-existent job returns 404."""
        response = client.get("/api/v1/plans/nonexistent-job-id")

        assert response.status_code == 404
        data = response.json()

        assert "error" in data

        # Verify new error format
        error = data["error"]
        assert "code" in error
        assert "message" in error
        assert "request_id" in error
        assert error["code"] == "not_found"
        assert error["message"] == "Job not found"

    def test_get_job_status_no_stack_trace_in_404(self, client, override_job_store):
        """Test that 404 error doesn't include stack traces."""
        response = client.get("/api/v1/plans/missing-job-123")

        assert response.status_code == 404
        data = response.json()

        # Should have error object with proper structure
        assert "error" in data
        error = data["error"]
        assert "code" in error
        assert "message" in error

        # Should not have stack traces
        assert "traceback" not in data
        assert "stack" not in str(data).lower()

    def test_get_job_status_timestamps_are_iso_format(self, client, override_job_store):
        """Test that timestamps are returned in ISO format."""
        job = asyncio.run(override_job_store.create_job(description="Test description"))

        response = client.get(f"/api/v1/plans/{job.job_id}")

        assert response.status_code == 200
        data = response.json()

        # Check that timestamps can be parsed as ISO format
        created_at = datetime.fromisoformat(data["created_at"].replace("Z", "+00:00"))
        updated_at = datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00"))

        assert isinstance(created_at, datetime)
        assert isinstance(updated_at, datetime)

    def test_get_job_status_with_unicode_in_result(self, client, override_job_store):
        """Test that Unicode characters in result are preserved."""
        job = asyncio.run(override_job_store.create_job(description="Test description"))
        result = {
            "specs": [
                {
                    "purpose": "Test with émojis 🚀",
                    "vision": "Spëcial çhars",
                    "must": ["Requirement with 中文"],
                    "dont": [],
                    "nice": [],
                }
            ]
        }
        asyncio.run(override_job_store.mark_succeeded(job.job_id, result))

        response = client.get(f"/api/v1/plans/{job.job_id}")

        assert response.status_code == 200
        data = response.json()

        assert data["result"] == result
        assert "🚀" in data["result"]["specs"][0]["purpose"]
        assert "中文" in data["result"]["specs"][0]["must"][0]

    def test_get_job_status_with_large_result_payload(self, client, override_job_store):
        """Test that large result payloads are handled correctly in single job endpoint."""
        job = asyncio.run(override_job_store.create_job(description="Test description"))

        # Create a large result with many specs
        large_result = {
            "specs": [
                {
                    "purpose": f"Purpose {i}",
                    "vision": f"Vision {i}",
                    "must": [f"Must {i}-{j}" for j in range(100)],
                    "dont": [f"Dont {i}-{j}" for j in range(100)],
                    "nice": [f"Nice {i}-{j}" for j in range(100)],
                }
                for i in range(10)
            ]
        }
        asyncio.run(override_job_store.mark_succeeded(job.job_id, large_result))

        response = client.get(f"/api/v1/plans/{job.job_id}")

        assert response.status_code == 200
        data = response.json()

        assert data["result"] == large_result
        assert len(data["result"]["specs"]) == 10

    def test_list_jobs_with_large_result_omits_payload(self, client, override_job_store):
        """Test that list endpoint omits large result payloads (regression test)."""
        job = asyncio.run(override_job_store.create_job(description="Test description"))

        # Create a large result with many specs
        large_result = {
            "specs": [
                {
                    "purpose": f"Purpose {i}",
                    "vision": f"Vision {i}",
                    "must": [f"Must {i}-{j}" for j in range(100)],
                    "dont": [f"Dont {i}-{j}" for j in range(100)],
                    "nice": [f"Nice {i}-{j}" for j in range(100)],
                }
                for i in range(10)
            ]
        }
        asyncio.run(override_job_store.mark_succeeded(job.job_id, large_result))

        # List endpoint should omit the large payload
        list_response = client.get("/api/v1/plans")

        assert list_response.status_code == 200
        list_data = list_response.json()

        assert len(list_data["jobs"]) == 1
        job_data = list_data["jobs"][0]

        # Should not contain the large result
        assert job_data["result"] is None
        assert job_data["has_result"] is True

        # Verify response size is small (no specs array included)
        import json

        response_bytes = len(json.dumps(list_data).encode("utf-8"))
        # Should be much smaller than the actual result (which would be ~300KB)
        # Just checking it's reasonably small (< 10KB for metadata)
        assert response_bytes < 10000, f"Response too large: {response_bytes} bytes"


class TestListJobsEndpoint:
    """Test cases for GET /plans endpoint."""

    def test_list_jobs_empty_store(self, client, override_job_store):
        """Test listing jobs when store is empty."""
        response = client.get("/api/v1/plans")

        assert response.status_code == 200
        data = response.json()

        assert "jobs" in data
        assert "total" in data
        assert "limit" in data
        assert data["jobs"] == []
        assert data["total"] == 0

    def test_list_jobs_returns_all_jobs(self, client, override_job_store):
        """Test listing jobs returns all jobs."""
        # Create several jobs
        job1 = asyncio.run(override_job_store.create_job(description="Test description"))
        time.sleep(0.01)
        job2 = asyncio.run(override_job_store.create_job(description="Test description"))
        time.sleep(0.01)
        job3 = asyncio.run(override_job_store.create_job(description="Test description"))

        response = client.get("/api/v1/plans")

        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 3
        assert len(data["jobs"]) == 3

        # Verify job IDs are present
        job_ids = [job["job_id"] for job in data["jobs"]]
        assert job1.job_id in job_ids
        assert job2.job_id in job_ids
        assert job3.job_id in job_ids

    def test_list_jobs_sorted_by_updated_at_descending(self, client, override_job_store):
        """Test that jobs are sorted by updated_at (most recent first)."""
        # Create jobs with explicit ordering
        job1 = asyncio.run(override_job_store.create_job(description="Test description"))
        job2 = asyncio.run(override_job_store.create_job(description="Test description"))
        job3 = asyncio.run(override_job_store.create_job(description="Test description"))

        # Update job1 to make it most recently updated
        # The update will change updated_at, making job1 the most recent
        asyncio.run(override_job_store.mark_running(job1.job_id))

        # Get all jobs to verify final state (in logical order for readability)
        final_job1 = asyncio.run(override_job_store.get_job(job1.job_id))
        final_job2 = asyncio.run(override_job_store.get_job(job2.job_id))
        final_job3 = asyncio.run(override_job_store.get_job(job3.job_id))

        # Verify that job1's updated_at is indeed more recent
        assert final_job1.updated_at > final_job2.updated_at
        assert final_job1.updated_at > final_job3.updated_at

        response = client.get("/api/v1/plans")

        assert response.status_code == 200
        data = response.json()

        # job1 should be first (most recently updated)
        assert data["jobs"][0]["job_id"] == job1.job_id
        # job3 should be second, job2 third (by creation/initial update time)
        assert data["jobs"][1]["job_id"] == job3.job_id
        assert data["jobs"][2]["job_id"] == job2.job_id

    def test_list_jobs_with_limit(self, client, override_job_store):
        """Test listing jobs with a limit parameter."""
        # Create 5 jobs
        for i in range(5):
            asyncio.run(override_job_store.create_job(description="Test description"))
            time.sleep(0.01)

        response = client.get("/api/v1/plans?limit=3")

        assert response.status_code == 200
        data = response.json()

        # Total should reflect all jobs (5), not just returned (3)
        assert data["total"] == 5
        assert len(data["jobs"]) == 3
        assert data["limit"] == 3

    def test_list_jobs_limit_respects_max_config(self, client, override_job_store):
        """Test that limit cannot exceed max configuration."""
        from app.core.config import settings

        # Create some jobs
        for i in range(5):
            asyncio.run(override_job_store.create_job(description="Test description"))

        # Request more than max
        response = client.get(f"/api/v1/plans?limit={settings.max_jobs_list_limit + 100}")

        assert response.status_code == 200
        data = response.json()

        # Should be capped at max
        assert data["limit"] == settings.max_jobs_list_limit

    def test_list_jobs_uses_default_limit_when_not_specified(self, client, override_job_store):
        """Test that default limit is used when not specified."""
        from app.core.config import settings

        # Create some jobs
        for i in range(5):
            asyncio.run(override_job_store.create_job(description="Test description"))

        response = client.get("/api/v1/plans")

        assert response.status_code == 200
        data = response.json()

        assert data["limit"] == settings.default_jobs_list_limit

    def test_list_jobs_includes_job_metadata(self, client, override_job_store):
        """Test that listed jobs include all required metadata with has_result flag."""
        job = asyncio.run(override_job_store.create_job(description="Test description"))
        result = {"specs": [{"purpose": "Test"}]}
        asyncio.run(override_job_store.mark_succeeded(job.job_id, result))

        response = client.get("/api/v1/plans")

        assert response.status_code == 200
        data = response.json()

        assert len(data["jobs"]) == 1
        job_data = data["jobs"][0]

        assert job_data["job_id"] == job.job_id
        assert job_data["status"] == "SUCCEEDED"
        assert "created_at" in job_data
        assert "updated_at" in job_data
        # List endpoint should return null result with has_result flag
        assert job_data["result"] is None
        assert "has_result" in job_data
        assert job_data["has_result"] is True

    def test_list_jobs_includes_errors_for_failed_jobs(self, client, override_job_store):
        """Test that failed jobs include error in list with has_result=false."""
        job = asyncio.run(override_job_store.create_job(description="Test description"))
        error = {"error": "Test error", "type": "ValueError"}
        asyncio.run(override_job_store.mark_failed(job.job_id, error))

        response = client.get("/api/v1/plans")

        assert response.status_code == 200
        data = response.json()

        assert len(data["jobs"]) == 1
        job_data = data["jobs"][0]

        assert job_data["status"] == "FAILED"
        assert job_data["error"] == error
        assert job_data["result"] is None
        assert "has_result" in job_data
        assert job_data["has_result"] is False

    def test_list_jobs_with_mixed_statuses(self, client, override_job_store):
        """Test listing jobs with different statuses."""
        # Create jobs with different statuses
        job1 = asyncio.run(override_job_store.create_job(description="Test description"))  # pending

        job2 = asyncio.run(override_job_store.create_job(description="Test description"))
        asyncio.run(override_job_store.mark_running(job2.job_id))

        job3 = asyncio.run(override_job_store.create_job(description="Test description"))
        asyncio.run(
            override_job_store.mark_succeeded(job3.job_id, {"specs": [{"purpose": "Test"}]})
        )

        job4 = asyncio.run(override_job_store.create_job(description="Test description"))
        asyncio.run(
            override_job_store.mark_failed(
                job4.job_id, {"error": "Test error", "type": "ValueError"}
            )
        )

        response = client.get("/api/v1/plans")

        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 4

        # Verify all statuses are present
        statuses = [job["status"] for job in data["jobs"]]
        assert "QUEUED" in statuses
        assert "RUNNING" in statuses
        assert "SUCCEEDED" in statuses
        assert "FAILED" in statuses

    def test_list_jobs_limit_validation_rejects_zero(self, client, override_job_store):
        """Test that limit=0 is rejected."""
        response = client.get("/api/v1/plans?limit=0")

        # Should fail validation (limit must be >= 1)
        assert response.status_code == 422

    def test_list_jobs_limit_validation_rejects_negative(self, client, override_job_store):
        """Test that negative limit is rejected."""
        response = client.get("/api/v1/plans?limit=-1")

        # Should fail validation (limit must be >= 1)
        assert response.status_code == 422


class TestPollingEndpointsConcurrency:
    """Test cases for concurrent polling scenarios."""

    def test_concurrent_get_job_status_requests(self, client, override_job_store):
        """Test that concurrent GET requests for same job work correctly."""
        from concurrent.futures import ThreadPoolExecutor

        job = asyncio.run(override_job_store.create_job(description="Test description"))

        def get_job():
            return client.get(f"/api/v1/plans/{job.job_id}")

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(get_job) for _ in range(20)]
            responses = [f.result() for f in futures]

        # All should succeed
        assert all(r.status_code == 200 for r in responses)

        # All should return same data
        job_ids = [r.json()["job_id"] for r in responses]
        assert all(jid == job.job_id for jid in job_ids)

    def test_high_frequency_polling_does_not_mutate_state(self, client, override_job_store):
        """Test that high-frequency polling doesn't mutate job state."""
        job = asyncio.run(override_job_store.create_job(description="Test description"))
        initial_job = asyncio.run(override_job_store.get_job(job.job_id))

        # Make many requests quickly
        for _ in range(100):
            response = client.get(f"/api/v1/plans/{job.job_id}")
            assert response.status_code == 200

        # Job should not have changed
        final_job = asyncio.run(override_job_store.get_job(job.job_id))
        assert final_job.status == initial_job.status
        assert final_job.updated_at == initial_job.updated_at

    def test_list_jobs_while_creating_jobs(self, client, override_job_store):
        """Test listing jobs while jobs are being created concurrently."""
        import random
        from concurrent.futures import ThreadPoolExecutor

        def create_job(i):
            asyncio.run(override_job_store.create_job(description="Test description"))
            time.sleep(random.uniform(0.001, 0.01))

        def list_jobs(i):
            return client.get("/api/v1/plans")

        with ThreadPoolExecutor(max_workers=10) as executor:
            # Mix create and list operations
            create_futures = [executor.submit(create_job, i) for i in range(10)]
            list_futures = [executor.submit(list_jobs, i) for i in range(10)]

            # Wait for all operations
            for f in create_futures + list_futures:
                f.result()

        # Final list should have all jobs
        response = client.get("/api/v1/plans")
        assert response.status_code == 200
        assert response.json()["total"] == 10


class TestPollingEndpointsEdgeCases:
    """Test cases for edge cases in polling endpoints."""

    def test_get_job_immediately_after_creation(self, client, override_job_store):
        """Test getting job status immediately after creation."""
        # Create job via POST
        post_response = client.post("/api/v1/plans", json={"description": "Build an API"})
        job_id = post_response.json()["job_id"]

        # Immediately get status
        get_response = client.get(f"/api/v1/plans/{job_id}")

        assert get_response.status_code == 200
        data = get_response.json()

        assert data["job_id"] == job_id
        # Status could be pending or already running/succeeded due to background task
        assert data["status"] in ["QUEUED", "RUNNING", "SUCCEEDED"]

    def test_polling_job_through_lifecycle(self, client, override_job_store):
        """Test polling a job through its complete lifecycle."""
        job = asyncio.run(override_job_store.create_job(description="Test description"))

        # Check pending state
        response = client.get(f"/api/v1/plans/{job.job_id}")
        assert response.json()["status"] == "QUEUED"

        # Update to running
        asyncio.run(override_job_store.mark_running(job.job_id))
        response = client.get(f"/api/v1/plans/{job.job_id}")
        assert response.json()["status"] == "RUNNING"

        # Update to succeeded
        asyncio.run(override_job_store.mark_succeeded(job.job_id, {"specs": [{"purpose": "Test"}]}))
        response = client.get(f"/api/v1/plans/{job.job_id}")
        data = response.json()
        assert data["status"] == "SUCCEEDED"
        assert data["result"] is not None

    def test_list_jobs_with_only_pending_jobs(self, client, override_job_store):
        """Test listing when all jobs are pending with has_result=false."""
        for i in range(5):
            asyncio.run(override_job_store.create_job(description="Test description"))

        response = client.get("/api/v1/plans")

        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 5
        assert all(job["status"] == "QUEUED" for job in data["jobs"])
        assert all(job["result"] is None for job in data["jobs"])
        assert all(job["has_result"] is False for job in data["jobs"])

    def test_list_jobs_response_structure_matches_single_job(self, client, override_job_store):
        """Test that jobs in list have lightweight structure vs single job endpoint."""
        job = asyncio.run(override_job_store.create_job(description="Test description"))
        asyncio.run(override_job_store.mark_succeeded(job.job_id, {"specs": [{"purpose": "Test"}]}))

        # Get single job (full result)
        single_response = client.get(f"/api/v1/plans/{job.job_id}")
        single_data = single_response.json()

        # Get list (lightweight)
        list_response = client.get("/api/v1/plans")
        list_data = list_response.json()

        # List should have has_result field, single should not
        job_from_list = list_data["jobs"][0]
        assert "has_result" in job_from_list
        assert "has_result" not in single_data

        # List should have null result, single should have full result
        assert job_from_list["result"] is None
        assert single_data["result"] is not None
        assert "specs" in single_data["result"]

    def test_get_job_with_invalid_uuid_format(self, client, override_job_store):
        """Test getting job with malformed UUID still returns 404."""
        response = client.get("/api/v1/plans/not-a-uuid")

        # Should return 404, not validation error
        assert response.status_code == 404

    def test_list_jobs_limit_as_string_number(self, client, override_job_store):
        """Test that limit as string number works correctly."""
        for i in range(10):
            asyncio.run(override_job_store.create_job(description="Test description"))

        response = client.get("/api/v1/plans?limit=5")

        assert response.status_code == 200
        data = response.json()

        # Total should be all jobs (10), returned jobs should be 5
        assert data["total"] == 10
        assert len(data["jobs"]) == 5
        assert data["limit"] == 5


class TestJobMetadataExposure:
    """Test cases for model and system_prompt_hash metadata in job responses."""

    def test_get_job_with_model_metadata(self, client, override_job_store):
        """Test that job with model metadata exposes it in GET response."""
        job = asyncio.run(
            override_job_store.create_job(description="Test description", model="gpt-4-turbo")
        )

        response = client.get(f"/api/v1/plans/{job.job_id}")

        assert response.status_code == 200
        data = response.json()

        assert "model" in data
        assert data["model"] == "gpt-4-turbo"

    def test_get_job_with_system_prompt_hash_metadata(self, client, override_job_store):
        """Test that job with system_prompt exposes hash in GET response."""
        custom_prompt = "You are a test assistant"
        import hashlib

        expected_hash = hashlib.sha256(custom_prompt.encode("utf-8")).hexdigest()

        job = asyncio.run(
            override_job_store.create_job(
                description="Test description", system_prompt=custom_prompt
            )
        )

        response = client.get(f"/api/v1/plans/{job.job_id}")

        assert response.status_code == 200
        data = response.json()

        assert "system_prompt_hash" in data
        assert data["system_prompt_hash"] == expected_hash

    def test_get_job_with_both_metadata_fields(self, client, override_job_store):
        """Test that job with both metadata fields exposes both."""
        custom_prompt = "Test prompt xyz"
        import hashlib

        expected_hash = hashlib.sha256(custom_prompt.encode("utf-8")).hexdigest()

        job = asyncio.run(
            override_job_store.create_job(
                description="Test description", model="claude-opus", system_prompt=custom_prompt
            )
        )

        response = client.get(f"/api/v1/plans/{job.job_id}")

        assert response.status_code == 200
        data = response.json()

        assert data["model"] == "claude-opus"
        assert data["system_prompt_hash"] == expected_hash

    def test_get_job_without_metadata_omits_fields(self, client, override_job_store):
        """Test that job without metadata doesn't include those fields."""
        job = asyncio.run(override_job_store.create_job(description="Test description"))

        response = client.get(f"/api/v1/plans/{job.job_id}")

        assert response.status_code == 200
        data = response.json()

        # Fields should not be present if None
        assert "model" not in data or data.get("model") is None
        assert "system_prompt_hash" not in data or data.get("system_prompt_hash") is None

    def test_get_pending_job_with_metadata(self, client, override_job_store):
        """Test that pending jobs expose metadata even before completion."""
        custom_prompt = "Pending test prompt"
        import hashlib

        expected_hash = hashlib.sha256(custom_prompt.encode("utf-8")).hexdigest()

        job = asyncio.run(
            override_job_store.create_job(
                description="Test description", model="gpt-4-turbo", system_prompt=custom_prompt
            )
        )

        response = client.get(f"/api/v1/plans/{job.job_id}")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "QUEUED"
        assert data["model"] == "gpt-4-turbo"
        assert data["system_prompt_hash"] == expected_hash

    def test_list_jobs_includes_metadata(self, client, override_job_store):
        """Test that job list includes metadata fields with has_result flag."""
        job1 = asyncio.run(
            override_job_store.create_job(description="Test description", model="gpt-4-turbo")
        )

        custom_prompt2 = "List test prompt"
        import hashlib

        expected_hash2 = hashlib.sha256(custom_prompt2.encode("utf-8")).hexdigest()
        job2 = asyncio.run(
            override_job_store.create_job(
                description="Test description", system_prompt=custom_prompt2
            )
        )

        job3 = asyncio.run(
            override_job_store.create_job(description="Test description")
        )  # No metadata

        # Mark job1 as succeeded so it has a result
        asyncio.run(override_job_store.mark_succeeded(job1.job_id, {"specs": [{"purpose": "Test"}]}))

        response = client.get("/api/v1/plans")

        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 3

        # Find jobs in response
        jobs_by_id = {job["job_id"]: job for job in data["jobs"]}

        # Check metadata is included
        assert jobs_by_id[job1.job_id]["model"] == "gpt-4-turbo"
        assert jobs_by_id[job2.job_id]["system_prompt_hash"] == expected_hash2

        # Check has_result flags
        assert jobs_by_id[job1.job_id]["has_result"] is True  # succeeded with result
        assert jobs_by_id[job2.job_id]["has_result"] is False  # queued, no result
        assert jobs_by_id[job3.job_id]["has_result"] is False  # queued, no result

        # All should have null result in list
        assert jobs_by_id[job1.job_id]["result"] is None
        assert jobs_by_id[job2.job_id]["result"] is None
        assert jobs_by_id[job3.job_id]["result"] is None

    def test_succeeded_job_with_metadata_includes_all_fields(self, client, override_job_store):
        """Test that succeeded job includes metadata alongside result."""
        custom_prompt = "Success test prompt"
        import hashlib

        expected_hash = hashlib.sha256(custom_prompt.encode("utf-8")).hexdigest()

        job = asyncio.run(
            override_job_store.create_job(
                description="Test description", model="gpt-4-turbo", system_prompt=custom_prompt
            )
        )

        result = {"specs": [{"purpose": "Test"}]}
        asyncio.run(override_job_store.mark_succeeded(job.job_id, result))

        response = client.get(f"/api/v1/plans/{job.job_id}")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "SUCCEEDED"
        assert data["result"] == result
        assert data["model"] == "gpt-4-turbo"
        assert data["system_prompt_hash"] == expected_hash

    def test_failed_job_with_metadata_includes_all_fields(self, client, override_job_store):
        """Test that failed job includes metadata alongside error."""
        custom_prompt = "Failed test prompt"
        import hashlib

        expected_hash = hashlib.sha256(custom_prompt.encode("utf-8")).hexdigest()

        job = asyncio.run(
            override_job_store.create_job(
                description="Test description", model="claude-opus", system_prompt=custom_prompt
            )
        )

        error = {"error": "Test error", "type": "ValueError"}
        asyncio.run(override_job_store.mark_failed(job.job_id, error))

        response = client.get(f"/api/v1/plans/{job.job_id}")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "FAILED"
        assert data["error"] == error
        assert data["model"] == "claude-opus"
        assert data["system_prompt_hash"] == expected_hash


class TestJobSerializationWithOptionalFields:
    """Test cases for job serialization with optional assumptions and open_questions fields."""

    def test_get_succeeded_job_with_optional_fields(self, client, override_job_store):
        """Test that jobs with optional fields are serialized correctly."""
        job = asyncio.run(override_job_store.create_job(description="Test description"))
        asyncio.run(override_job_store.mark_running(job.job_id))

        result = {
            "specs": [
                {
                    "purpose": "Test Purpose",
                    "vision": "Test Vision",
                    "must": ["Requirement 1"],
                    "dont": ["Avoid 1"],
                    "nice": ["Nice 1"],
                    "assumptions": ["Using PostgreSQL", "RESTful conventions"],
                    "open_questions": ["What auth method?", "Support pagination?"],
                }
            ]
        }
        asyncio.run(override_job_store.mark_succeeded(job.job_id, result))

        response = client.get(f"/api/v1/plans/{job.job_id}")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "SUCCEEDED"
        assert "result" in data
        assert "specs" in data["result"]
        spec = data["result"]["specs"][0]
        assert "assumptions" in spec
        assert "open_questions" in spec
        assert len(spec["assumptions"]) == 2
        assert len(spec["open_questions"]) == 2
        assert spec["assumptions"][0] == "Using PostgreSQL"
        assert spec["open_questions"][0] == "What auth method?"

    def test_get_succeeded_job_without_optional_fields(self, client, override_job_store):
        """Test that jobs without optional fields are serialized with empty lists."""
        job = asyncio.run(override_job_store.create_job(description="Test description"))
        asyncio.run(override_job_store.mark_running(job.job_id))

        result = {
            "specs": [
                {
                    "purpose": "Test Purpose",
                    "vision": "Test Vision",
                    "must": ["Requirement 1"],
                    "dont": ["Avoid 1"],
                    "nice": ["Nice 1"],
                    "assumptions": [],
                    "open_questions": [],
                }
            ]
        }
        asyncio.run(override_job_store.mark_succeeded(job.job_id, result))

        response = client.get(f"/api/v1/plans/{job.job_id}")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "SUCCEEDED"
        spec = data["result"]["specs"][0]
        assert spec["assumptions"] == []
        assert spec["open_questions"] == []

    def test_list_jobs_with_optional_fields(self, client, override_job_store):
        """Test that listing jobs omits result but includes has_result flag."""
        # Create and succeed a job with optional fields
        job = asyncio.run(override_job_store.create_job(description="Test description"))
        asyncio.run(override_job_store.mark_running(job.job_id))

        result = {
            "specs": [
                {
                    "purpose": "Test Purpose",
                    "vision": "Test Vision",
                    "must": ["Requirement 1"],
                    "dont": ["Avoid 1"],
                    "nice": ["Nice 1"],
                    "assumptions": ["Assumption 1", "Assumption 2"],
                    "open_questions": ["Question 1"],
                }
            ]
        }
        asyncio.run(override_job_store.mark_succeeded(job.job_id, result))

        response = client.get("/api/v1/plans")

        assert response.status_code == 200
        data = response.json()

        assert "jobs" in data
        assert len(data["jobs"]) == 1
        job_data = data["jobs"][0]
        assert job_data["status"] == "SUCCEEDED"
        # List endpoint should omit result but indicate it exists
        assert job_data["result"] is None
        assert "has_result" in job_data
        assert job_data["has_result"] is True
