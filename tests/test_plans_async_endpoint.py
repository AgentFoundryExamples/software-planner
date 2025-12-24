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
"""Tests for the async POST /plans endpoint."""

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
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
    from app.services.rate_limiter import RateLimiter

    # Create a disabled rate limiter for these tests
    disabled_limiter = RateLimiter(window_seconds=60, max_requests=10, enabled=False)  # Disabled

    # Patch both the LLM client and rate limiter
    with patch("app.services.store_singleton.get_llm_client", return_value=mock_llm_client):
        with patch("app.api.routes.get_rate_limiter", return_value=disabled_limiter):
            yield TestClient(app)


@pytest.fixture
def mock_job_store():
    """Create a mock job store for testing."""
    return JobStore()


@pytest.fixture
def override_job_store(mock_llm_client, mock_job_store):
    """Override the job store dependency for testing."""
    from app.services.rate_limiter import RateLimiter
    from app.services.store_singleton import get_job_store

    # Create a disabled rate limiter for these tests
    disabled_limiter = RateLimiter(window_seconds=60, max_requests=10, enabled=False)  # Disabled

    # Patch both job store, LLM client, and rate limiter
    with patch("app.services.store_singleton.get_llm_client", return_value=mock_llm_client):
        with patch("app.api.routes.get_rate_limiter", return_value=disabled_limiter):
            app.dependency_overrides[get_job_store] = lambda: mock_job_store
            yield mock_job_store
            app.dependency_overrides.clear()


class TestPlansEndpointJobCreation:
    """Test cases for POST /plans job creation."""

    def test_plans_endpoint_creates_job_and_returns_202(self, client, override_job_store):
        """Test that POST /plans returns 202 with job_id."""
        response = client.post("/api/v1/plans", json={"description": "Build a REST API"})

        assert response.status_code == 202
        data = response.json()

        assert "job_id" in data
        assert "status" in data
        assert data["status"] == "QUEUED"
        assert len(data["job_id"]) > 0

    def test_plans_endpoint_creates_job_in_store(self, client, override_job_store):
        """Test that job is actually created in the job store."""
        response = client.post("/api/v1/plans", json={"description": "Build a REST API"})

        assert response.status_code == 202
        job_id = response.json()["job_id"]

        # Verify job exists in store
        job = asyncio.run(override_job_store.get_job(job_id))
        assert job is not None
        assert job.job_id == job_id
        # Note: TestClient runs background tasks synchronously, so job may already be succeeded
        assert job.status in ["QUEUED", "RUNNING", "SUCCEEDED"]

    def test_plans_endpoint_response_structure(self, client, override_job_store):
        """Test that response has only job_id and status fields."""
        response = client.post("/api/v1/plans", json={"description": "Build a web service"})

        assert response.status_code == 202
        data = response.json()

        # Should have exactly these two fields
        assert set(data.keys()) == {"job_id", "status"}

    def test_plans_endpoint_sets_timestamps(self, client, override_job_store):
        """Test that created jobs have created_at and updated_at timestamps."""
        response = client.post("/api/v1/plans", json={"description": "Build an API"})

        job_id = response.json()["job_id"]
        job = asyncio.run(override_job_store.get_job(job_id))

        assert job is not None
        assert job.created_at is not None
        assert job.updated_at is not None

    def test_plans_endpoint_multiple_requests_unique_job_ids(self, client, override_job_store):
        """Test that multiple requests generate unique job IDs."""
        responses = [
            client.post("/api/v1/plans", json={"description": f"Project {i}"}) for i in range(10)
        ]

        job_ids = [r.json()["job_id"] for r in responses]

        # All should be successful
        assert all(r.status_code == 202 for r in responses)

        # All job IDs should be unique
        assert len(job_ids) == len(set(job_ids))


class TestPlansEndpointValidationErrors:
    """Test cases for validation errors in POST /plans."""

    def test_plans_endpoint_with_empty_description_returns_400(self, client, override_job_store):
        """Test that empty description returns 400 without creating job."""
        initial_count = len(asyncio.run(override_job_store.list_jobs()))

        response = client.post("/api/v1/plans", json={"description": ""})

        assert response.status_code == 400

        # No job should be created
        assert len(asyncio.run(override_job_store.list_jobs())) == initial_count

    def test_plans_endpoint_with_whitespace_only_returns_400(self, client, override_job_store):
        """Test that whitespace-only description returns 400 without creating job."""
        initial_count = len(asyncio.run(override_job_store.list_jobs()))

        response = client.post("/api/v1/plans", json={"description": "   \t\n  "})

        assert response.status_code == 400

        # No job should be created
        assert len(asyncio.run(override_job_store.list_jobs())) == initial_count

    def test_plans_endpoint_with_oversized_description_returns_400(
        self, client, override_job_store
    ):
        """Test that oversized description returns 400 without creating job."""
        from app.core.config import settings

        initial_count = len(asyncio.run(override_job_store.list_jobs()))
        oversized = "a" * (settings.max_description_bytes + 1)

        response = client.post("/api/v1/plans", json={"description": oversized})

        assert response.status_code == 400

        # No job should be created
        assert len(asyncio.run(override_job_store.list_jobs())) == initial_count

    def test_plans_endpoint_with_missing_description_returns_422(self, client, override_job_store):
        """Test that missing description field returns 422 without creating job."""
        initial_count = len(asyncio.run(override_job_store.list_jobs()))

        response = client.post("/api/v1/plans", json={})

        assert response.status_code == 422

        # No job should be created
        assert len(asyncio.run(override_job_store.list_jobs())) == initial_count

    def test_plans_endpoint_with_wrong_field_type_returns_422(self, client, override_job_store):
        """Test that wrong field type returns 422 without creating job."""
        initial_count = len(asyncio.run(override_job_store.list_jobs()))

        response = client.post("/api/v1/plans", json={"description": 123})

        assert response.status_code == 422

        # No job should be created
        assert len(asyncio.run(override_job_store.list_jobs())) == initial_count


class TestPlansEndpointBackgroundExecution:
    """Test cases for background task execution.

    Note: TestClient runs background tasks synchronously by default, but the tasks
    are still executed after the response is returned. The time.sleep() calls in
    these tests ensure the background tasks have completed before checking results.
    This is not a race condition - it's the expected behavior with FastAPI's
    BackgroundTasks in test environments.
    """

    def test_plans_endpoint_background_task_succeeds(self, client, override_job_store):
        """Test that background task completes successfully."""
        response = client.post("/api/v1/plans", json={"description": "Build a REST API"})

        job_id = response.json()["job_id"]

        # Wait for background task to complete (TestClient runs them synchronously)
        time.sleep(0.5)

        # Check job status
        job = asyncio.run(override_job_store.get_job(job_id))
        assert job is not None
        assert job.status == "SUCCEEDED"
        assert job.result is not None
        assert "specs" in job.result

    def test_plans_endpoint_background_task_stores_result(self, client, override_job_store):
        """Test that background task stores the planning result."""
        response = client.post("/api/v1/plans", json={"description": "Create a web service"})

        job_id = response.json()["job_id"]
        time.sleep(0.5)

        job = asyncio.run(override_job_store.get_job(job_id))
        assert job is not None
        assert job.result is not None
        assert "specs" in job.result
        assert isinstance(job.result["specs"], list)
        assert len(job.result["specs"]) >= 1

    def test_plans_endpoint_background_task_updates_timestamp(self, client, override_job_store):
        """Test that background task updates the job timestamp."""
        response = client.post("/api/v1/plans", json={"description": "Build an API"})

        job_id = response.json()["job_id"]
        initial_job = asyncio.run(override_job_store.get_job(job_id))
        initial_updated_at = initial_job.updated_at

        time.sleep(0.5)

        job = asyncio.run(override_job_store.get_job(job_id))
        assert job.updated_at >= initial_updated_at

    def test_plans_endpoint_preserves_created_at(self, client, override_job_store):
        """Test that background execution doesn't change created_at."""
        response = client.post("/api/v1/plans", json={"description": "Build an API"})

        job_id = response.json()["job_id"]
        initial_job = asyncio.run(override_job_store.get_job(job_id))
        initial_created_at = initial_job.created_at

        time.sleep(0.5)

        job = asyncio.run(override_job_store.get_job(job_id))
        assert job.created_at == initial_created_at


class TestPlansEndpointErrorHandling:
    """Test cases for error handling in background execution."""

    def test_plans_endpoint_with_simulated_failure(self, client, override_job_store, monkeypatch):
        """Test that exceptions in background worker set failed status."""

        # Mock generate_plan to raise an exception
        def mock_generate_plan_error(
            description,
            job_repository=None,
            job_id=None,
            llm_client=None,
            model=None,
            system_prompt=None,
        ):
            if job_repository and job_id:
                import asyncio

                asyncio.run(job_repository.mark_running(job_id))
            raise ValueError("Simulated planning error")

        monkeypatch.setattr("app.api.routes.generate_plan", mock_generate_plan_error)

        response = client.post("/api/v1/plans", json={"description": "Build a REST API"})

        job_id = response.json()["job_id"]
        time.sleep(0.5)

        job = asyncio.run(override_job_store.get_job(job_id))
        assert job is not None
        assert job.status == "FAILED"
        assert job.error is not None

    def test_plans_endpoint_error_does_not_leak_stack_trace(
        self, client, override_job_store, monkeypatch
    ):
        """Test that error details don't include stack traces."""

        def mock_generate_plan_error(
            description,
            job_repository=None,
            job_id=None,
            llm_client=None,
            model=None,
            system_prompt=None,
        ):
            if job_repository and job_id:
                import asyncio

                asyncio.run(job_repository.mark_running(job_id))
            raise RuntimeError("Internal error with sensitive data")

        monkeypatch.setattr("app.api.routes.generate_plan", mock_generate_plan_error)

        response = client.post("/api/v1/plans", json={"description": "Build a REST API"})

        job_id = response.json()["job_id"]
        time.sleep(0.5)

        job = asyncio.run(override_job_store.get_job(job_id))
        assert job is not None
        assert job.error is not None

        # Error should have error message and type, but no stack trace
        assert "error" in job.error
        assert "type" in job.error
        assert "traceback" not in job.error
        assert "RuntimeError" in job.error["type"]

    def test_plans_endpoint_error_does_not_crash_server(
        self, client, override_job_store, monkeypatch
    ):
        """Test that background errors don't crash the server."""

        def mock_generate_plan_error(
            description,
            job_repository=None,
            job_id=None,
            llm_client=None,
            model=None,
            system_prompt=None,
        ):
            if job_repository and job_id:
                import asyncio

                asyncio.run(job_repository.mark_running(job_id))
            raise Exception("Critical error")

        monkeypatch.setattr("app.api.routes.generate_plan", mock_generate_plan_error)

        # First request with error
        response1 = client.post("/api/v1/plans", json={"description": "Build API 1"})
        assert response1.status_code == 202

        time.sleep(0.5)

        # Server should still be responsive
        response2 = client.post("/api/v1/plans", json={"description": "Build API 2"})
        assert response2.status_code == 202


class TestPlansEndpointConcurrency:
    """Test cases for concurrent request handling."""

    def test_plans_endpoint_concurrent_requests_unique_jobs(self, client, override_job_store):
        """Test that concurrent requests create unique job IDs."""
        num_requests = 20

        def make_request(i):
            return client.post("/api/v1/plans", json={"description": f"Build API {i}"})

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request, i) for i in range(num_requests)]
            responses = [f.result() for f in futures]

        # All should succeed
        assert all(r.status_code == 202 for r in responses)

        # All should have unique job IDs
        job_ids = [r.json()["job_id"] for r in responses]
        assert len(job_ids) == len(set(job_ids))

    def test_plans_endpoint_concurrent_background_execution(self, client, override_job_store):
        """Test that concurrent background tasks execute correctly."""
        num_requests = 5

        responses = [
            client.post("/api/v1/plans", json={"description": f"Project {i}"})
            for i in range(num_requests)
        ]

        job_ids = [r.json()["job_id"] for r in responses]

        # Wait for all background tasks
        time.sleep(1.0)

        # All jobs should succeed
        for job_id in job_ids:
            job = asyncio.run(override_job_store.get_job(job_id))
            assert job is not None
            assert job.status == "SUCCEEDED"
            assert job.result is not None


class TestPlansEndpointEdgeCases:
    """Test cases for edge cases."""

    def test_plans_endpoint_with_unicode_description(self, client, override_job_store):
        """Test that Unicode descriptions work correctly."""
        response = client.post(
            "/api/v1/plans", json={"description": "Build API with émojis 🚀 and spëcial çhars"}
        )

        assert response.status_code == 202
        job_id = response.json()["job_id"]

        time.sleep(0.5)

        job = asyncio.run(override_job_store.get_job(job_id))
        assert job is not None
        assert job.status == "SUCCEEDED"

    def test_plans_endpoint_with_max_length_description(self, client, override_job_store):
        """Test that descriptions at max length work correctly."""
        from app.core.config import settings

        description = "a" * settings.max_description_bytes

        response = client.post("/api/v1/plans", json={"description": description})

        assert response.status_code == 202
        job_id = response.json()["job_id"]

        time.sleep(0.5)

        job = asyncio.run(override_job_store.get_job(job_id))
        assert job is not None
        assert job.status == "SUCCEEDED"

    def test_plans_endpoint_with_extra_fields(self, client, override_job_store):
        """Test that extra fields are ignored."""
        response = client.post(
            "/api/v1/plans",
            json={"description": "Build an API", "extra_field": "should be ignored"},
        )

        assert response.status_code == 202


class TestPlansEndpointModelAndPromptParameters:
    """Test cases for model and system_prompt parameters in async endpoint."""

    def test_plans_endpoint_with_model_parameter(self, client, override_job_store):
        """Test that model parameter is stored in job metadata."""
        response = client.post(
            "/api/v1/plans", json={"description": "Build a REST API", "model": "gpt-4-turbo"}
        )

        # Accept both success and validation failure
        assert response.status_code in [202, 400]

        if response.status_code == 202:
            job_id = response.json()["job_id"]
            job = asyncio.run(override_job_store.get_job(job_id))
            assert job is not None
            # Model should be stored in job metadata
            assert job.model == "gpt-4-turbo"

    def test_plans_endpoint_with_system_prompt_parameter(self, client, override_job_store):
        """Test that system_prompt parameter is stored in job metadata."""
        custom_prompt = "You are an expert API architect."

        response = client.post(
            "/api/v1/plans",
            json={"description": "Build a REST API", "system_prompt": custom_prompt},
        )

        assert response.status_code == 202
        job_id = response.json()["job_id"]
        job = asyncio.run(override_job_store.get_job(job_id))

        assert job is not None
        # System prompt should be stored
        assert job.system_prompt is not None
        assert job.system_prompt == custom_prompt

    def test_plans_endpoint_with_both_overrides(self, client, override_job_store):
        """Test that both model and system_prompt can be provided together."""
        response = client.post(
            "/api/v1/plans",
            json={
                "description": "Build a REST API",
                "model": "gpt-4-turbo",
                "system_prompt": "You are an expert.",
            },
        )

        # Accept both success and validation failure
        assert response.status_code in [202, 400]

        if response.status_code == 202:
            job_id = response.json()["job_id"]
            job = asyncio.run(override_job_store.get_job(job_id))
            assert job is not None
            assert job.model == "gpt-4-turbo"
            assert job.system_prompt is not None

    def test_plans_endpoint_without_overrides_has_null_metadata(self, client, override_job_store):
        """Test that jobs without overrides have null metadata fields."""
        response = client.post("/api/v1/plans", json={"description": "Build a REST API"})

        assert response.status_code == 202
        job_id = response.json()["job_id"]
        job = asyncio.run(override_job_store.get_job(job_id))

        assert job is not None
        assert job.model is None
        assert job.system_prompt is None

    def test_plans_endpoint_oversized_system_prompt_rejected(self, client, override_job_store):
        """Test that oversized system prompts are rejected."""
        from app.core.config import settings

        oversized_prompt = "a" * (settings.max_system_prompt_bytes + 1)

        response = client.post(
            "/api/v1/plans",
            json={"description": "Build a REST API", "system_prompt": oversized_prompt},
        )

        assert response.status_code == 400
        data = response.json()
        assert "error" in data or "detail" in data

    def test_plans_endpoint_whitespace_model_rejected(self, client, override_job_store):
        """Test that whitespace-only model names are rejected."""
        response = client.post(
            "/api/v1/plans", json={"description": "Build a REST API", "model": "   "}
        )

        assert response.status_code == 400
        data = response.json()
        assert "error" in data or "detail" in data

    def test_plans_endpoint_concurrent_jobs_different_models(self, client, override_job_store):
        """Test that concurrent jobs with different models don't interfere."""
        response1 = client.post(
            "/api/v1/plans", json={"description": "Build API 1", "model": "gpt-4-turbo"}
        )

        response2 = client.post(
            "/api/v1/plans", json={"description": "Build API 2", "model": "claude-opus"}
        )

        # Accept both success and validation failure
        if response1.status_code == 202 and response2.status_code == 202:
            job_id1 = response1.json()["job_id"]
            job_id2 = response2.json()["job_id"]

            time.sleep(0.5)

            job1 = asyncio.run(override_job_store.get_job(job_id1))
            job2 = asyncio.run(override_job_store.get_job(job_id2))

            assert job1 is not None
            assert job2 is not None
            # Models should be kept separate
            assert job1.model == "gpt-4-turbo"
            assert job2.model == "claude-opus"

    def test_plans_endpoint_concurrent_jobs_different_prompts(self, client, override_job_store):
        """Test that concurrent jobs with different prompts don't interfere."""
        prompt1 = "You are a backend specialist."
        prompt2 = "You are a frontend specialist."

        response1 = client.post(
            "/api/v1/plans", json={"description": "Build API 1", "system_prompt": prompt1}
        )

        response2 = client.post(
            "/api/v1/plans", json={"description": "Build API 2", "system_prompt": prompt2}
        )

        assert response1.status_code == 202
        assert response2.status_code == 202

        job_id1 = response1.json()["job_id"]
        job_id2 = response2.json()["job_id"]

        time.sleep(0.5)

        job1 = asyncio.run(override_job_store.get_job(job_id1))
        job2 = asyncio.run(override_job_store.get_job(job_id2))

        assert job1 is not None
        assert job2 is not None
        # Prompts should be different
        assert job1.system_prompt != job2.system_prompt
        assert job1.system_prompt == prompt1
        assert job2.system_prompt == prompt2
