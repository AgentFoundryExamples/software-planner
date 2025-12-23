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

from app.models.response import PlanResponse, SpecItem


def generate_plan(description: str) -> PlanResponse:
    """Generate a software plan based on the provided description.
    
    This is a deterministic, synchronous function that returns hard-coded specifications.
    The function is isolated to allow for easy replacement with actual planning logic
    in the future (e.g., LLM-based generation).
    
    Args:
        description: Project description string.
        
    Returns:
        PlanResponse containing a list of specification items.
        
    Note:
        Current implementation returns static data regardless of input.
        Future versions will implement actual planning logic.
    """
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
    
    return PlanResponse(specs=spec_items)
