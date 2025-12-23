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
"""Planning service with LLM-based planning logic.

This module provides the main planning function that uses an LLM client
to generate software specifications based on project descriptions.
"""

import logging
from typing import Any, Optional

from app.core.config import settings
from app.models.response import PlanResponse, SpecItem
from app.services.job_store import JobStore
from app.services.llm_client import (
    BaseLLMClient,
    LLMConfigurationError,
    LLMError,
    LLMRequestError,
    LLMResponseError,
    get_default_system_prompt,
)

logger = logging.getLogger(__name__)


# Constants for response size limits
MAX_STRING_FIELD_LENGTH = 10000  # Maximum length for purpose/vision fields
MAX_ARRAY_ITEM_LENGTH = 5000     # Maximum length for items in must/dont/nice arrays


def _normalize_specs(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize LLM response to ensure specs is a list with valid structure.
    
    Handles edge cases:
    - Single spec object instead of list: wraps it in a list
    - Empty specs list: raises error (schema violation)
    - Single string values in must/dont/nice: wraps in lists
    - Whitespace in string values: strips leading/trailing whitespace
    - Oversized responses: truncates string fields to reasonable limits
    
    Args:
        data: Raw parsed JSON data from LLM.
        
    Returns:
        Normalized dictionary with specs as a list.
        
    Raises:
        LLMResponseError: If specs is empty or data cannot be normalized.
    """
    # If specs is a single object instead of a list, wrap it
    if "specs" in data and isinstance(data["specs"], dict):
        logger.info("Normalizing single spec object to list")
        data["specs"] = [data["specs"]]
    
    # Validate specs is a list
    if "specs" not in data or not isinstance(data["specs"], list):
        raise LLMResponseError("Response missing 'specs' list after normalization")
    
    # Check for empty specs (schema violation)
    if len(data["specs"]) == 0:
        raise LLMResponseError("LLM returned empty specs list (minimum one spec required)")
    
    # Normalize each spec item
    normalized_specs = []
    for idx, spec in enumerate(data["specs"]):
        if not isinstance(spec, dict):
            raise LLMResponseError(f"Spec at index {idx} is not an object")
        
        normalized_spec = {}
        
        # Normalize string fields (strip whitespace, guard against oversized)
        for field in ["purpose", "vision"]:
            if field not in spec:
                raise LLMResponseError(f"Spec at index {idx} missing required field '{field}'")
            
            value = spec[field]
            if not isinstance(value, str):
                raise LLMResponseError(f"Spec at index {idx}: field '{field}' must be a string")
            
            # Strip whitespace and guard against oversized strings
            value = value.strip()
            if len(value) > MAX_STRING_FIELD_LENGTH:
                logger.warning(
                    f"Truncating oversized {field} field",
                    extra={"spec_index": idx, "original_length": len(value)}
                )
                value = value[:MAX_STRING_FIELD_LENGTH]
            
            normalized_spec[field] = value
        
        # Normalize array fields
        for field in ["must", "dont", "nice"]:
            if field not in spec:
                raise LLMResponseError(f"Spec at index {idx} missing required field '{field}'")
            
            value = spec[field]
            
            # Wrap single strings in a list
            if isinstance(value, str):
                logger.info(
                    f"Normalizing single string to list",
                    extra={"spec_index": idx, "field": field}
                )
                value = [value]
            
            if not isinstance(value, list):
                raise LLMResponseError(
                    f"Spec at index {idx}: field '{field}' must be an array or string"
                )
            
            # Normalize each item in the array (strip whitespace, ensure strings)
            normalized_items = []
            for item_idx, item in enumerate(value):
                if not isinstance(item, str):
                    raise LLMResponseError(
                        f"Spec at index {idx}: field '{field}' item {item_idx} must be a string"
                    )
                
                item = item.strip()
                
                # Guard against oversized items
                if len(item) > MAX_ARRAY_ITEM_LENGTH:
                    logger.warning(
                        f"Truncating oversized array item",
                        extra={"spec_index": idx, "field": field, "item_index": item_idx, "original_length": len(item)}
                    )
                    item = item[:MAX_ARRAY_ITEM_LENGTH]
                
                # Only include non-empty items
                if item:
                    normalized_items.append(item)
            
            normalized_spec[field] = normalized_items
        
        # Validate that at least 'must' field has content
        # The 'must' field should contain actual requirements
        if not normalized_spec.get("must"):
            logger.warning(
                "Spec has empty 'must' field after normalization",
                extra={"spec_index": idx, "purpose": normalized_spec.get("purpose", "unknown")}
            )
        
        normalized_specs.append(normalized_spec)
    
    return {"specs": normalized_specs}


def generate_plan(
    description: str, 
    job_store: Optional[JobStore] = None, 
    job_id: Optional[str] = None, 
    llm_client: Optional[BaseLLMClient] = None,
    model: Optional[str] = None,
    system_prompt: Optional[str] = None
) -> PlanResponse:
    """Generate a software plan based on the provided description.
    
    Uses an LLM client to generate structured software specifications from
    a project description. Implements robust error handling, response
    normalization, and job lifecycle management.
    
    When called from background workers, job_store and job_id should be provided
    to record status transitions and results.
    
    Args:
        description: Project description string.
        job_store: Optional JobStore instance for recording status updates.
        job_id: Optional job ID for status tracking.
        llm_client: Optional LLM client instance. If not provided, will use
            the global singleton from store_singleton.
        model: Optional logical model name to use. If not provided, uses default.
        system_prompt: Optional custom system prompt. If not provided, uses default.
        
    Returns:
        PlanResponse containing a list of specification items.
        
    Raises:
        LLMConfigurationError: If LLM client is misconfigured.
        LLMRequestError: If LLM API request fails.
        LLMResponseError: If LLM response is invalid or cannot be parsed.
    """
    # If job tracking is enabled, validate job exists before updating
    if job_store and job_id:
        job = job_store.get_job(job_id)
        if not job:
            # Job not found - cannot track status for non-existent job
            # Clear job_id to prevent further update attempts
            logger.warning(
                "Job not found during planning",
                extra={"job_id": job_id}
            )
            job_id = None
        else:
            logger.info(
                "Starting plan generation",
                extra={"job_id": job_id, "description_length": len(description)}
            )
            job_store.update_job(job_id, status="running")
    
    try:
        # Get LLM client - if model is specified, get a client for that model
        # Otherwise use provided client or get singleton
        if llm_client is None:
            if model is not None:
                # Model override requested - get client for that specific model
                from app.services.llm_client import get_llm_client_for_model
                try:
                    llm_client = get_llm_client_for_model(
                        logical_model_id=model,
                        cache_clients=True
                    )
                    logger.info(
                        "Using model-specific LLM client",
                        extra={"model": model, "job_id": job_id or "none"}
                    )
                except LLMConfigurationError as e:
                    # Model validation error - this should have been caught in routes
                    # but handle it gracefully here as well
                    logger.error(
                        f"Model configuration error: {e}",
                        extra={"model": model, "job_id": job_id or "none"}
                    )
                    raise
            else:
                # No model override - use default singleton client
                from app.services.store_singleton import get_llm_client
                llm_client = get_llm_client()
        
        # Get system prompt - use provided override, otherwise fall back to config or default
        if system_prompt is None:
            system_prompt = settings.llm_system_prompt or get_default_system_prompt()
        
        # Call LLM to generate specs
        logger.info(
            "Calling LLM to generate specs",
            extra={
                "description_length": len(description),
                "has_custom_prompt": bool(system_prompt != get_default_system_prompt()),
                "job_id": job_id or "none",
                "model_override": model or "none",
            }
        )
        
        raw_result = llm_client.generate_specs(
            description=description,
            system_prompt=system_prompt
        )
        
        # Normalize the response to handle edge cases
        logger.debug(
            "Normalizing LLM response",
            extra={"job_id": job_id or "none", "specs_count": len(raw_result.get("specs", []))}
        )
        normalized_result = _normalize_specs(raw_result)
        
        # Validate normalized result matches PlanResponse schema
        response = PlanResponse.model_validate(normalized_result)
        
        logger.info(
            "Plan generation succeeded",
            extra={
                "job_id": job_id or "none",
                "specs_count": len(response.specs)
            }
        )
        
        # Update job with successful result if job tracking is enabled
        if job_store and job_id:
            # Convert response to dict preserving top-level 'specs'
            result_dict = response.model_dump()
            job_store.update_job(job_id, status="succeeded", result=result_dict)
        
        return response
        
    except LLMError as e:
        # Handles all specific LLM errors (Configuration, Request, Response)
        error_type_name = type(e).__name__
        error_category = error_type_name.replace('LLM', '').replace('Error', '').lower()
        error_msg = f"LLM {error_category} error: {e}"
        
        logger.error(
            f"Plan generation failed due to {error_category} error",
            extra={
                "job_id": job_id or "none",
                "error": str(e),
                "error_type": error_type_name,
            }
        )
        
        # Update job with error if job tracking is enabled
        if job_store and job_id:
            try:
                error_dict = {
                    "error": error_msg,
                    "type": error_type_name
                }
                job_store.update_job(job_id, status="failed", error=error_dict)
            except Exception as update_exc:
                logger.error(
                    f"Failed to update job status after {error_category} error",
                    extra={"job_id": job_id, "update_error": str(update_exc)}
                )
        raise
        
    except Exception as e:
        # Unexpected errors
        error_msg = f"Unexpected error during planning: {e}"
        logger.error(
            "Plan generation failed due to unexpected error",
            extra={
                "job_id": job_id or "none",
                "error": str(e),
                "error_type": type(e).__name__,
            },
            exc_info=True
        )
        
        # Update job with error if job tracking is enabled
        if job_store and job_id:
            try:
                error_dict = {
                    "error": error_msg,
                    "type": type(e).__name__
                }
                job_store.update_job(job_id, status="failed", error=error_dict)
            except Exception as update_exc:
                logger.error(
                    "Failed to update job status after unexpected error",
                    extra={"job_id": job_id, "update_error": str(update_exc)}
                )
        raise
