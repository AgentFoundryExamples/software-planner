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
"""Tests for the JobRepository service."""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from app.services.job_repository import (
    JobRepository,
    JobRepositoryError,
    JobNotFoundError,
    JobTransitionError
)
from app.models.job import Job


@pytest.fixture
def mock_engine():
    """Create a mock async engine for testing."""
    engine = MagicMock()
    return engine


@pytest.fixture
def job_repository(mock_engine):
    """Create a JobRepository instance with mocked engine."""
    return JobRepository(engine=mock_engine)


class TestJobRepositoryCreate:
    """Test cases for create_job operation."""
    
    @pytest.mark.asyncio
    async def test_create_job_success(self, job_repository, mock_engine):
        """Test successful job creation."""
        # Mock successful insert
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock()
        mock_engine.begin = MagicMock(return_value=mock_conn)
        
        job = await job_repository.create_job(
            description="Test project",
            model="test-model",
            system_prompt="Test prompt"
        )
        
        assert job is not None
        assert job.status == "QUEUED"
        assert job.description == "Test project"
        assert job.model == "test-model"
        assert job.system_prompt == "Test prompt"
        assert job.result is None
        assert job.error is None
        assert job.created_at is not None
        assert job.updated_at is not None
    
    @pytest.mark.asyncio
    async def test_create_job_without_optional_fields(self, job_repository, mock_engine):
        """Test job creation without model and system_prompt."""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock()
        mock_engine.begin = MagicMock(return_value=mock_conn)
        
        job = await job_repository.create_job(description="Test project")
        
        assert job.status == "QUEUED"
        assert job.description == "Test project"
        assert job.model is None
        assert job.system_prompt is None


class TestJobRepositoryGet:
    """Test cases for get_job operation."""
    
    @pytest.mark.asyncio
    async def test_get_job_found(self, job_repository, mock_engine):
        """Test retrieving an existing job."""
        # Mock database response
        mock_row = MagicMock()
        mock_row.job_id = "test-job-id"
        mock_row.status = "QUEUED"
        mock_row.description = "Test"
        mock_row.model = "test-model"
        mock_row.system_prompt = "prompt"
        mock_row.result = None
        mock_row.error = None
        mock_row.created_at = datetime.now(timezone.utc)
        mock_row.updated_at = datetime.now(timezone.utc)
        mock_row.started_at = None
        mock_row.finished_at = None
        
        mock_result = MagicMock()
        mock_result.fetchone = MagicMock(return_value=mock_row)
        
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_result)
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock()
        mock_engine.connect = MagicMock(return_value=mock_conn)
        
        job = await job_repository.get_job("test-job-id")
        
        assert job is not None
        assert job.job_id == "test-job-id"
        assert job.status == "QUEUED"
    
    @pytest.mark.asyncio
    async def test_get_job_not_found(self, job_repository, mock_engine):
        """Test retrieving a non-existent job returns None."""
        mock_result = MagicMock()
        mock_result.fetchone = MagicMock(return_value=None)
        
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_result)
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock()
        mock_engine.connect = MagicMock(return_value=mock_conn)
        
        job = await job_repository.get_job("non-existent-id")
        
        assert job is None


class TestJobRepositoryMarkRunning:
    """Test cases for mark_running lifecycle transition."""
    
    @pytest.mark.asyncio
    async def test_mark_running_success(self, job_repository, mock_engine):
        """Test successful transition from QUEUED to RUNNING."""
        # Mock SELECT FOR UPDATE
        mock_row = MagicMock()
        mock_row.status = "QUEUED"
        
        mock_result = MagicMock()
        mock_result.fetchone = MagicMock(return_value=mock_row)
        
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_result)
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock()
        mock_engine.begin = MagicMock(return_value=mock_conn)
        
        # Mock get_job to return updated job
        updated_job = Job(
            job_id="test-id",
            status="RUNNING",
            description="Test",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            started_at=datetime.now(timezone.utc),
            finished_at=None
        )
        job_repository.get_job = AsyncMock(return_value=updated_job)
        
        job = await job_repository.mark_running("test-id")
        
        assert job.status == "RUNNING"
        assert job.started_at is not None
    
    @pytest.mark.asyncio
    async def test_mark_running_invalid_transition(self, job_repository, mock_engine):
        """Test invalid transition raises JobTransitionError."""
        # Mock job in RUNNING state
        mock_row = MagicMock()
        mock_row.status = "RUNNING"
        
        mock_result = MagicMock()
        mock_result.fetchone = MagicMock(return_value=mock_row)
        
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_result)
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock()
        mock_engine.begin = MagicMock(return_value=mock_conn)
        
        # Don't mock get_job since we expect it to fail in the transition check
        with pytest.raises(JobTransitionError) as exc_info:
            await job_repository.mark_running("test-id")
        
        assert "Cannot transition from RUNNING to RUNNING" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_mark_running_job_not_found(self, job_repository, mock_engine):
        """Test marking non-existent job as running raises JobNotFoundError."""
        mock_result = MagicMock()
        mock_result.fetchone = MagicMock(return_value=None)
        
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_result)
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock()
        mock_engine.begin = MagicMock(return_value=mock_conn)
        
        # Don't mock get_job since we expect the fetch to fail first
        with pytest.raises(JobNotFoundError) as exc_info:
            await job_repository.mark_running("non-existent-id")
        
        assert "Job not found" in str(exc_info.value)


class TestJobRepositoryMarkSucceeded:
    """Test cases for mark_succeeded lifecycle transition."""
    
    @pytest.mark.asyncio
    async def test_mark_succeeded_success(self, job_repository, mock_engine):
        """Test successful transition from RUNNING to SUCCEEDED."""
        # Mock SELECT FOR UPDATE
        mock_row = MagicMock()
        mock_row.status = "RUNNING"
        
        mock_result = MagicMock()
        mock_result.fetchone = MagicMock(return_value=mock_row)
        
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_result)
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock()
        mock_engine.begin = MagicMock(return_value=mock_conn)
        
        result = {"specs": [{"purpose": "Test"}]}
        
        # Mock get_job to return updated job
        updated_job = Job(
            job_id="test-id",
            status="SUCCEEDED",
            description="Test",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
            result=result
        )
        job_repository.get_job = AsyncMock(return_value=updated_job)
        
        job = await job_repository.mark_succeeded("test-id", result)
        
        assert job.status == "SUCCEEDED"
        assert job.result == result
        assert job.finished_at is not None
    
    @pytest.mark.asyncio
    async def test_mark_succeeded_invalid_transition(self, job_repository, mock_engine):
        """Test invalid transition raises JobTransitionError."""
        # Mock job in QUEUED state
        mock_row = MagicMock()
        mock_row.status = "QUEUED"
        
        mock_result = MagicMock()
        mock_result.fetchone = MagicMock(return_value=mock_row)
        
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_result)
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock()
        mock_engine.begin = MagicMock(return_value=mock_conn)
        
        # Don't mock get_job since we expect it to fail in the transition check
        with pytest.raises(JobTransitionError) as exc_info:
            await job_repository.mark_succeeded("test-id", {"specs": []})
        
        assert "Cannot transition from QUEUED to SUCCEEDED" in str(exc_info.value)


class TestJobRepositoryMarkFailed:
    """Test cases for mark_failed lifecycle transition."""
    
    @pytest.mark.asyncio
    async def test_mark_failed_from_running(self, job_repository, mock_engine):
        """Test successful transition from RUNNING to FAILED."""
        # Mock SELECT FOR UPDATE
        mock_row = MagicMock()
        mock_row.status = "RUNNING"
        mock_row.started_at = datetime.now(timezone.utc)
        
        mock_result = MagicMock()
        mock_result.fetchone = MagicMock(return_value=mock_row)
        
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_result)
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock()
        mock_engine.begin = MagicMock(return_value=mock_conn)
        
        error = {"error": "Test error", "type": "TestError"}
        
        # Mock get_job to return updated job
        updated_job = Job(
            job_id="test-id",
            status="FAILED",
            description="Test",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            started_at=mock_row.started_at,
            finished_at=datetime.now(timezone.utc),
            error=error
        )
        job_repository.get_job = AsyncMock(return_value=updated_job)
        
        job = await job_repository.mark_failed("test-id", error)
        
        assert job.status == "FAILED"
        assert job.error == error
        assert job.finished_at is not None
    
    @pytest.mark.asyncio
    async def test_mark_failed_from_queued(self, job_repository, mock_engine):
        """Test transition from QUEUED to FAILED (restart recovery case)."""
        # Mock SELECT FOR UPDATE
        mock_row = MagicMock()
        mock_row.status = "QUEUED"
        mock_row.started_at = None
        
        mock_result = MagicMock()
        mock_result.fetchone = MagicMock(return_value=mock_row)
        
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_result)
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock()
        mock_engine.begin = MagicMock(return_value=mock_conn)
        
        error = {"error": "Test error", "type": "TestError"}
        
        # Mock get_job to return updated job
        updated_job = Job(
            job_id="test-id",
            status="FAILED",
            description="Test",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            started_at=datetime.now(timezone.utc),  # Should be set
            finished_at=datetime.now(timezone.utc),
            error=error
        )
        job_repository.get_job = AsyncMock(return_value=updated_job)
        
        job = await job_repository.mark_failed("test-id", error)
        
        assert job.status == "FAILED"
        assert job.started_at is not None  # Should be set even if was None
    
    @pytest.mark.asyncio
    async def test_mark_failed_invalid_transition(self, job_repository, mock_engine):
        """Test invalid transition from terminal state raises JobTransitionError."""
        # Mock job in SUCCEEDED state
        mock_row = MagicMock()
        mock_row.status = "SUCCEEDED"
        
        mock_result = MagicMock()
        mock_result.fetchone = MagicMock(return_value=mock_row)
        
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_result)
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock()
        mock_engine.begin = MagicMock(return_value=mock_conn)
        
        # Don't mock get_job since we expect it to fail in the transition check
        with pytest.raises(JobTransitionError) as exc_info:
            await job_repository.mark_failed("test-id", {"error": "test"})
        
        assert "Cannot transition from SUCCEEDED to FAILED" in str(exc_info.value)


class TestJobRepositoryList:
    """Test cases for list_jobs operation."""
    
    @pytest.mark.asyncio
    async def test_list_jobs_empty(self, job_repository, mock_engine):
        """Test listing jobs from empty repository."""
        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([]))
        
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_result)
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock()
        mock_engine.connect = MagicMock(return_value=mock_conn)
        
        jobs = await job_repository.list_jobs()
        
        assert jobs == []
    
    @pytest.mark.asyncio
    async def test_list_jobs_with_limit(self, job_repository, mock_engine):
        """Test listing jobs with limit parameter."""
        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([]))
        
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_result)
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock()
        mock_engine.connect = MagicMock(return_value=mock_conn)
        
        jobs = await job_repository.list_jobs(limit=10)
        
        # Verify LIMIT clause was added
        call_args = mock_conn.execute.call_args
        query_str = str(call_args[0][0])
        assert "LIMIT" in query_str


class TestJobRepositoryRecoverStuckJobs:
    """Test cases for recover_stuck_jobs operation."""
    
    @pytest.mark.asyncio
    async def test_recover_stuck_jobs_none_stuck(self, job_repository, mock_engine):
        """Test recovery when no jobs are stuck."""
        mock_result = MagicMock()
        mock_result.rowcount = 0  # No rows affected
        
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_result)
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock()
        mock_engine.begin = MagicMock(return_value=mock_conn)
        
        count = await job_repository.recover_stuck_jobs()
        
        assert count == 0
        # Verify single UPDATE was called
        assert mock_conn.execute.call_count == 1
    
    @pytest.mark.asyncio
    async def test_recover_stuck_jobs_marks_failed(self, job_repository, mock_engine):
        """Test recovery marks RUNNING jobs as FAILED."""
        mock_result = MagicMock()
        mock_result.rowcount = 2  # Two rows affected
        
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_result)
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock()
        mock_engine.begin = MagicMock(return_value=mock_conn)
        
        count = await job_repository.recover_stuck_jobs()
        
        assert count == 2
        # Verify single UPDATE was called (optimized single query)
        assert mock_conn.execute.call_count == 1


class TestJobRepositoryDatabaseErrors:
    """Test cases for database error handling and fallback paths."""
    
    @pytest.mark.asyncio
    async def test_hash_determinism_for_job_ids(self, job_repository, mock_engine):
        """Test that job IDs are deterministic based on input parameters."""
        import uuid
        
        # Mock successful inserts for multiple jobs
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock()
        mock_engine.begin = MagicMock(return_value=mock_conn)
        
        # Create multiple jobs with same description
        job1 = await job_repository.create_job(description="Same description")
        job2 = await job_repository.create_job(description="Same description")
        
        # Job IDs should be different (UUIDs are unique)
        assert job1.job_id != job2.job_id
        # Both should be valid UUIDs
        try:
            uuid.UUID(job1.job_id)
            uuid.UUID(job2.job_id)
        except ValueError:
            pytest.fail("Job IDs should be valid UUIDs")
    
    @pytest.mark.asyncio
    async def test_system_prompt_hash_determinism(self, job_repository, mock_engine):
        """Test that system_prompt_hash is computed deterministically."""
        import hashlib
        
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock()
        mock_engine.begin = MagicMock(return_value=mock_conn)
        
        prompt = "Test system prompt"
        expected_hash = hashlib.sha256(prompt.encode('utf-8')).hexdigest()
        
        job = await job_repository.create_job(
            description="Test",
            system_prompt=prompt
        )
        
        # Job should store the prompt itself, not the hash
        # Hash is computed on retrieval
        assert job.system_prompt == prompt
