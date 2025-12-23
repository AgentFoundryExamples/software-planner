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
"""Tests for the JobStore service."""

import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pytest

from app.services.job_store import JobStore


class TestJobStoreBasicOperations:
    """Test cases for basic JobStore operations."""
    
    def test_create_job_generates_unique_id(self):
        """Test that create_job generates a unique job ID."""
        store = JobStore()
        job = store.create_job()
        
        assert job is not None
        assert job.job_id is not None
        assert len(job.job_id) > 0
    
    def test_create_job_sets_pending_status(self):
        """Test that newly created jobs have pending status."""
        store = JobStore()
        job = store.create_job()
        
        assert job.status == "pending"
    
    def test_create_job_sets_timestamps(self):
        """Test that create_job sets created_at and updated_at."""
        store = JobStore()
        before = datetime.now(timezone.utc)
        job = store.create_job()
        after = datetime.now(timezone.utc)
        
        assert before <= job.created_at <= after
        assert before <= job.updated_at <= after
        assert job.created_at == job.updated_at
    
    def test_create_job_initializes_result_and_error_to_none(self):
        """Test that new jobs have None for result and error."""
        store = JobStore()
        job = store.create_job()
        
        assert job.result is None
        assert job.error is None
    
    def test_get_job_retrieves_existing_job(self):
        """Test that get_job retrieves a job by ID."""
        store = JobStore()
        created_job = store.create_job()
        
        retrieved_job = store.get_job(created_job.job_id)
        
        assert retrieved_job is not None
        assert retrieved_job.job_id == created_job.job_id
        assert retrieved_job.status == created_job.status
    
    def test_get_job_returns_none_for_unknown_id(self):
        """Test that get_job returns None for non-existent job ID."""
        store = JobStore()
        job = store.get_job("non-existent-id")
        
        assert job is None
    
    def test_update_job_changes_status(self):
        """Test that update_job changes the job status."""
        store = JobStore()
        job = store.create_job()
        
        updated = store.update_job(job.job_id, status="running")
        
        assert updated is not None
        assert updated.status == "running"
        assert updated.job_id == job.job_id
    
    def test_update_job_updates_timestamp(self):
        """Test that update_job updates the updated_at timestamp."""
        store = JobStore()
        job = store.create_job()
        original_updated_at = job.updated_at
        
        time.sleep(0.01)  # Ensure time difference
        updated = store.update_job(job.job_id, status="running")
        
        assert updated is not None
        assert updated.updated_at > original_updated_at
    
    def test_update_job_sets_result(self):
        """Test that update_job can set the result field."""
        store = JobStore()
        job = store.create_job()
        result = {"specs": [{"purpose": "test"}]}
        
        updated = store.update_job(job.job_id, result=result)
        
        assert updated is not None
        assert updated.result == result
    
    def test_update_job_sets_error(self):
        """Test that update_job can set the error field."""
        store = JobStore()
        job = store.create_job()
        error = {"error": "Something failed", "type": "ValueError"}
        
        updated = store.update_job(job.job_id, error=error)
        
        assert updated is not None
        assert updated.error == error
    
    def test_update_job_returns_none_for_unknown_id(self):
        """Test that update_job returns None for non-existent job."""
        store = JobStore()
        updated = store.update_job("non-existent-id", status="running")
        
        assert updated is None
    
    def test_update_job_partial_update(self):
        """Test that update_job only updates specified fields."""
        store = JobStore()
        job = store.create_job()
        result = {"specs": []}
        
        # Update only status
        store.update_job(job.job_id, status="running")
        
        # Update only result
        updated = store.update_job(job.job_id, result=result)
        
        assert updated is not None
        assert updated.status == "running"  # Should remain from previous update
        assert updated.result == result
        assert updated.error is None
    
    def test_list_jobs_empty_store(self):
        """Test that list_jobs returns empty list for empty store."""
        store = JobStore()
        jobs = store.list_jobs()
        
        assert jobs == []
    
    def test_list_jobs_returns_all_jobs(self):
        """Test that list_jobs returns all created jobs."""
        store = JobStore()
        job1 = store.create_job()
        job2 = store.create_job()
        job3 = store.create_job()
        
        jobs = store.list_jobs()
        
        assert len(jobs) == 3
        job_ids = {job.job_id for job in jobs}
        assert job1.job_id in job_ids
        assert job2.job_id in job_ids
        assert job3.job_id in job_ids
    
    def test_list_jobs_sorted_by_created_at_descending(self):
        """Test that list_jobs returns jobs sorted by created_at (newest first)."""
        store = JobStore()
        
        job1 = store.create_job()
        time.sleep(0.01)
        job2 = store.create_job()
        time.sleep(0.01)
        job3 = store.create_job()
        
        jobs = store.list_jobs()
        
        assert len(jobs) == 3
        # Newest first
        assert jobs[0].job_id == job3.job_id
        assert jobs[1].job_id == job2.job_id
        assert jobs[2].job_id == job1.job_id


class TestJobStoreEdgeCases:
    """Test cases for edge cases in JobStore."""
    
    def test_create_job_generates_unique_ids(self):
        """Test that multiple jobs get unique IDs."""
        store = JobStore()
        jobs = [store.create_job() for _ in range(100)]
        job_ids = [job.job_id for job in jobs]
        
        # All IDs should be unique
        assert len(job_ids) == len(set(job_ids))
    
    def test_update_job_with_all_fields(self):
        """Test updating a job with all fields at once."""
        store = JobStore()
        job = store.create_job()
        
        result = {"specs": []}
        error = {"error": "test"}
        
        updated = store.update_job(
            job.job_id,
            status="failed",
            result=result,
            error=error
        )
        
        assert updated is not None
        assert updated.status == "failed"
        assert updated.result == result
        assert updated.error == error
    
    def test_update_preserves_created_at(self):
        """Test that updates don't change created_at timestamp."""
        store = JobStore()
        job = store.create_job()
        original_created_at = job.created_at
        
        time.sleep(0.01)
        updated = store.update_job(job.job_id, status="running")
        
        assert updated is not None
        assert updated.created_at == original_created_at
    
    def test_get_job_after_update_returns_latest(self):
        """Test that get_job returns the updated version."""
        store = JobStore()
        job = store.create_job()
        
        store.update_job(job.job_id, status="running")
        store.update_job(job.job_id, status="succeeded")
        
        retrieved = store.get_job(job.job_id)
        
        assert retrieved is not None
        assert retrieved.status == "succeeded"
    
    def test_large_result_payload_stored_correctly(self):
        """Test that large result payloads are stored without mutation."""
        store = JobStore()
        job = store.create_job()
        
        large_result = {
            "specs": [
                {
                    "purpose": f"Purpose {i}",
                    "vision": f"Vision {i}",
                    "must": [f"item-{j}" for j in range(100)],
                    "dont": [f"dont-{j}" for j in range(100)],
                    "nice": [f"nice-{j}" for j in range(100)]
                }
                for i in range(50)
            ]
        }
        
        updated = store.update_job(job.job_id, result=large_result)
        
        assert updated is not None
        assert updated.result == large_result
        assert len(updated.result["specs"]) == 50


class TestJobStoreThreadSafety:
    """Test cases for thread safety of JobStore."""
    
    def test_concurrent_job_creation(self):
        """Test that concurrent job creation is thread-safe."""
        store = JobStore()
        num_threads = 10
        jobs_per_thread = 10
        
        def create_jobs():
            return [store.create_job() for _ in range(jobs_per_thread)]
        
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(create_jobs) for _ in range(num_threads)]
            results = [f.result() for f in futures]
        
        # Flatten results
        all_jobs = [job for sublist in results for job in sublist]
        
        # All jobs should have unique IDs
        job_ids = [job.job_id for job in all_jobs]
        assert len(job_ids) == len(set(job_ids))
        assert len(job_ids) == num_threads * jobs_per_thread
    
    def test_concurrent_updates_are_safe(self):
        """Test that concurrent updates don't corrupt job state."""
        store = JobStore()
        job = store.create_job()
        num_threads = 10
        
        def update_to_running():
            store.update_job(job.job_id, status="running")
        
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(update_to_running) for _ in range(num_threads)]
            [f.result() for f in futures]
        
        # Job should still be in valid state
        retrieved = store.get_job(job.job_id)
        assert retrieved is not None
        assert retrieved.status == "running"
    
    def test_concurrent_read_and_write(self):
        """Test that concurrent reads and writes don't cause errors."""
        store = JobStore()
        jobs = [store.create_job() for _ in range(5)]
        
        def read_jobs():
            for job in jobs:
                store.get_job(job.job_id)
            store.list_jobs()
        
        def write_jobs():
            for job in jobs:
                store.update_job(job.job_id, status="running")
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            read_futures = [executor.submit(read_jobs) for _ in range(5)]
            write_futures = [executor.submit(write_jobs) for _ in range(5)]
            
            # Wait for all operations
            [f.result() for f in read_futures + write_futures]
        
        # All jobs should still exist and be in valid state
        assert len(store.list_jobs()) == 5
        for job in jobs:
            retrieved = store.get_job(job.job_id)
            assert retrieved is not None
    
    def test_no_timestamp_race_condition(self):
        """Test that concurrent updates don't create timestamp inconsistencies."""
        store = JobStore()
        job = store.create_job()
        num_updates = 20
        
        def update_job():
            time.sleep(0.001)  # Small delay to increase chance of race
            store.update_job(job.job_id, status="running")
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(update_job) for _ in range(num_updates)]
            [f.result() for f in futures]
        
        # Check that updated_at is valid and after created_at
        retrieved = store.get_job(job.job_id)
        assert retrieved is not None
        assert retrieved.updated_at >= retrieved.created_at


class TestJobStoreMetadata:
    """Test cases for model and system_prompt_hash metadata in JobStore."""
    
    def test_create_job_with_model_metadata(self):
        """Test creating a job with model metadata."""
        store = JobStore()
        job = store.create_job(model="gpt-4-turbo")
        
        assert job is not None
        assert job.model == "gpt-4-turbo"
        assert job.system_prompt_hash is None
    
    def test_create_job_with_system_prompt_hash_metadata(self):
        """Test creating a job with system_prompt_hash metadata."""
        store = JobStore()
        job = store.create_job(system_prompt_hash="abc123def456")
        
        assert job is not None
        assert job.model is None
        assert job.system_prompt_hash == "abc123def456"
    
    def test_create_job_with_both_metadata_fields(self):
        """Test creating a job with both metadata fields."""
        store = JobStore()
        job = store.create_job(
            model="claude-opus",
            system_prompt_hash="xyz789"
        )
        
        assert job is not None
        assert job.model == "claude-opus"
        assert job.system_prompt_hash == "xyz789"
    
    def test_create_job_without_metadata(self):
        """Test creating a job without metadata has None values."""
        store = JobStore()
        job = store.create_job()
        
        assert job is not None
        assert job.model is None
        assert job.system_prompt_hash is None
    
    def test_get_job_preserves_metadata(self):
        """Test that retrieving a job preserves metadata."""
        store = JobStore()
        job = store.create_job(
            model="gpt-4-turbo",
            system_prompt_hash="hash123"
        )
        
        retrieved = store.get_job(job.job_id)
        
        assert retrieved is not None
        assert retrieved.model == "gpt-4-turbo"
        assert retrieved.system_prompt_hash == "hash123"
    
    def test_update_job_preserves_metadata(self):
        """Test that updating a job preserves metadata."""
        store = JobStore()
        job = store.create_job(
            model="gpt-4-turbo",
            system_prompt_hash="hash123"
        )
        
        # Update status
        updated = store.update_job(job.job_id, status="running")
        
        assert updated is not None
        assert updated.status == "running"
        assert updated.model == "gpt-4-turbo"
        assert updated.system_prompt_hash == "hash123"
    
    def test_list_jobs_includes_metadata(self):
        """Test that listing jobs includes metadata."""
        store = JobStore()
        job1 = store.create_job(model="gpt-4-turbo")
        job2 = store.create_job(system_prompt_hash="hash123")
        job3 = store.create_job()  # No metadata
        
        jobs = store.list_jobs()
        
        assert len(jobs) == 3
        
        # Find jobs by ID
        jobs_by_id = {job.job_id: job for job in jobs}
        
        assert jobs_by_id[job1.job_id].model == "gpt-4-turbo"
        assert jobs_by_id[job2.job_id].system_prompt_hash == "hash123"
        assert jobs_by_id[job3.job_id].model is None
        assert jobs_by_id[job3.job_id].system_prompt_hash is None
    
    def test_concurrent_creation_with_different_metadata(self):
        """Test that concurrent job creation with different metadata is safe."""
        store = JobStore()
        
        def create_with_model(model_name):
            return store.create_job(model=model_name)
        
        models = [f"model-{i}" for i in range(10)]
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(create_with_model, m) for m in models]
            jobs = [f.result() for f in futures]
        
        # All jobs should have correct model
        for i, job in enumerate(jobs):
            assert job.model == f"model-{i}"
    
    def test_metadata_with_succeeded_job(self):
        """Test that metadata is preserved when job succeeds."""
        store = JobStore()
        job = store.create_job(
            model="gpt-4-turbo",
            system_prompt_hash="hash123"
        )
        
        result = {"specs": [{"purpose": "Test"}]}
        updated = store.update_job(job.job_id, status="succeeded", result=result)
        
        assert updated is not None
        assert updated.status == "succeeded"
        assert updated.result == result
        assert updated.model == "gpt-4-turbo"
        assert updated.system_prompt_hash == "hash123"
    
    def test_metadata_with_failed_job(self):
        """Test that metadata is preserved when job fails."""
        store = JobStore()
        job = store.create_job(
            model="claude-opus",
            system_prompt_hash="hash456"
        )
        
        error = {"error": "Test error", "type": "ValueError"}
        updated = store.update_job(job.job_id, status="failed", error=error)
        
        assert updated is not None
        assert updated.status == "failed"
        assert updated.error == error
        assert updated.model == "claude-opus"
        assert updated.system_prompt_hash == "hash456"
