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
"""Job model for async task tracking."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

JobStatus = Literal["QUEUED", "RUNNING", "SUCCEEDED", "FAILED"]


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
        model: Optional logical model name used for this job.
        system_prompt_hash: Optional hash of the system prompt used (for tracking).
    """

    job_id: str = Field(..., description="Unique job identifier (UUID string)")
    status: JobStatus = Field(..., description="Current job status")
    description: str | None = Field(None, description="Project description for planning")
    created_at: datetime = Field(..., description="Job creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    started_at: datetime | None = Field(None, description="Timestamp when job started execution")
    finished_at: datetime | None = Field(
        None, description="Timestamp when job finished (succeeded or failed)"
    )
    result: dict | None = Field(None, description="Job result with top-level 'specs' field")
    error: dict | None = Field(None, description="Error details if job failed")
    model: str | None = Field(None, description="Logical model name used for this job")
    system_prompt: str | None = Field(None, description="System prompt used for this job")
