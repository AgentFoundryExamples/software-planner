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
"""Thread-safe in-memory job storage."""

import uuid
from datetime import datetime, timezone
from threading import Lock
from typing import Dict, List, Optional

from app.models.job import Job, JobStatus


class JobStore:
    """Thread-safe in-memory storage for job metadata.
    
    This class provides atomic operations for creating, reading, updating,
    and listing jobs. All operations are protected by a threading lock to
    ensure thread safety when accessed from background workers and request
    handlers concurrently.
    
    Attributes:
        _jobs: Internal dictionary mapping job_id to Job instances.
        _lock: Threading lock for synchronizing access to _jobs.
    """
    
    def __init__(self) -> None:
        """Initialize an empty job store with a lock."""
        self._jobs: Dict[str, Job] = {}
        self._lock = Lock()
    
    def create_job(self, max_retries: int = 10) -> Job:
        """Create a new job with unique ID and pending status.
        
        Generates a unique job_id, initializes timestamps, and stores
        the job with 'pending' status. Retries UUID generation if
        duplicates are detected (highly unlikely but handles the edge case).
        
        Args:
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
                        status="pending",
                        created_at=now,
                        updated_at=now,
                        result=None,
                        error=None
                    )
                    self._jobs[job_id] = job
                    return job
            
            raise RuntimeError(
                f"Failed to generate unique job_id after {max_retries} attempts"
            )
    
    def get_job(self, job_id: str) -> Optional[Job]:
        """Retrieve a job by ID.
        
        Args:
            job_id: The job identifier to look up.
            
        Returns:
            Job instance if found, None otherwise.
        """
        with self._lock:
            return self._jobs.get(job_id)
    
    def update_job(
        self,
        job_id: str,
        status: Optional[JobStatus] = None,
        result: Optional[dict] = None,
        error: Optional[dict] = None
    ) -> Optional[Job]:
        """Update job fields atomically.
        
        Updates the specified job with new values and refreshes the
        updated_at timestamp. Only provided fields are updated.
        
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
            if result is not None:
                updated_data["result"] = result
            if error is not None:
                updated_data["error"] = error
            
            updated_job = Job(**updated_data)
            self._jobs[job_id] = updated_job
            return updated_job
    
    def list_jobs(self) -> List[Job]:
        """List all jobs in the store.
        
        Returns:
            List of all Job instances, ordered by creation time (newest first).
        """
        with self._lock:
            jobs = list(self._jobs.values())
            # Sort by created_at descending (newest first)
            jobs.sort(key=lambda j: j.created_at, reverse=True)
            return jobs
