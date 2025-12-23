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
"""Planning service with deterministic, hard-coded planning logic.

This module provides a pure Python planning function that returns static data.
It is designed to be easily replaced with actual LLM-based planning in the future.
"""

from typing import Optional

from app.models.response import PlanResponse, SpecItem
from app.services.job_store import JobStore


def generate_plan(description: str, job_store: Optional[JobStore] = None, job_id: Optional[str] = None) -> PlanResponse:
    """Generate a software plan based on the provided description.
    
    This is a deterministic, synchronous function that returns hard-coded specifications.
    The function is isolated to allow for easy replacement with actual planning logic
    in the future (e.g., LLM-based generation).
    
    When called from background workers, job_store and job_id should be provided
    to record status transitions and results.
    
    Args:
        description: Project description string.
        job_store: Optional JobStore instance for recording status updates.
        job_id: Optional job ID for status tracking.
        
    Returns:
        PlanResponse containing a list of specification items.
        
    Note:
        Current implementation returns static data regardless of input.
        Future versions will implement actual planning logic.
    """
    # Update job status to running if job tracking is enabled
    if job_store and job_id:
        job_store.update_job(job_id, status="running")
    
    try:
        # Hard-coded static response for deterministic behavior
        # This will be replaced with actual planning logic in the future
        spec_items = [
            SpecItem(
                purpose="Core API Development",
                vision="Build a robust and scalable REST API with proper error handling and validation",
                must=[
                    "Implement RESTful endpoints with proper HTTP methods",
                    "Add comprehensive input validation",
                    "Include error handling with informative messages",
                    "Write unit and integration tests"
                ],
                dont=[
                    "Skip validation on user inputs",
                    "Expose internal error details to clients",
                    "Hardcode configuration values",
                    "Ignore security best practices"
                ],
                nice=[
                    "Add API rate limiting",
                    "Include request/response logging",
                    "Implement API versioning",
                    "Add OpenAPI documentation"
                ]
            )
        ]
        
        response = PlanResponse(specs=spec_items)
        
        # Update job with successful result if job tracking is enabled
        if job_store and job_id:
            # Convert response to dict preserving top-level 'specs'
            result_dict = response.model_dump()
            job_store.update_job(job_id, status="succeeded", result=result_dict)
        
        return response
        
    except Exception as e:
        # Update job with error if job tracking is enabled
        if job_store and job_id:
            error_dict = {
                "error": str(e),
                "type": type(e).__name__
            }
            job_store.update_job(job_id, status="failed", error=error_dict)
        raise
