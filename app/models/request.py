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
"""Request models for API endpoints."""

from pydantic import BaseModel, Field, field_validator


class PlanRequest(BaseModel):
    """Request model for the /plan endpoint.
    
    Attributes:
        description: Project description string with validation for non-empty content
                    and maximum length constraint.
    """
    
    description: str = Field(
        ...,
        description="Non-empty project description (max 8192 bytes)",
        examples=["Build a REST API for managing tasks"]
    )
    
    @field_validator('description')
    @classmethod
    def validate_description(cls, v: str) -> str:
        """Validate description is not whitespace-only and within byte limit.
        
        Args:
            v: The description string to validate.
            
        Returns:
            The validated description string.
            
        Raises:
            ValueError: If description is whitespace-only or exceeds byte limit.
        """
        # Check if whitespace-only
        if not v or not v.strip():
            raise ValueError("Description cannot be empty or whitespace-only")
        
        # Check byte length (UTF-8 encoding)
        byte_length = len(v.encode('utf-8'))
        from app.core.config import settings
        max_bytes = settings.max_description_bytes
        
        if byte_length > max_bytes:
            raise ValueError(
                f"Description exceeds maximum length of {max_bytes} bytes "
                f"(current: {byte_length} bytes)"
            )
        
        return v
