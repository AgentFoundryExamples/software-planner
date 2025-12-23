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
"""API route handlers for the planning service."""

import logging
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status

from app.core.config import settings
from app.models.job import Job
from app.models.request import PlanRequest
from app.models.response import PlanResponse
from app.services.planner import generate_plan
from app.services.job_store import JobStore
from app.services.store_singleton import get_job_store

logger = logging.getLogger(__name__)

router = APIRouter()


def _format_job_response(job: Job) -> dict:
    """Format a job instance into a response dictionary.
    
    Helper function to ensure consistent job response structure across endpoints.
    Per acceptance criteria: pending jobs return result=null and omit error field.
    
    Args:
        job: Job instance to format.
        
    Returns:
        Dict with job metadata in API response format.
    """
    response = {
        "job_id": job.job_id,
        "status": job.status,
        "created_at": job.created_at.isoformat(),
        "updated_at": job.updated_at.isoformat(),
        "result": None
    }
    
    # Include result for succeeded jobs
    if job.status == "succeeded" and job.result is not None:
        response["result"] = job.result
    
    # Include error for failed jobs (omit for non-failed jobs)
    if job.status == "failed" and job.error is not None:
        response["error"] = job.error
    
    return response


@router.post(
    "/plan",
    response_model=PlanResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Successfully generated plan",
            "content": {
                "application/json": {
                    "example": {
                        "specs": [
                            {
                                "purpose": "Core API Development",
                                "vision": "Build a robust and scalable REST API",
                                "must": ["Implement RESTful endpoints"],
                                "dont": ["Skip validation"],
                                "nice": ["Add rate limiting"]
                            }
                        ]
                    }
                }
            }
        },
        400: {
            "description": "Invalid request - empty, whitespace-only, or oversized description",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Validation error",
                        "status_code": 400,
                        "details": [
                            {
                                "loc": ["body", "description"],
                                "msg": "Description cannot be empty or whitespace-only",
                                "type": "value_error"
                            }
                        ]
                    }
                }
            }
        },
        422: {
            "description": "Malformed JSON or missing required fields",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Validation error",
                        "status_code": 422,
                        "details": [
                            {
                                "loc": ["body", "description"],
                                "msg": "Field required",
                                "type": "missing"
                            }
                        ]
                    }
                }
            }
        }
    },
    summary="Generate software plan",
    description="Accepts a project description and returns a structured plan with specifications"
)
def create_plan(request: PlanRequest) -> PlanResponse:
    """Generate a software plan based on the provided description.
    
    Args:
        request: PlanRequest containing the project description.
        
    Returns:
        PlanResponse with structured specifications.
        
    Raises:
        HTTPException: 400 if description is empty, whitespace-only, or exceeds byte limit.
        HTTPException: 422 if JSON is malformed or required fields are missing.
    """
    return generate_plan(request.description)


def _background_planner_worker(job_id: str, description: str, job_store: JobStore):
    """Background worker that executes the planner and updates job status.
    
    This function runs in the background after the POST /plans endpoint returns.
    It updates the job status through the lifecycle: pending -> running -> succeeded/failed.
    
    Args:
        job_id: The job identifier to track.
        description: The project description to plan.
        job_store: The job store instance for status updates.
    """
    try:
        # Execute planner with job tracking
        # The generate_plan function will update status to "running" and then "succeeded"
        generate_plan(description, job_store=job_store, job_id=job_id)
    except Exception as e:
        # Capture any exception and set failed status
        # Don't leak stack traces - only store sanitized error info
        logger.error(f"Background task for job {job_id} failed: {e}", exc_info=True)
        try:
            error_dict = {
                "error": str(e),
                "type": type(e).__name__
            }
            job_store.update_job(job_id, status="failed", error=error_dict)
        except Exception as update_exc:
            # If we can't even update the job status, log this critical failure
            # to avoid masking the original exception and losing all trace of the error.
            logger.critical(
                f"CRITICAL: Failed to update job {job_id} to 'failed' status "
                f"after planner error. Original error: {e}. "
                f"Update error: {update_exc}",
                exc_info=True
            )


@router.post(
    "/plans",
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        202: {
            "description": "Job created and accepted for processing",
            "content": {
                "application/json": {
                    "example": {
                        "job_id": "550e8400-e29b-41d4-a716-446655440000",
                        "status": "pending"
                    }
                }
            }
        },
        400: {
            "description": "Invalid request - empty, whitespace-only, or oversized description",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Validation error",
                        "status_code": 400,
                        "details": [
                            {
                                "loc": ["body", "description"],
                                "msg": "Description cannot be empty or whitespace-only",
                                "type": "value_error"
                            }
                        ]
                    }
                }
            }
        },
        422: {
            "description": "Malformed JSON or missing required fields",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Validation error",
                        "status_code": 422,
                        "details": [
                            {
                                "loc": ["body", "description"],
                                "msg": "Field required",
                                "type": "missing"
                            }
                        ]
                    }
                }
            }
        }
    },
    summary="Create async software planning job",
    description="Accepts a project description, creates a job, and returns job_id immediately. Planning executes in background."
)
def create_plan_async(
    request: PlanRequest,
    background_tasks: BackgroundTasks,
    job_store: JobStore = Depends(get_job_store)
) -> dict:
    """Create an async planning job that executes in the background.
    
    This endpoint validates the request, creates a job with 'pending' status,
    schedules background execution, and returns immediately with the job_id.
    
    Args:
        request: PlanRequest containing the project description.
        background_tasks: FastAPI background tasks manager.
        job_store: JobStore instance (injected via dependency).
        
    Returns:
        Dict with job_id and status "pending".
        
    Raises:
        HTTPException: 400 if description is empty, whitespace-only, or exceeds byte limit.
        HTTPException: 422 if JSON is malformed or required fields are missing.
    """
    # Create job in pending status
    job = job_store.create_job()
    
    # Schedule background task
    background_tasks.add_task(
        _background_planner_worker,
        job_id=job.job_id,
        description=request.description,
        job_store=job_store
    )
    
    # Return immediately with job info
    return {
        "job_id": job.job_id,
        "status": job.status
    }


@router.get(
    "/plans/{job_id}",
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Job metadata retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "job_id": "550e8400-e29b-41d4-a716-446655440000",
                        "status": "succeeded",
                        "created_at": "2025-01-01T12:00:00Z",
                        "updated_at": "2025-01-01T12:00:05Z",
                        "result": {
                            "specs": [
                                {
                                    "purpose": "Core API Development",
                                    "vision": "Build a robust REST API",
                                    "must": ["Implement endpoints"],
                                    "dont": ["Skip validation"],
                                    "nice": ["Add rate limiting"]
                                }
                            ]
                        }
                    }
                }
            }
        },
        404: {
            "description": "Job not found or expired",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Job not found",
                        "status_code": 404
                    }
                }
            }
        }
    },
    summary="Get job status and result",
    description="Retrieve metadata for a specific job including status, timestamps, and result/error when applicable"
)
def get_job_status(
    job_id: str,
    job_store: JobStore = Depends(get_job_store)
) -> dict:
    """Get the status and metadata for a specific job.
    
    Returns job metadata including job_id, status, created_at, updated_at.
    When status is 'succeeded', includes result with specs.
    When status is 'failed', includes error details.
    Pending/running jobs have result=None and no error field.
    
    Args:
        job_id: The job identifier to retrieve.
        job_store: JobStore instance (injected via dependency).
        
    Returns:
        Dict with job metadata.
        
    Raises:
        HTTPException: 404 if job not found or expired.
    """
    job = job_store.get_job(job_id)
    
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    return _format_job_response(job)


@router.get(
    "/plans",
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "List of recent jobs",
            "content": {
                "application/json": {
                    "example": {
                        "jobs": [
                            {
                                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                                "status": "succeeded",
                                "created_at": "2025-01-01T12:00:00Z",
                                "updated_at": "2025-01-01T12:00:05Z",
                                "result": {
                                    "specs": [{"purpose": "Example"}]
                                }
                            }
                        ],
                        "total": 1,
                        "limit": 100
                    }
                }
            }
        }
    },
    summary="List recent jobs",
    description="List recent jobs sorted by most recently updated. Use limit parameter to control number of results."
)
def list_jobs(
    limit: Optional[int] = Query(
        None,
        ge=1,
        description="Maximum number of jobs to return. Defaults to configured limit if not specified."
    ),
    job_store: JobStore = Depends(get_job_store)
) -> dict:
    """List recent jobs sorted by most recently updated.
    
    Returns a list of jobs with the same metadata shape as the single job endpoint.
    Jobs are sorted by updated_at in descending order (most recent first).
    
    Args:
        limit: Maximum number of jobs to return (optional).
        job_store: JobStore instance (injected via dependency).
        
    Returns:
        Dict with jobs list, total count, and applied limit.
    """
    # Apply limit constraints
    effective_limit = limit if limit is not None else settings.default_jobs_list_limit
    effective_limit = min(effective_limit, settings.max_jobs_list_limit)
    
    # Get total count before applying limit
    total_count = job_store.count_jobs()
    jobs = job_store.list_jobs(limit=effective_limit)
    
    # Format jobs with same structure as single job endpoint
    formatted_jobs = [_format_job_response(job) for job in jobs]
    
    return {
        "jobs": formatted_jobs,
        "total": total_count,
        "limit": effective_limit
    }


