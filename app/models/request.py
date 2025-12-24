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

from app.core.config import settings
from app.utils.sanitization import (
    has_control_characters,
    validate_description_content,
    validate_description_length,
    validate_string_not_empty
)


class PlanRequest(BaseModel):
    """Request model for the /plan endpoint.
    
    Attributes:
        description: Project description string with validation for non-empty content
                    and maximum length constraint.
        model: Optional logical model name to use for this request. Must be enabled in 
               the model registry. If omitted, uses the configured default model.
        system_prompt: Optional custom system prompt to override the default. Must not 
                      exceed max_system_prompt_bytes (32768 bytes). If omitted, uses the
                      configured default system prompt.
    """
    
    description: str = Field(
        ...,
        description="Non-empty project description (max 8192 bytes)",
        examples=["Build a REST API for managing tasks"]
    )
    
    model: str | None = Field(
        None,
        description=(
            "Optional logical model name (e.g., 'gpt-4-turbo', 'claude-opus'). "
            "Must match an enabled model in the registry. Defaults to configured default model."
        ),
        examples=["gpt-4-turbo", "claude-opus"]
    )
    
    system_prompt: str | None = Field(
        None,
        description=(
            "Optional custom system prompt to override the default (max 32768 bytes). "
            "Used to customize the planning behavior for this request only."
        ),
        examples=["You are a software planning assistant specializing in microservices..."]
    )
    
    @field_validator('description')
    @classmethod
    def validate_description(cls, v: str) -> str:
        """Validate description is not whitespace-only, within byte limit, and has no control chars.
        
        Args:
            v: The description string to validate.
            
        Returns:
            The validated description string.
            
        Raises:
            ValueError: If description is whitespace-only, exceeds byte limit, or contains control chars.
        """
        # Check if empty or whitespace-only
        is_valid, error_msg = validate_string_not_empty(v, "Description")
        if not is_valid:
            raise ValueError(error_msg)
        
        # Check for control characters
        is_valid, error_msg = validate_description_content(v)
        if not is_valid:
            raise ValueError(error_msg)
        
        # Check byte length (UTF-8 encoding)
        max_bytes = settings.max_description_bytes
        is_valid, error_msg = validate_description_length(v, max_bytes)
        if not is_valid:
            raise ValueError(error_msg)
        
        return v
    
    @field_validator('model')
    @classmethod
    def validate_model(cls, v: str | None) -> str | None:
        """Validate model name if provided.
        
        Args:
            v: The model name to validate, or None.
            
        Returns:
            The validated model name, or None if not provided.
            
        Raises:
            ValueError: If model name is empty or whitespace-only.
        """
        if v is not None:
            # Check if empty or whitespace-only
            stripped_v = v.strip()
            if not stripped_v:
                raise ValueError("Model name cannot be empty or whitespace-only")
            return stripped_v
        
        return v
    
    @field_validator('system_prompt')
    @classmethod
    def validate_system_prompt(cls, v: str | None) -> str | None:
        """Validate system prompt is within byte limit if provided.
        
        Args:
            v: The system prompt to validate, or None.
            
        Returns:
            The validated system prompt, or None if not provided.
            
        Raises:
            ValueError: If system prompt exceeds byte limit or is whitespace-only.
        """
        if v is not None:
            # Check if whitespace-only
            if not v.strip():
                raise ValueError("System prompt cannot be whitespace-only")
            
            # Check byte length (UTF-8 encoding)
            byte_length = len(v.encode('utf-8'))
            max_bytes = settings.max_system_prompt_bytes
            
            if byte_length > max_bytes:
                raise ValueError(
                    f"System prompt exceeds maximum length of {max_bytes} bytes "
                    f"(current: {byte_length} bytes)"
                )
        
        return v
