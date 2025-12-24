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
"""Standardized error response models and factory."""

from typing import Any, Optional

from pydantic import BaseModel, Field


# Standard error codes for the API
class ErrorCode:
    """Standard error codes for API responses."""

    # Validation errors (400)
    PAYLOAD_TOO_LARGE = "payload_too_large"
    INVALID_DESCRIPTION = "invalid_description"
    INVALID_MODEL = "invalid_model"
    INVALID_SYSTEM_PROMPT = "invalid_system_prompt"
    VALIDATION_ERROR = "validation_error"

    # Request format errors (422)
    INVALID_JSON = "invalid_json"
    MISSING_FIELD = "missing_field"
    INVALID_TYPE = "invalid_type"
    MALFORMED_REQUEST = "malformed_request"

    # Authentication errors (401, 403)
    MISSING_AUTH = "missing_authentication"
    INVALID_AUTH = "invalid_authentication"

    # Rate limiting (429)
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"

    # Server errors (500+)
    INTERNAL_ERROR = "internal_error"
    PLANNER_ERROR = "planner_error"
    TIMEOUT_ERROR = "timeout_error"

    # Resource errors (404)
    NOT_FOUND = "not_found"


class ErrorDetail(BaseModel):
    """Structured error detail object."""

    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[dict[str, Any]] = Field(
        None, description="Additional error context (field locations, validation details, etc.)"
    )
    request_id: Optional[str] = Field(None, description="Request ID for tracing and support")


class ErrorResponse(BaseModel):
    """Standardized error response wrapper."""

    error: ErrorDetail = Field(..., description="Error details")


def create_error_response(
    code: str,
    message: str,
    details: Optional[dict[str, Any]] = None,
    request_id: Optional[str] = None,
) -> dict[str, Any]:
    """Factory function to create standardized error responses.

    Creates error responses in the format:
    {
        "error": {
            "code": "error_code",
            "message": "Human-readable message",
            "details": {...},  # Optional
            "request_id": "uuid"  # Optional
        }
    }

    Args:
        code: Machine-readable error code from ErrorCode class.
        message: Human-readable error message.
        details: Optional additional context (field locations, validation info, etc.).
        request_id: Optional request ID for tracing.

    Returns:
        Dictionary with standardized error structure.
    """
    error_detail = {
        "code": code,
        "message": message,
    }

    if details is not None:
        error_detail["details"] = details

    if request_id is not None:
        error_detail["request_id"] = request_id

    return {"error": error_detail}


def create_validation_error(
    message: str,
    field: Optional[str] = None,
    validation_errors: Optional[list[dict[str, Any]]] = None,
    request_id: Optional[str] = None,
) -> dict[str, Any]:
    """Create a standardized validation error response.

    Args:
        message: Human-readable error message.
        field: Optional field name that failed validation.
        validation_errors: Optional list of validation error details.
        request_id: Optional request ID for tracing.

    Returns:
        Dictionary with standardized error structure.
    """
    details = {}

    if field is not None:
        details["field"] = field

    if validation_errors is not None:
        details["validation_errors"] = validation_errors

    return create_error_response(
        code=ErrorCode.VALIDATION_ERROR,
        message=message,
        details=details if details else None,
        request_id=request_id,
    )


def create_planner_error(
    message: str, error_type: Optional[str] = None, request_id: Optional[str] = None
) -> dict[str, Any]:
    """Create a standardized planner error response.

    Args:
        message: Human-readable error message (should be sanitized).
        error_type: Optional error type classification.
        request_id: Optional request ID for tracing.

    Returns:
        Dictionary with standardized error structure.
    """
    details = {}

    if error_type is not None:
        details["error_type"] = error_type

    return create_error_response(
        code=ErrorCode.PLANNER_ERROR,
        message=message,
        details=details if details else None,
        request_id=request_id,
    )
