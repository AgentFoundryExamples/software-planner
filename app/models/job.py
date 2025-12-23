"""Job model for async task tracking."""

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


JobStatus = Literal["pending", "running", "succeeded", "failed"]


class Job(BaseModel):
    """Job model representing an asynchronous task.
    
    This model tracks the lifecycle of asynchronous planning jobs,
    including their status, timestamps, results, and any errors.
    
    Attributes:
        job_id: Unique identifier for the job (UUID string).
        status: Current status of the job.
        created_at: Timestamp when the job was created.
        updated_at: Timestamp when the job was last updated.
        result: Planning result containing specs (None until job succeeds).
        error: Error details if job failed (None otherwise).
    """
    
    job_id: str = Field(..., description="Unique job identifier (UUID string)")
    status: JobStatus = Field(..., description="Current job status")
    created_at: datetime = Field(..., description="Job creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    result: dict | None = Field(None, description="Job result with top-level 'specs' field")
    error: dict | None = Field(None, description="Error details if job failed")
