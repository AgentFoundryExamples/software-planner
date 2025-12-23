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

import time
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.job_store import JobStore


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def mock_job_store():
    """Create a mock job store for testing."""
    return JobStore()


@pytest.fixture
def override_job_store(mock_job_store):
    """Override the job store dependency for testing."""
    from app.services.store_singleton import get_job_store
    
    app.dependency_overrides[get_job_store] = lambda: mock_job_store
    yield mock_job_store
    app.dependency_overrides.clear()


class TestGetJobStatusEndpoint:
    """Test cases for GET /plans/{job_id} endpoint."""
    
    def test_get_pending_job(self, client, override_job_store):
        """Test getting status of a pending job."""
        # Create a pending job
        job = override_job_store.create_job()
        
        response = client.get(f"/api/v1/plans/{job.job_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["job_id"] == job.job_id
        assert data["status"] == "pending"
        assert "created_at" in data
        assert "updated_at" in data
        assert data["result"] is None
        assert "error" not in data
    
    def test_get_succeeded_job(self, client, override_job_store):
        """Test getting status of a succeeded job with result."""
        # Create a job and update it to succeeded status with result
        job = override_job_store.create_job()
        result = {
            "specs": [
                {
                    "purpose": "Test Purpose",
                    "vision": "Test Vision",
                    "must": ["Requirement 1"],
                    "dont": ["Avoid 1"],
                    "nice": ["Nice to have 1"]
                }
            ]
        }
        override_job_store.update_job(job.job_id, status="succeeded", result=result)
        
        response = client.get(f"/api/v1/plans/{job.job_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["job_id"] == job.job_id
        assert data["status"] == "succeeded"
        assert data["result"] == result
        assert "error" not in data
    
    def test_get_failed_job(self, client, override_job_store):
        """Test getting status of a failed job with error."""
        # Create a job and update it to failed status with error
        job = override_job_store.create_job()
        error = {
            "error": "Planning failed",
            "type": "ValueError"
        }
        override_job_store.update_job(job.job_id, status="failed", error=error)
        
        response = client.get(f"/api/v1/plans/{job.job_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["job_id"] == job.job_id
        assert data["status"] == "failed"
        assert data["result"] is None
        assert data["error"] == error
    
    def test_get_running_job(self, client, override_job_store):
        """Test getting status of a running job."""
        # Create a job and update it to running status
        job = override_job_store.create_job()
        override_job_store.update_job(job.job_id, status="running")
        
        response = client.get(f"/api/v1/plans/{job.job_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["job_id"] == job.job_id
        assert data["status"] == "running"
        assert data["result"] is None
        assert "error" not in data
    
    def test_get_nonexistent_job_returns_404(self, client, override_job_store):
        """Test that requesting a non-existent job returns 404."""
        response = client.get("/api/v1/plans/nonexistent-job-id")
        
        assert response.status_code == 404
        data = response.json()
        
        assert "error" in data
        assert data["error"] == "Job not found"
    
    def test_get_job_status_no_stack_trace_in_404(self, client, override_job_store):
        """Test that 404 error doesn't include stack traces."""
        response = client.get("/api/v1/plans/missing-job-123")
        
        assert response.status_code == 404
        data = response.json()
        
        # Should only have error and status_code fields
        assert "error" in data
        assert "status_code" in data
        assert "traceback" not in data
        assert "stack" not in str(data).lower()
    
    def test_get_job_status_timestamps_are_iso_format(self, client, override_job_store):
        """Test that timestamps are returned in ISO format."""
        job = override_job_store.create_job()
        
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
        job = override_job_store.create_job()
        result = {
            "specs": [
                {
                    "purpose": "Test with émojis 🚀",
                    "vision": "Spëcial çhars",
                    "must": ["Requirement with 中文"],
                    "dont": [],
                    "nice": []
                }
            ]
        }
        override_job_store.update_job(job.job_id, status="succeeded", result=result)
        
        response = client.get(f"/api/v1/plans/{job.job_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["result"] == result
        assert "🚀" in data["result"]["specs"][0]["purpose"]
        assert "中文" in data["result"]["specs"][0]["must"][0]
    
    def test_get_job_status_with_large_result_payload(self, client, override_job_store):
        """Test that large result payloads are handled correctly."""
        job = override_job_store.create_job()
        
        # Create a large result with many specs
        large_result = {
            "specs": [
                {
                    "purpose": f"Purpose {i}",
                    "vision": f"Vision {i}",
                    "must": [f"Must {i}-{j}" for j in range(100)],
                    "dont": [f"Dont {i}-{j}" for j in range(100)],
                    "nice": [f"Nice {i}-{j}" for j in range(100)]
                }
                for i in range(10)
            ]
        }
        override_job_store.update_job(job.job_id, status="succeeded", result=large_result)
        
        response = client.get(f"/api/v1/plans/{job.job_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["result"] == large_result
        assert len(data["result"]["specs"]) == 10


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
        job1 = override_job_store.create_job()
        time.sleep(0.01)
        job2 = override_job_store.create_job()
        time.sleep(0.01)
        job3 = override_job_store.create_job()
        
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
        job1 = override_job_store.create_job()
        job2 = override_job_store.create_job()
        job3 = override_job_store.create_job()
        
        # Update job1 to make it most recently updated
        # The update will change updated_at, making job1 the most recent
        override_job_store.update_job(job1.job_id, status="running")
        
        # Get all jobs to verify final state
        final_job1 = override_job_store.get_job(job1.job_id)
        final_job3 = override_job_store.get_job(job3.job_id)
        final_job2 = override_job_store.get_job(job2.job_id)
        
        # Verify that job1's updated_at is indeed more recent
        assert final_job1.updated_at > final_job3.updated_at
        assert final_job1.updated_at > final_job2.updated_at
        
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
            override_job_store.create_job()
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
            override_job_store.create_job()
        
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
            override_job_store.create_job()
        
        response = client.get("/api/v1/plans")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["limit"] == settings.default_jobs_list_limit
    
    def test_list_jobs_includes_job_metadata(self, client, override_job_store):
        """Test that listed jobs include all required metadata."""
        job = override_job_store.create_job()
        result = {"specs": [{"purpose": "Test"}]}
        override_job_store.update_job(job.job_id, status="succeeded", result=result)
        
        response = client.get("/api/v1/plans")
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["jobs"]) == 1
        job_data = data["jobs"][0]
        
        assert job_data["job_id"] == job.job_id
        assert job_data["status"] == "succeeded"
        assert "created_at" in job_data
        assert "updated_at" in job_data
        assert job_data["result"] == result
    
    def test_list_jobs_includes_errors_for_failed_jobs(self, client, override_job_store):
        """Test that failed jobs include error in list."""
        job = override_job_store.create_job()
        error = {"error": "Test error", "type": "ValueError"}
        override_job_store.update_job(job.job_id, status="failed", error=error)
        
        response = client.get("/api/v1/plans")
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["jobs"]) == 1
        job_data = data["jobs"][0]
        
        assert job_data["status"] == "failed"
        assert job_data["error"] == error
        assert job_data["result"] is None
    
    def test_list_jobs_with_mixed_statuses(self, client, override_job_store):
        """Test listing jobs with different statuses."""
        # Create jobs with different statuses
        job1 = override_job_store.create_job()  # pending
        
        job2 = override_job_store.create_job()
        override_job_store.update_job(job2.job_id, status="running")
        
        job3 = override_job_store.create_job()
        override_job_store.update_job(
            job3.job_id,
            status="succeeded",
            result={"specs": [{"purpose": "Test"}]}
        )
        
        job4 = override_job_store.create_job()
        override_job_store.update_job(
            job4.job_id,
            status="failed",
            error={"error": "Test error", "type": "ValueError"}
        )
        
        response = client.get("/api/v1/plans")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total"] == 4
        
        # Verify all statuses are present
        statuses = [job["status"] for job in data["jobs"]]
        assert "pending" in statuses
        assert "running" in statuses
        assert "succeeded" in statuses
        assert "failed" in statuses
    
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
        
        job = override_job_store.create_job()
        
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
        job = override_job_store.create_job()
        initial_job = override_job_store.get_job(job.job_id)
        
        # Make many requests quickly
        for _ in range(100):
            response = client.get(f"/api/v1/plans/{job.job_id}")
            assert response.status_code == 200
        
        # Job should not have changed
        final_job = override_job_store.get_job(job.job_id)
        assert final_job.status == initial_job.status
        assert final_job.updated_at == initial_job.updated_at
    
    def test_list_jobs_while_creating_jobs(self, client, override_job_store):
        """Test listing jobs while jobs are being created concurrently."""
        from concurrent.futures import ThreadPoolExecutor
        import random
        
        def create_job(i):
            override_job_store.create_job()
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
        post_response = client.post(
            "/api/v1/plans",
            json={"description": "Build an API"}
        )
        job_id = post_response.json()["job_id"]
        
        # Immediately get status
        get_response = client.get(f"/api/v1/plans/{job_id}")
        
        assert get_response.status_code == 200
        data = get_response.json()
        
        assert data["job_id"] == job_id
        # Status could be pending or already running/succeeded due to background task
        assert data["status"] in ["pending", "running", "succeeded"]
    
    def test_polling_job_through_lifecycle(self, client, override_job_store):
        """Test polling a job through its complete lifecycle."""
        job = override_job_store.create_job()
        
        # Check pending state
        response = client.get(f"/api/v1/plans/{job.job_id}")
        assert response.json()["status"] == "pending"
        
        # Update to running
        override_job_store.update_job(job.job_id, status="running")
        response = client.get(f"/api/v1/plans/{job.job_id}")
        assert response.json()["status"] == "running"
        
        # Update to succeeded
        override_job_store.update_job(
            job.job_id,
            status="succeeded",
            result={"specs": [{"purpose": "Test"}]}
        )
        response = client.get(f"/api/v1/plans/{job.job_id}")
        data = response.json()
        assert data["status"] == "succeeded"
        assert data["result"] is not None
    
    def test_list_jobs_with_only_pending_jobs(self, client, override_job_store):
        """Test listing when all jobs are pending."""
        for i in range(5):
            override_job_store.create_job()
        
        response = client.get("/api/v1/plans")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total"] == 5
        assert all(job["status"] == "pending" for job in data["jobs"])
        assert all(job["result"] is None for job in data["jobs"])
    
    def test_list_jobs_response_structure_matches_single_job(self, client, override_job_store):
        """Test that jobs in list have same structure as single job endpoint."""
        job = override_job_store.create_job()
        override_job_store.update_job(
            job.job_id,
            status="succeeded",
            result={"specs": [{"purpose": "Test"}]}
        )
        
        # Get single job
        single_response = client.get(f"/api/v1/plans/{job.job_id}")
        single_data = single_response.json()
        
        # Get list
        list_response = client.get("/api/v1/plans")
        list_data = list_response.json()
        
        # Structure should match
        job_from_list = list_data["jobs"][0]
        assert set(job_from_list.keys()) == set(single_data.keys())
    
    def test_get_job_with_invalid_uuid_format(self, client, override_job_store):
        """Test getting job with malformed UUID still returns 404."""
        response = client.get("/api/v1/plans/not-a-uuid")
        
        # Should return 404, not validation error
        assert response.status_code == 404
    
    def test_list_jobs_limit_as_string_number(self, client, override_job_store):
        """Test that limit as string number works correctly."""
        for i in range(10):
            override_job_store.create_job()
        
        response = client.get("/api/v1/plans?limit=5")
        
        assert response.status_code == 200
        data = response.json()
        
        # Total should be all jobs (10), returned jobs should be 5
        assert data["total"] == 10
        assert len(data["jobs"]) == 5
        assert data["limit"] == 5
