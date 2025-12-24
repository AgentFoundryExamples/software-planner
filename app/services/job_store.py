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
"""Thread-safe in-memory job storage for testing."""

import uuid
from datetime import datetime, timezone
from threading import Lock
from typing import Dict, List, Optional

from app.models.job import Job, JobStatus


class JobStore:
    """Thread-safe in-memory storage for job metadata (test double).
    
    This class is used as a test double for JobRepository in unit tests.
    It provides atomic operations for creating, reading, updating, and listing jobs.
    
    Note: Uses threading.Lock instead of asyncio.Lock because:
    - Tests call async methods via asyncio.run(), creating new event loops
    - Some tests use ThreadPoolExecutor to test concurrent access
    - asyncio.Lock requires a single event loop and doesn't work across threads
    
    In production, use JobRepository with database-backed persistence instead.
    
    Attributes:
        _jobs: Internal dictionary mapping job_id to Job instances.
        _lock: Threading lock for synchronizing access to _jobs.
    """
    
    def __init__(self) -> None:
        """Initialize an empty job store with a lock."""
        self._jobs: Dict[str, Job] = {}
        self._lock = Lock()
    
    async def create_job(
        self,
        description: str,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        max_retries: int = 10
    ) -> Job:
        """Create a new job with unique ID and QUEUED status.
        
        Generates a unique job_id, initializes timestamps, and stores
        the job with 'QUEUED' status. Retries UUID generation if
        duplicates are detected (highly unlikely but handles the edge case).
        
        Args:
            description: Project description for planning.
            model: Optional logical model name for this job.
            system_prompt: Optional system prompt used for this job.
            max_retries: Maximum number of attempts to generate unique UUID.
            
        Returns:
            Newly created Job instance.
            
        Raises:
            RuntimeError: If unable to generate unique job_id after max_retries.
        """
        now = datetime.now(timezone.utc)
        
        with self._lock:
            for attempt in range(max_retries):
                job_id = str(uuid.uuid4())
                if job_id not in self._jobs:
                    job = Job(
                        job_id=job_id,
                        status="QUEUED",
                        description=description,
                        created_at=now,
                        updated_at=now,
                        started_at=None,
                        finished_at=None,
                        result=None,
                        error=None,
                        model=model,
                        system_prompt=system_prompt
                    )
                    self._jobs[job_id] = job
                    return job
            
            raise RuntimeError(
                f"Failed to generate unique job_id after {max_retries} attempts"
            )
    
    async def get_job(self, job_id: str) -> Optional[Job]:
        """Retrieve a job by ID.
        
        Args:
            job_id: The job identifier to look up.
            
        Returns:
            Job instance if found, None otherwise.
        """
        with self._lock:
            return self._jobs.get(job_id)

    
    async def count_jobs(self) -> int:
        """Count total number of jobs in the store.
        
        Returns:
            Total count of jobs.
        """
        with self._lock:
            return len(self._jobs)
    
    async def mark_running(self, job_id: str) -> Job:
        """Mark a job as RUNNING with started_at timestamp.
        
        Args:
            job_id: The job identifier to update.
            
        Returns:
            Updated Job instance.
            
        Raises:
            RuntimeError: If job doesn't exist.
        """
        now = datetime.now(timezone.utc)
        
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise RuntimeError(f"Job not found: {job_id}")
            
            # Create updated job
            updated_data = job.model_dump()
            updated_data["status"] = "RUNNING"
            updated_data["started_at"] = now
            updated_data["updated_at"] = now
            
            updated_job = Job(**updated_data)
            self._jobs[job_id] = updated_job
            return updated_job
    
    async def mark_succeeded(self, job_id: str, result: dict) -> Job:
        """Mark a job as SUCCEEDED with result and finished_at timestamp.
        
        Args:
            job_id: The job identifier to update.
            result: Planning result dictionary.
            
        Returns:
            Updated Job instance.
            
        Raises:
            RuntimeError: If job doesn't exist.
        """
        now = datetime.now(timezone.utc)
        
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise RuntimeError(f"Job not found: {job_id}")
            
            # Create updated job
            updated_data = job.model_dump()
            updated_data["status"] = "SUCCEEDED"
            updated_data["result"] = result
            updated_data["finished_at"] = now
            updated_data["updated_at"] = now
            
            updated_job = Job(**updated_data)
            self._jobs[job_id] = updated_job
            return updated_job
    
    async def mark_failed(self, job_id: str, error: dict) -> Job:
        """Mark a job as FAILED with error and finished_at timestamp.
        
        Args:
            job_id: The job identifier to update.
            error: Error details dictionary.
            
        Returns:
            Updated Job instance.
            
        Raises:
            RuntimeError: If job doesn't exist.
        """
        now = datetime.now(timezone.utc)
        
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise RuntimeError(f"Job not found: {job_id}")
            
            # Create updated job
            updated_data = job.model_dump()
            updated_data["status"] = "FAILED"
            updated_data["error"] = error
            # Set started_at if not already set
            if updated_data.get("started_at") is None:
                updated_data["started_at"] = now
            updated_data["finished_at"] = now
            updated_data["updated_at"] = now
            
            updated_job = Job(**updated_data)
            self._jobs[job_id] = updated_job
            return updated_job
    
    async def list_jobs(self, limit: Optional[int] = None) -> List[Job]:
        """List all jobs in the store.
        
        Args:
            limit: Maximum number of jobs to return (None for all jobs).
        
        Returns:
            List of Job instances, ordered by update time (most recently updated first).
        """
        with self._lock:
            # Create a shallow copy to avoid holding lock during sort/slice
            jobs = list(self._jobs.values())
        
        # Sort and slice outside the lock to minimize contention
        jobs.sort(key=lambda j: j.updated_at, reverse=True)
        
        if limit is not None and limit > 0:
            jobs = jobs[:limit]
        
        return jobs
    
    async def recover_stuck_jobs(self) -> int:
        """Recover jobs stuck in RUNNING state.
        
        For in-memory store, just returns 0 since jobs don't persist.
        
        Returns:
            Number of jobs recovered (always 0 for in-memory store).
        """
        return 0
    
    async def update_job(
        self,
        job_id: str,
        status: Optional[JobStatus] = None,
        result: Optional[dict] = None,
        error: Optional[dict] = None
    ) -> Optional[Job]:
        """Update job fields atomically (convenience method for tests).
        
        This method provides a simplified interface for updating job fields
        without going through the specific mark_* methods. It's primarily
        intended for testing scenarios.
        
        Args:
            job_id: The job identifier to update.
            status: New status value (if provided).
            result: New result dictionary (if provided).
            error: New error dictionary (if provided).
            
        Returns:
            Updated Job instance if found, None if job doesn't exist.
        """
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            
            # Create updated job with new timestamp
            updated_data = job.model_dump()
            updated_data["updated_at"] = datetime.now(timezone.utc)
            
            if status is not None:
                updated_data["status"] = status
                # Update timestamps based on status
                if status == "RUNNING" and updated_data.get("started_at") is None:
                    updated_data["started_at"] = updated_data["updated_at"]
                elif status in ("SUCCEEDED", "FAILED") and updated_data.get("finished_at") is None:
                    updated_data["finished_at"] = updated_data["updated_at"]
            
            if result is not None:
                updated_data["result"] = result
            if error is not None:
                updated_data["error"] = error
            
            updated_job = Job(**updated_data)
            self._jobs[job_id] = updated_job
            return updated_job
