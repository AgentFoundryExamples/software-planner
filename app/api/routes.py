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
    }
    
    # Include model metadata if present
    if job.model is not None:
        response["model"] = job.model
    
    if job.system_prompt_hash is not None:
        response["system_prompt_hash"] = job.system_prompt_hash
    
    # Include result for succeeded jobs, otherwise null
    if job.status == "succeeded" and job.result is not None:
        response["result"] = job.result
    else:
        response["result"] = None
    
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
        request: PlanRequest containing the project description and optional model/prompt overrides.
        
    Returns:
        PlanResponse with structured specifications.
        
    Raises:
        HTTPException: 400 if description is empty, whitespace-only, exceeds byte limit,
                       or if model name is invalid/disabled.
        HTTPException: 422 if JSON is malformed or required fields are missing.
    """
    # Validate model if provided
    if request.model is not None:
        from app.services.model_registry import get_model_registry
        registry = get_model_registry()
        
        # Check if model exists in registry
        model_config = registry.get_model_config(request.model)
        if model_config is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown model '{request.model}'. Available models: {', '.join(registry.get_enabled_models().keys())}"
            )
        
        # Check if model is enabled
        if not model_config.enabled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Model '{request.model}' is disabled"
            )
    
    # Generate plan with optional overrides
    return generate_plan(
        description=request.description,
        model=request.model,
        system_prompt=request.system_prompt
    )


def _background_planner_worker(
    job_id: str, 
    description: str, 
    job_store: JobStore,
    model: Optional[str] = None,
    system_prompt: Optional[str] = None
):
    """Background worker that executes the planner and updates job status.
    
    This function runs in the background after the POST /plans endpoint returns.
    It updates the job status through the lifecycle: pending -> running -> succeeded/failed.
    
    Args:
        job_id: The job identifier to track.
        description: The project description to plan.
        job_store: The job store instance for status updates.
        model: Optional logical model name to use.
        system_prompt: Optional custom system prompt to use.
    """
    try:
        # Execute planner with job tracking and optional overrides
        # The generate_plan function will update status to "running" and then "succeeded"
        generate_plan(
            description=description, 
            job_store=job_store, 
            job_id=job_id,
            model=model,
            system_prompt=system_prompt
        )
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
    description="""Create an asynchronous planning job that executes in the background.

**Async Semantics:**
- Returns immediately with HTTP 202 Accepted
- Job starts with 'pending' status and transitions through: pending → running → succeeded/failed
- Use returned job_id to poll for status and results via GET /plans/{job_id}

**Storage Limitations:**
- Jobs are stored in-memory only for the lifetime of the process
- Jobs will be lost on server restart
- No job cancellation support

**Validation:**
- Description must be non-empty and not whitespace-only
- Maximum size: 8192 bytes (UTF-8 encoded)
"""
)
def create_plan_async(
    request: PlanRequest,
    background_tasks: BackgroundTasks,
    job_store: JobStore = Depends(get_job_store)
) -> dict:
    """Create an async planning job that executes in the background.
    
    This endpoint validates the request, creates a job with 'pending' status,
    schedules background execution, and returns immediately with the job_id.
    
    **Job Lifecycle:**
    1. Job created with status='pending'
    2. Background task starts, status transitions to 'running'
    3. On success: status='succeeded', result contains specs
    4. On failure: status='failed', error contains details
    
    **Polling:**
    Use GET /plans/{job_id} to check job status and retrieve results.
    
    **Limitations:**
    - Jobs stored in-memory only (lost on server restart)
    - No cancellation support
    - Jobs persist for process lifetime only
    
    Args:
        request: PlanRequest containing the project description and optional overrides.
        background_tasks: FastAPI background tasks manager.
        job_store: JobStore instance (injected via dependency).
        
    Returns:
        Dict with job_id and status "pending".
        
    Raises:
        HTTPException: 400 if description is empty, whitespace-only, exceeds byte limit,
                       or if model name is invalid/disabled.
        HTTPException: 422 if JSON is malformed or required fields are missing.
    """
    # Validate model if provided
    if request.model is not None:
        from app.services.model_registry import get_model_registry
        registry = get_model_registry()
        
        # Check if model exists in registry
        model_config = registry.get_model_config(request.model)
        if model_config is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown model '{request.model}'. Available models: {', '.join(registry.get_enabled_models().keys())}"
            )
        
        # Check if model is enabled
        if not model_config.enabled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Model '{request.model}' is disabled"
            )
    
    # Calculate system prompt hash if provided
    system_prompt_hash = None
    if request.system_prompt is not None:
        import hashlib
        system_prompt_hash = hashlib.sha256(request.system_prompt.encode('utf-8')).hexdigest()
    
    # Create job in pending status with metadata
    job = job_store.create_job(
        model=request.model,
        system_prompt_hash=system_prompt_hash
    )
    
    # Schedule background task with all parameters
    background_tasks.add_task(
        _background_planner_worker,
        job_id=job.job_id,
        description=request.description,
        job_store=job_store,
        model=request.model,
        system_prompt=request.system_prompt
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
                    "examples": {
                        "pending": {
                            "summary": "Pending job",
                            "value": {
                                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                                "status": "pending",
                                "created_at": "2025-01-01T12:00:00Z",
                                "updated_at": "2025-01-01T12:00:00Z",
                                "result": None
                            }
                        },
                        "running": {
                            "summary": "Running job",
                            "value": {
                                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                                "status": "running",
                                "created_at": "2025-01-01T12:00:00Z",
                                "updated_at": "2025-01-01T12:00:02Z",
                                "result": None
                            }
                        },
                        "succeeded": {
                            "summary": "Succeeded job",
                            "value": {
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
                        },
                        "failed": {
                            "summary": "Failed job",
                            "value": {
                                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                                "status": "failed",
                                "created_at": "2025-01-01T12:00:00Z",
                                "updated_at": "2025-01-01T12:00:05Z",
                                "result": None,
                                "error": {
                                    "error": "Planning failed",
                                    "type": "ValueError"
                                }
                            }
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
    description="""Retrieve metadata for a specific job including status, timestamps, and result/error when applicable.

**Status Values:**
- `pending`: Job created but not yet started
- `running`: Job is currently executing
- `succeeded`: Job completed successfully, result contains specs
- `failed`: Job failed, error contains details

**Response Fields:**
- Always present: job_id, status, created_at, updated_at
- `result`: Present with value when status='succeeded', null otherwise
- `error`: Only present when status='failed'

**HTTP Status Codes:**
- 200: Job found and metadata returned (regardless of job status)
- 404: Job not found (never existed or expired/deleted)

**Polling Strategy:**
Poll this endpoint periodically to check job completion. Jobs are stored in-memory only
and will be lost on server restart.
"""
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
    
    **Status Transitions:**
    pending → running → succeeded/failed
    
    **Result Field:**
    - null for pending/running/failed jobs
    - Contains {"specs": [...]} for succeeded jobs
    
    **Error Field:**
    - Only present for failed jobs
    - Contains error message and type
    
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
    summary="List recent jobs (debug endpoint)",
    description="""List recent jobs sorted by most recently updated. Use limit parameter to control number of results.

**Purpose:**
This is a debug/monitoring endpoint for viewing all jobs in the system.

**Features:**
- Returns jobs sorted by updated_at descending (most recent first)
- Configurable limit (default: 100, max: 1000)
- Each job has same metadata structure as GET /plans/{job_id}

**Limitations:**
- Only shows jobs in current process memory
- Jobs are lost on server restart
- Not intended for production job management
"""
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
    
    **Debug Endpoint:**
    This endpoint is intended for debugging and monitoring. It shows all jobs
    currently in memory but should not be used for production job management
    as jobs are not persisted.
    
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


