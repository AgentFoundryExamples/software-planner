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
"""Database-backed job repository with lifecycle management."""

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.exc import IntegrityError, DBAPIError

from app.models.job import Job, JobStatus
from app.services.db.connection import get_db_engine
from app.services.metrics import get_metrics_collector
from app.utils.logging_helpers import log_job_transition

logger = logging.getLogger(__name__)


class JobRepositoryError(Exception):
    """Base exception for job repository errors."""
    pass


class JobNotFoundError(JobRepositoryError):
    """Exception raised when a job is not found."""
    pass


class JobTransitionError(JobRepositoryError):
    """Exception raised when an invalid status transition is attempted."""
    pass


class JobRepository:
    """Database-backed repository for job persistence and lifecycle management.
    
    This repository provides atomic CRUD operations and enforces valid lifecycle
    transitions for jobs. All operations use transactions and row locking to
    ensure consistency under concurrent access.
    
    Lifecycle transitions enforced:
    - QUEUED -> RUNNING (mark_running)
    - RUNNING -> SUCCEEDED (mark_succeeded)
    - RUNNING -> FAILED (mark_failed)
    - QUEUED -> FAILED (mark_failed, for startup recovery)
    
    Attributes:
        engine: SQLAlchemy async engine for database operations.
    """
    
    def __init__(self, engine: Optional[AsyncEngine] = None):
        """Initialize the job repository.
        
        Args:
            engine: Optional AsyncEngine instance. If not provided, uses default from connection module.
        """
        self.engine = engine or get_db_engine()
    
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
            JobRepositoryError: If unable to generate unique job_id after max_retries.
            JobRepositoryError: If database operation fails.
        """
        now = datetime.now(timezone.utc)
        
        for attempt in range(max_retries):
            job_id = str(uuid.uuid4())
            
            try:
                async with self.engine.begin() as conn:
                    # Try to insert the job
                    await conn.execute(
                        text("""
                            INSERT INTO jobs (
                                job_id, status, description, model, system_prompt,
                                result, error, created_at, updated_at, started_at, finished_at
                            ) VALUES (
                                :job_id, :status, :description, :model, :system_prompt,
                                :result, :error, :created_at, :updated_at, :started_at, :finished_at
                            )
                        """),
                        {
                            "job_id": job_id,
                            "status": "QUEUED",
                            "description": description,
                            "model": model,
                            "system_prompt": system_prompt,
                            "result": None,
                            "error": None,
                            "created_at": now,
                            "updated_at": now,
                            "started_at": None,
                            "finished_at": None,
                        }
                    )
                
                # Job created successfully
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
                
                logger.info(
                    "Job created successfully",
                    extra={"job_id": job_id, "model": model}
                )
                
                # Record metrics and structured logging
                metrics = get_metrics_collector()
                metrics.record_job_status("QUEUED")
                
                # Log structured transition
                log_job_transition(
                    logger=logger,
                    job_id=job_id,
                    from_status=None,
                    to_status="QUEUED",
                    model=model
                )
                
                return job
                
            except IntegrityError as e:
                # Check if this is a primary key violation (duplicate job_id)
                # PostgreSQL error code 23505 is unique_violation
                # We check both the error code and the constraint name for robustness
                orig_exception = getattr(e, 'orig', None)
                is_duplicate = False
                
                if orig_exception:
                    # Check pgcode if available (asyncpg provides this)
                    pgcode = getattr(orig_exception, 'pgcode', None)
                    if pgcode == '23505':  # unique_violation
                        is_duplicate = True
                    # Also check constraint name if available
                    constraint = getattr(orig_exception, 'constraint_name', '')
                    if constraint and 'job_id' in constraint.lower():
                        is_duplicate = True
                
                # Fallback to string matching if error details not available
                if not is_duplicate:
                    error_str = str(e).lower()
                    if ("duplicate key" in error_str or "unique constraint" in error_str) and "job_id" in error_str:
                        is_duplicate = True
                
                if is_duplicate:
                    logger.warning(
                        f"UUID collision detected on attempt {attempt + 1}, retrying",
                        extra={"job_id": job_id, "attempt": attempt + 1}
                    )
                    continue
                else:
                    # Other integrity error
                    logger.error(
                        "Database integrity error creating job",
                        extra={"error": str(e)},
                        exc_info=True
                    )
                    raise JobRepositoryError(f"Failed to create job: {e}")
            
            except Exception as e:
                logger.error(
                    "Unexpected error creating job",
                    extra={"error": str(e), "error_type": type(e).__name__},
                    exc_info=True
                )
                raise JobRepositoryError(f"Failed to create job: {e}")
        
        # Max retries exhausted
        raise JobRepositoryError(
            f"Failed to generate unique job_id after {max_retries} attempts"
        )
    
    async def get_job(self, job_id: str) -> Optional[Job]:
        """Retrieve a job by ID.
        
        Args:
            job_id: The job identifier to look up.
            
        Returns:
            Job instance if found, None otherwise.
            
        Raises:
            JobRepositoryError: If database operation fails.
        """
        try:
            async with self.engine.connect() as conn:
                result = await conn.execute(
                    text("""
                        SELECT job_id, status, description, model, system_prompt,
                               result, error, created_at, updated_at, started_at, finished_at
                        FROM jobs
                        WHERE job_id = :job_id
                    """),
                    {"job_id": job_id}
                )
                
                row = result.fetchone()
                
                if row is None:
                    return None
                
                # Parse JSON fields
                result_data = json.loads(row.result) if row.result else None
                error_data = json.loads(row.error) if row.error else None
                
                return Job(
                    job_id=row.job_id,
                    status=row.status,
                    description=row.description,
                    created_at=row.created_at,
                    updated_at=row.updated_at,
                    started_at=row.started_at,
                    finished_at=row.finished_at,
                    result=result_data,
                    error=error_data,
                    model=row.model,
                    system_prompt=row.system_prompt
                )
        
        except Exception as e:
            logger.error(
                "Error retrieving job",
                extra={"job_id": job_id, "error": str(e), "error_type": type(e).__name__},
                exc_info=True
            )
            raise JobRepositoryError(f"Failed to retrieve job: {e}")
    
    async def mark_running(self, job_id: str) -> Job:
        """Mark a job as RUNNING with started_at timestamp.
        
        Enforces valid transition: only QUEUED jobs can be marked RUNNING.
        Uses row locking to prevent concurrent transitions.
        
        Args:
            job_id: The job identifier to update.
            
        Returns:
            Updated Job instance.
            
        Raises:
            JobNotFoundError: If job doesn't exist.
            JobTransitionError: If job is not in QUEUED status.
            JobRepositoryError: If database operation fails.
        """
        now = datetime.now(timezone.utc)
        
        try:
            async with self.engine.begin() as conn:
                # Lock the row for update
                result = await conn.execute(
                    text("""
                        SELECT status
                        FROM jobs
                        WHERE job_id = :job_id
                        FOR UPDATE
                    """),
                    {"job_id": job_id}
                )
                
                row = result.fetchone()
                
                if row is None:
                    raise JobNotFoundError(f"Job not found: {job_id}")
                
                current_status = row.status
                
                # Enforce valid transition
                if current_status != "QUEUED":
                    raise JobTransitionError(
                        f"Cannot transition from {current_status} to RUNNING. "
                        f"Only QUEUED jobs can be marked RUNNING."
                    )
                
                # Update to RUNNING
                await conn.execute(
                    text("""
                        UPDATE jobs
                        SET status = :status,
                            started_at = :started_at,
                            updated_at = :updated_at
                        WHERE job_id = :job_id
                    """),
                    {
                        "job_id": job_id,
                        "status": "RUNNING",
                        "started_at": now,
                        "updated_at": now
                    }
                )
            
            # Fetch and return updated job
            updated_job = await self.get_job(job_id)
            
            if updated_job is None:
                raise JobRepositoryError(f"Job disappeared after update: {job_id}")
            
            logger.info(
                "Job marked as RUNNING",
                extra={"job_id": job_id}
            )
            
            # Record metrics and structured logging
            metrics = get_metrics_collector()
            metrics.record_job_status("RUNNING")
            metrics.increment_jobs_in_progress()
            
            # Log structured transition
            log_job_transition(
                logger=logger,
                job_id=job_id,
                from_status="QUEUED",
                to_status="RUNNING"
            )
            
            return updated_job
        
        except (JobNotFoundError, JobTransitionError):
            # Re-raise domain exceptions as-is
            raise
        
        except Exception as e:
            logger.error(
                "Error marking job as RUNNING",
                extra={"job_id": job_id, "error": str(e), "error_type": type(e).__name__},
                exc_info=True
            )
            raise JobRepositoryError(f"Failed to mark job as RUNNING: {e}")
    
    async def mark_succeeded(self, job_id: str, result: dict) -> Job:
        """Mark a job as SUCCEEDED with result and finished_at timestamp.
        
        Enforces valid transition: only RUNNING jobs can be marked SUCCEEDED.
        Uses row locking to prevent concurrent transitions.
        
        Args:
            job_id: The job identifier to update.
            result: Planning result dictionary with top-level 'specs' field.
            
        Returns:
            Updated Job instance.
            
        Raises:
            JobNotFoundError: If job doesn't exist.
            JobTransitionError: If job is not in RUNNING status.
            JobRepositoryError: If database operation fails.
        """
        now = datetime.now(timezone.utc)
        
        try:
            # Serialize result to JSON
            result_json = json.dumps(result)
            
            async with self.engine.begin() as conn:
                # Lock the row for update
                result_row = await conn.execute(
                    text("""
                        SELECT status
                        FROM jobs
                        WHERE job_id = :job_id
                        FOR UPDATE
                    """),
                    {"job_id": job_id}
                )
                
                row = result_row.fetchone()
                
                if row is None:
                    raise JobNotFoundError(f"Job not found: {job_id}")
                
                current_status = row.status
                
                # Enforce valid transition
                if current_status != "RUNNING":
                    raise JobTransitionError(
                        f"Cannot transition from {current_status} to SUCCEEDED. "
                        f"Only RUNNING jobs can be marked SUCCEEDED."
                    )
                
                # Update to SUCCEEDED
                await conn.execute(
                    text("""
                        UPDATE jobs
                        SET status = :status,
                            result = :result,
                            finished_at = :finished_at,
                            updated_at = :updated_at
                        WHERE job_id = :job_id
                    """),
                    {
                        "job_id": job_id,
                        "status": "SUCCEEDED",
                        "result": result_json,
                        "finished_at": now,
                        "updated_at": now
                    }
                )
            
            # Fetch and return updated job
            updated_job = await self.get_job(job_id)
            
            if updated_job is None:
                raise JobRepositoryError(f"Job disappeared after update: {job_id}")
            
            logger.info(
                "Job marked as SUCCEEDED",
                extra={"job_id": job_id}
            )
            
            # Record metrics and structured logging
            metrics = get_metrics_collector()
            metrics.record_job_status("SUCCEEDED")
            metrics.decrement_jobs_in_progress()
            
            # Calculate and record job duration
            if updated_job.started_at and updated_job.finished_at:
                duration = (updated_job.finished_at - updated_job.started_at).total_seconds()
                metrics.record_job_duration("SUCCEEDED", duration)
            
            # Log structured transition
            log_job_transition(
                logger=logger,
                job_id=job_id,
                from_status="RUNNING",
                to_status="SUCCEEDED"
            )
            
            return updated_job
        
        except (JobNotFoundError, JobTransitionError):
            # Re-raise domain exceptions as-is
            raise
        
        except Exception as e:
            logger.error(
                "Error marking job as SUCCEEDED",
                extra={"job_id": job_id, "error": str(e), "error_type": type(e).__name__},
                exc_info=True
            )
            raise JobRepositoryError(f"Failed to mark job as SUCCEEDED: {e}")
    
    async def mark_failed(self, job_id: str, error: dict) -> Job:
        """Mark a job as FAILED with error and finished_at timestamp.
        
        Enforces valid transition: only QUEUED or RUNNING jobs can be marked FAILED.
        Uses row locking to prevent concurrent transitions.
        
        Args:
            job_id: The job identifier to update.
            error: Error details dictionary.
            
        Returns:
            Updated Job instance.
            
        Raises:
            JobNotFoundError: If job doesn't exist.
            JobTransitionError: If job is already in terminal state.
            JobRepositoryError: If database operation fails.
        """
        now = datetime.now(timezone.utc)
        
        try:
            # Serialize error to JSON
            error_json = json.dumps(error)
            
            async with self.engine.begin() as conn:
                # Lock the row for update
                result = await conn.execute(
                    text("""
                        SELECT status, started_at
                        FROM jobs
                        WHERE job_id = :job_id
                        FOR UPDATE
                    """),
                    {"job_id": job_id}
                )
                
                row = result.fetchone()
                
                if row is None:
                    raise JobNotFoundError(f"Job not found: {job_id}")
                
                current_status = row.status
                started_at = row.started_at
                
                # Enforce valid transition
                if current_status not in ("QUEUED", "RUNNING"):
                    raise JobTransitionError(
                        f"Cannot transition from {current_status} to FAILED. "
                        f"Only QUEUED or RUNNING jobs can be marked FAILED."
                    )
                
                # If job was never started, set started_at to now for consistency
                if started_at is None:
                    started_at = now
                
                # Update to FAILED
                await conn.execute(
                    text("""
                        UPDATE jobs
                        SET status = :status,
                            error = :error,
                            started_at = :started_at,
                            finished_at = :finished_at,
                            updated_at = :updated_at
                        WHERE job_id = :job_id
                    """),
                    {
                        "job_id": job_id,
                        "status": "FAILED",
                        "error": error_json,
                        "started_at": started_at,
                        "finished_at": now,
                        "updated_at": now
                    }
                )
            
            # Fetch and return updated job
            updated_job = await self.get_job(job_id)
            
            if updated_job is None:
                raise JobRepositoryError(f"Job disappeared after update: {job_id}")
            
            logger.info(
                "Job marked as FAILED",
                extra={"job_id": job_id, "error_type": error.get("type")}
            )
            
            # Record metrics and structured logging
            metrics = get_metrics_collector()
            metrics.record_job_status("FAILED")
            
            # Decrement in-progress counter only if was RUNNING
            if current_status == "RUNNING":
                metrics.decrement_jobs_in_progress()
            
            # Calculate and record job duration if started
            if updated_job.started_at and updated_job.finished_at:
                duration = (updated_job.finished_at - updated_job.started_at).total_seconds()
                metrics.record_job_duration("FAILED", duration)
            
            # Log structured transition
            log_job_transition(
                logger=logger,
                job_id=job_id,
                from_status=current_status,
                to_status="FAILED",
                error_type=error.get("type")
            )
            
            return updated_job
        
        except (JobNotFoundError, JobTransitionError):
            # Re-raise domain exceptions as-is
            raise
        
        except Exception as e:
            logger.error(
                "Error marking job as FAILED",
                extra={"job_id": job_id, "error": str(e), "error_type": type(e).__name__},
                exc_info=True
            )
            raise JobRepositoryError(f"Failed to mark job as FAILED: {e}")
    
    async def list_jobs(self, limit: Optional[int] = None) -> List[Job]:
        """List all jobs in the repository.
        
        Args:
            limit: Maximum number of jobs to return (None for all jobs).
        
        Returns:
            List of Job instances, ordered by update time (most recently updated first).
            
        Raises:
            JobRepositoryError: If database operation fails.
        """
        try:
            async with self.engine.connect() as conn:
                # Build query with parameterized limit
                query = """
                    SELECT job_id, status, description, model, system_prompt,
                           result, error, created_at, updated_at, started_at, finished_at
                    FROM jobs
                    ORDER BY updated_at DESC
                """
                
                params = {}
                if limit is not None and limit > 0:
                    query += " LIMIT :limit"
                    params["limit"] = limit
                
                result = await conn.execute(text(query), params)
                
                jobs = []
                for row in result:
                    # Parse JSON fields
                    result_data = json.loads(row.result) if row.result else None
                    error_data = json.loads(row.error) if row.error else None
                    
                    job = Job(
                        job_id=row.job_id,
                        status=row.status,
                        description=row.description,
                        created_at=row.created_at,
                        updated_at=row.updated_at,
                        started_at=row.started_at,
                        finished_at=row.finished_at,
                        result=result_data,
                        error=error_data,
                        model=row.model,
                        system_prompt=row.system_prompt
                    )
                    jobs.append(job)
                
                return jobs
        
        except Exception as e:
            logger.error(
                "Error listing jobs",
                extra={"error": str(e), "error_type": type(e).__name__},
                exc_info=True
            )
            raise JobRepositoryError(f"Failed to list jobs: {e}")
    
    async def count_jobs(self) -> int:
        """Count total number of jobs in the repository.
        
        Returns:
            Total count of jobs.
            
        Raises:
            JobRepositoryError: If database operation fails.
        """
        try:
            async with self.engine.connect() as conn:
                result = await conn.execute(text("SELECT COUNT(*) as count FROM jobs"))
                row = result.fetchone()
                return row.count if row else 0
        
        except Exception as e:
            logger.error(
                "Error counting jobs",
                extra={"error": str(e), "error_type": type(e).__name__},
                exc_info=True
            )
            raise JobRepositoryError(f"Failed to count jobs: {e}")
    
    async def recover_stuck_jobs(self) -> int:
        """Recover jobs stuck in RUNNING state after restart.
        
        Marks all RUNNING jobs as FAILED with a restart recovery message.
        This should be called during application startup to handle jobs that
        were interrupted by server restart.
        
        Returns:
            Number of jobs that were recovered (marked as FAILED).
            
        Raises:
            JobRepositoryError: If database operation fails.
        """
        now = datetime.now(timezone.utc)
        error = {
            "error": "Job interrupted by server restart",
            "type": "RestartRecoveryError"
        }
        error_json = json.dumps(error)
        
        try:
            async with self.engine.begin() as conn:
                # Atomically update all RUNNING jobs to FAILED
                result = await conn.execute(
                    text("""
                        UPDATE jobs
                        SET status = :status,
                            error = :error,
                            started_at = COALESCE(started_at, :now),
                            finished_at = :now,
                            updated_at = :now
                        WHERE status = 'RUNNING'
                    """),
                    {
                        "status": "FAILED",
                        "error": error_json,
                        "now": now,
                    }
                )
                
                recovered_count = result.rowcount
                
                if recovered_count > 0:
                    logger.warning(
                        f"Startup recovery completed: {recovered_count} jobs marked as FAILED",
                        extra={"recovered_count": recovered_count}
                    )
                else:
                    logger.info("No stuck jobs found during startup recovery")
                
                return recovered_count
        
        except Exception as e:
            logger.error(
                "Error recovering stuck jobs",
                extra={"error": str(e), "error_type": type(e).__name__},
                exc_info=True
            )
            raise JobRepositoryError(f"Failed to recover stuck jobs: {e}")
