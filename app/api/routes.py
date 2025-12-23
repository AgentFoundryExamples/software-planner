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

from fastapi import APIRouter, status

from app.models.request import PlanRequest
from app.models.response import PlanResponse
from app.services.planner import generate_plan

router = APIRouter()


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
