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

import hashlib
import logging
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status

from app.api.dependencies import require_api_key
from app.core.config import settings
from app.models.job import Job
from app.models.request import PlanRequest
from app.models.response import PlanResponse
from app.services.planner import generate_plan
from app.services.job_repository import JobRepository
from app.services.store_singleton import get_job_store

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/models",
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "List of available models with metadata",
            "content": {
                "application/json": {
                    "example": {
                        "models": [
                            {
                                "logical_name": "my-gpt-model",
                                "provider": "openai",
                                "model_id": "gpt-5.1",
                                "enabled": True,
                                "timeout": 60,
                                "max_retries": 3,
                                "description": "OpenAI GPT-5.1 model for high-quality software planning",
                                "metadata": {
                                    "approximate_max_context": 128000,
                                    "supports_streaming": False
                                }
                            }
                        ]
                    }
                }
            }
        }
    },
    summary="Discover available LLM models",
    description="""List all enabled LLM models with their metadata.

**Purpose:**
This discovery endpoint allows clients to validate model availability before submitting
planning jobs and understand the capabilities and constraints of each model.

**Response Format:**
- `logical_name`: User-friendly identifier to use in POST /plans requests
- `provider`: Backend provider (openai, anthropic, google)
- `model_id`: Provider-specific model identifier
- `enabled`: Whether the model is currently available for use
- `timeout`: Request timeout in seconds
- `max_retries`: Maximum retry attempts for transient failures
- `description`: Human-readable description of the model
- `metadata`: Additional model-specific information (context window, etc.)

**Empty Response:**
Returns an empty list if no models are enabled (still returns 200 OK).

**Usage:**
Call this endpoint before submitting planning jobs to discover available models
and their constraints (e.g., timeout expectations, context limits).
"""
)
def list_models() -> dict:
    """List all enabled LLM models with metadata.
    
    This endpoint exposes the model registry to clients, allowing them to:
    - Discover which models are available
    - Understand model constraints (timeout, retries, context limits)
    - Validate model names before submitting planning jobs
    - Select appropriate models based on their characteristics
    
    **Model Discovery Flow:**
    1. Client calls GET /models to see available options
    2. Client selects a model based on requirements (timeout, provider preference, etc.)
    3. Client includes model name in POST /plans request body
    4. Client can later check model used via GET /plans/{job_id}
    
    **Metadata:**
    Each model includes approximate_max_context (token limit) and other
    provider-specific metadata to help clients make informed choices.
    
    Returns:
        Dict with list of model configurations including all metadata fields.
    """
    from app.services.model_registry import get_model_registry
    
    registry = get_model_registry()
    enabled_models = registry.get_enabled_models()
    
    # Build response with comprehensive metadata
    models_list = []
    for logical_name, config in enabled_models.items():
        # Determine approximate max context based on provider and model
        approximate_max_context = _get_approximate_max_context(config.provider, config.model_id)
        
        model_info = {
            "logical_name": logical_name,
            "provider": config.provider,
            "model_id": config.model_id,
            "enabled": config.enabled,
            "timeout": config.timeout,
            "max_retries": config.max_retries,
            "description": _get_model_description(config.provider, config.model_id),
            "metadata": {
                "approximate_max_context": approximate_max_context,
                "supports_streaming": False  # Currently no streaming support
            }
        }
        
        # Include base_url presence indicator (but not the actual URL for security)
        if config.base_url is not None:
            model_info["metadata"]["has_custom_base_url"] = True
        
        models_list.append(model_info)
    
    return {"models": models_list}


# Context window sizes by provider and model prefix
# Note: These are approximate values based on published provider documentation.
# Update this configuration as providers release new models or update context limits.
_MODEL_CONTEXT_SIZES = {
    "openai": {
        "prefixes": [
            ("gpt-5", 128000),  # GPT-5 series
            ("gpt-4-turbo", 128000),  # GPT-4 Turbo
            ("gpt-4-1106", 128000),  # GPT-4 Turbo variants
            ("gpt-4-32k", 32768),  # GPT-4 32K variant
            ("gpt-4", 8192),  # GPT-4 base (must come after more specific matches)
        ],
        "default": 16384,  # Conservative default for unknown OpenAI models
    },
    "anthropic": {
        # Anthropic uses model variant names (opus, sonnet, haiku) in various positions
        # so we use substring matching for these, but prefix matching for version numbers
        "prefixes": [
            ("claude-3", 200000),  # Claude 3 series
            ("claude-4", 200000),  # Claude 4 series
        ],
        "substrings": [
            ("sonnet", 200000),  # Sonnet variants (e.g., claude-sonnet-4.5)
            ("opus", 200000),  # Opus variants
            ("haiku", 200000),  # Haiku variants
        ],
        "default": 100000,  # Conservative default for unknown Anthropic models
    },
    "google": {
        "prefixes": [
            ("gemini-1.5", 1000000),  # Gemini 1.5+
            ("gemini-2", 1000000),  # Gemini 2.x
            ("gemini-3", 1000000),  # Gemini 3.x
        ],
        "default": 32000,  # Conservative default for older Gemini models
    },
}
_DEFAULT_CONTEXT_SIZE = 8192  # Very conservative default for unknown providers


def _get_approximate_max_context(provider: str, model_id: str) -> int:
    """Get approximate maximum context window for a model.
    
    Uses prefix matching against known model patterns for most providers.
    For Anthropic models, also checks substrings for variant names (opus, sonnet, haiku)
    which can appear in various positions in model IDs.
    
    Prefixes are checked in order, so more specific patterns should come before general ones.
    
    Args:
        provider: Provider identifier (openai, anthropic, google).
        model_id: Model identifier.
        
    Returns:
        Approximate token limit for the model's context window.
        
    Note:
        Context limits are based on published provider documentation and may
        become outdated. Update _MODEL_CONTEXT_SIZES when providers release
        new models or change context limits.
    """
    provider_lower = provider.lower()
    model_id_lower = model_id.lower()
    
    provider_info = _MODEL_CONTEXT_SIZES.get(provider_lower)
    if not provider_info:
        return _DEFAULT_CONTEXT_SIZE
    
    # Check prefixes first (more specific matching)
    for prefix, size in provider_info.get("prefixes", []):
        if model_id_lower.startswith(prefix):
            return size
    
    # For providers that need it (like Anthropic), check substrings
    # This handles model variants like "claude-sonnet-4.5" where "sonnet" is in the middle
    for substring, size in provider_info.get("substrings", []):
        if substring in model_id_lower:
            return size
            
    return provider_info["default"]


def _get_model_description(provider: str, model_id: str) -> str:
    """Get human-readable description for a model.
    
    Uses prefix matching against known model patterns. More specific patterns
    are checked before general ones to avoid false positives.
    
    Args:
        provider: Provider identifier (openai, anthropic, google).
        model_id: Model identifier.
        
    Returns:
        Human-readable description of the model.
    """
    provider_lower = provider.lower()
    model_id_lower = model_id.lower()
    
    # OpenAI models - check more specific patterns first
    if provider_lower == "openai":
        if model_id_lower.startswith("gpt-5"):
            return f"OpenAI {model_id} - Latest generation model with improved reasoning and performance"
        elif model_id_lower.startswith("gpt-4-turbo"):
            return f"OpenAI {model_id} - Fast GPT-4 variant with extended context window"
        elif model_id_lower.startswith("gpt-4"):
            return f"OpenAI {model_id} - Advanced reasoning and code generation"
        else:
            return f"OpenAI {model_id}"
    
    # Anthropic models
    elif provider_lower == "anthropic":
        if "opus" in model_id_lower:
            return f"Anthropic {model_id} - Most capable Claude model for complex tasks"
        elif "sonnet" in model_id_lower:
            return f"Anthropic {model_id} - Balanced performance and speed for most tasks"
        elif "haiku" in model_id_lower:
            return f"Anthropic {model_id} - Fast and efficient for simpler tasks"
        else:
            return f"Anthropic {model_id}"
    
    # Google models
    elif provider_lower == "google":
        if "pro" in model_id_lower:
            return f"Google {model_id} - Production-grade Gemini model with large context"
        elif "flash" in model_id_lower:
            return f"Google {model_id} - Fast Gemini variant for quick responses"
        else:
            return f"Google {model_id}"
    
    # Unknown provider
    else:
        return f"{provider} {model_id}"


def _validate_model_or_raise(model_name: str) -> None:
    """Validate model exists and is enabled, or raise HTTPException.
    
    Args:
        model_name: The logical model name to validate.
        
    Raises:
        HTTPException: 400 if model is unknown or disabled.
    """
    from app.services.model_registry import get_model_registry
    registry = get_model_registry()
    
    model_config = registry.get_model_config(model_name)
    if model_config is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown model '{model_name}'. Available models: {', '.join(registry.get_enabled_models().keys())}"
        )
    
    if not model_config.enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Model '{model_name}' is disabled"
        )


def _format_job_response(job: Job) -> dict:
    """Format a job instance into a response dictionary.
    
    Helper function to ensure consistent job response structure across endpoints.
    Per acceptance criteria: QUEUED jobs return result=null and omit error field.
    
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
    
    if job.system_prompt is not None and len(job.system_prompt) > 0:
        response["system_prompt_hash"] = hashlib.sha256(job.system_prompt.encode('utf-8')).hexdigest()
    
    # Include result for succeeded jobs, otherwise null
    if job.status == "SUCCEEDED" and job.result is not None:
        response["result"] = job.result
    else:
        response["result"] = None
    
    # Include error for failed jobs (omit for non-failed jobs)
    if job.status == "FAILED" and job.error is not None:
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
        401: {
            "description": "Missing authentication - X-API-Key header required",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Missing X-API-Key header",
                        "status_code": 401
                    }
                }
            }
        },
        403: {
            "description": "Invalid authentication - API key not recognized",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Invalid API key",
                        "status_code": 403
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
def create_plan(
    request: PlanRequest,
    api_key: str = Depends(require_api_key)
) -> PlanResponse:
    """Generate a software plan based on the provided description.
    
    Args:
        request: PlanRequest containing the project description and optional model/prompt overrides.
        api_key: Validated API key from X-API-Key header (injected via dependency).
        
    Returns:
        PlanResponse with structured specifications.
        
    Raises:
        HTTPException: 401 if X-API-Key header is missing.
        HTTPException: 403 if X-API-Key value is invalid.
        HTTPException: 400 if description is empty, whitespace-only, exceeds byte limit,
                       or if model name is invalid/disabled.
        HTTPException: 422 if JSON is malformed or required fields are missing.
    """
    # Validate model if provided
    if request.model is not None:
        _validate_model_or_raise(request.model)
    
    # Generate plan with optional overrides
    return generate_plan(
        description=request.description,
        model=request.model,
        system_prompt=request.system_prompt
    )


def _background_planner_worker(
    job_id: str, 
    description: str, 
    job_repository: JobRepository,
    model: Optional[str] = None,
    system_prompt: Optional[str] = None
):
    """Background worker that executes the planner and updates job status.
    
    This function runs in the background after the POST /plans endpoint returns.
    It updates the job status through the lifecycle: QUEUED -> RUNNING -> SUCCEEDED/FAILED.
    
    Args:
        job_id: The job identifier to track.
        description: The project description to plan.
        job_repository: The job repository instance for status updates.
        model: Optional logical model name to use.
        system_prompt: Optional custom system prompt to use.
    """
    try:
        # Execute planner with job tracking and optional overrides
        # The generate_plan function will update status to "RUNNING" and then "SUCCEEDED"
        generate_plan(
            description=description, 
            job_repository=job_repository, 
            job_id=job_id,
            model=model,
            system_prompt=system_prompt
        )
    except Exception as e:
        # Capture any exception and set failed status
        # Don't leak stack traces - only store sanitized error info
        logger.error(f"Background task for job {job_id} failed: {e}", exc_info=True)
        try:
            import asyncio
            error_dict = {
                "error": str(e),
                "type": type(e).__name__
            }
            asyncio.run(job_repository.mark_failed(job_id, error_dict))
        except Exception as update_exc:
            # If we can't even update the job status, log this critical failure
            # to avoid masking the original exception and losing all trace of the error.
            logger.critical(
                f"CRITICAL: Failed to update job {job_id} to 'FAILED' status "
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
                        "status": "QUEUED"
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
        401: {
            "description": "Missing authentication - X-API-Key header required",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Missing X-API-Key header",
                        "status_code": 401
                    }
                }
            }
        },
        403: {
            "description": "Invalid authentication - API key not recognized",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Invalid API key",
                        "status_code": 403
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
- Job starts with 'QUEUED' status and transitions through: QUEUED → RUNNING → SUCCEEDED/FAILED
- Use returned job_id to poll for status and results via GET /plans/{job_id}

**Storage:**
- Jobs are stored in PostgreSQL database and persist across server restarts
- Stuck jobs (in RUNNING state during restart) are automatically marked as FAILED on startup

**Validation:**
- Description must be non-empty and not whitespace-only
- Maximum size: 8192 bytes (UTF-8 encoded)
"""
)
async def create_plan_async(
    request: PlanRequest,
    background_tasks: BackgroundTasks,
    job_repository: JobRepository = Depends(get_job_store),
    api_key: str = Depends(require_api_key)
) -> dict:
    """Create an async planning job that executes in the background.
    
    This endpoint validates the request, creates a job with 'QUEUED' status,
    schedules background execution, and returns immediately with the job_id.
    
    **Job Lifecycle:**
    1. Job created with status='QUEUED'
    2. Background task starts, status transitions to 'RUNNING'
    3. On success: status='SUCCEEDED', result contains specs
    4. On failure: status='FAILED', error contains details
    
    **Polling:**
    Use GET /plans/{job_id} to check job status and retrieve results.
    
    **Persistence:**
    - Jobs stored in PostgreSQL database
    - Jobs persist across server restarts
    - No cancellation support
    
    Args:
        request: PlanRequest containing the project description and optional overrides.
        background_tasks: FastAPI background tasks manager.
        job_repository: JobRepository instance (injected via dependency).
        api_key: Validated API key from X-API-Key header (injected via dependency).
        
    Returns:
        Dict with job_id and status "QUEUED".
        
    Raises:
        HTTPException: 401 if X-API-Key header is missing.
        HTTPException: 403 if X-API-Key value is invalid.
        HTTPException: 400 if description is empty, whitespace-only, exceeds byte limit,
                       or if model name is invalid/disabled.
        HTTPException: 422 if JSON is malformed or required fields are missing.
    """
    # Validate model if provided
    if request.model is not None:
        _validate_model_or_raise(request.model)
    
    # Create job in QUEUED status with metadata
    job = await job_repository.create_job(
        description=request.description,
        model=request.model,
        system_prompt=request.system_prompt
    )
    
    # Schedule background task with all parameters
    background_tasks.add_task(
        _background_planner_worker,
        job_id=job.job_id,
        description=request.description,
        job_repository=job_repository,
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
                        "queued": {
                            "summary": "Queued job",
                            "value": {
                                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                                "status": "QUEUED",
                                "created_at": "2025-01-01T12:00:00Z",
                                "updated_at": "2025-01-01T12:00:00Z",
                                "result": None
                            }
                        },
                        "running": {
                            "summary": "Running job",
                            "value": {
                                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                                "status": "RUNNING",
                                "created_at": "2025-01-01T12:00:00Z",
                                "updated_at": "2025-01-01T12:00:02Z",
                                "result": None
                            }
                        },
                        "succeeded": {
                            "summary": "Succeeded job",
                            "value": {
                                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                                "status": "SUCCEEDED",
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
                                "status": "FAILED",
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
- `QUEUED`: Job created but not yet started
- `RUNNING`: Job is currently executing
- `SUCCEEDED`: Job completed successfully, result contains specs
- `FAILED`: Job failed, error contains details

**Response Fields:**
- Always present: job_id, status, created_at, updated_at
- `result`: Present with value when status='SUCCEEDED', null otherwise
- `error`: Only present when status='FAILED'

**HTTP Status Codes:**
- 200: Job found and metadata returned (regardless of job status)
- 404: Job not found (never existed or expired/deleted)

**Polling Strategy:**
Poll this endpoint periodically to check job completion. Jobs are persisted in the database
and will survive server restarts.
"""
)
async def get_job_status(
    job_id: str,
    job_repository: JobRepository = Depends(get_job_store)
) -> dict:
    """Get the status and metadata for a specific job.
    
    Returns job metadata including job_id, status, created_at, updated_at.
    When status is 'SUCCEEDED', includes result with specs.
    When status is 'FAILED', includes error details.
    QUEUED/RUNNING jobs have result=None and no error field.
    
    **Status Transitions:**
    QUEUED → RUNNING → SUCCEEDED/FAILED
    
    **Result Field:**
    - null for QUEUED/RUNNING/FAILED jobs
    - Contains {"specs": [...]} for SUCCEEDED jobs
    
    **Error Field:**
    - Only present for FAILED jobs
    - Contains error message and type
    
    Args:
        job_id: The job identifier to retrieve.
        job_repository: JobRepository instance (injected via dependency).
        
    Returns:
        Dict with job metadata.
        
    Raises:
        HTTPException: 404 if job not found or expired.
    """
    job = await job_repository.get_job(job_id)
    
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
                                "status": "SUCCEEDED",
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

**Persistence:**
- Shows all jobs stored in the database
- Jobs persist across server restarts
"""
)
async def list_jobs(
    limit: Optional[int] = Query(
        None,
        ge=1,
        description="Maximum number of jobs to return. Defaults to configured limit if not specified."
    ),
    job_repository: JobRepository = Depends(get_job_store)
) -> dict:
    """List recent jobs sorted by most recently updated.
    
    Returns a list of jobs with the same metadata shape as the single job endpoint.
    Jobs are sorted by updated_at in descending order (most recent first).
    
    **Debug Endpoint:**
    This endpoint is intended for debugging and monitoring. It shows all jobs
    currently in the database.
    
    Args:
        limit: Maximum number of jobs to return (optional).
        job_repository: JobRepository instance (injected via dependency).
        
    Returns:
        Dict with jobs list, total count, and applied limit.
    """
    # Apply limit constraints
    effective_limit = limit if limit is not None else settings.default_jobs_list_limit
    effective_limit = min(effective_limit, settings.max_jobs_list_limit)
    
    # Get total count before applying limit
    total_count = await job_repository.count_jobs()
    jobs = await job_repository.list_jobs(limit=effective_limit)
    
    # Format jobs with same structure as single job endpoint
    formatted_jobs = [_format_job_response(job) for job in jobs]
    
    return {
        "jobs": formatted_jobs,
        "total": total_count,
        "limit": effective_limit
    }


