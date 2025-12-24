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
"""Response models for API endpoints."""

from pydantic import BaseModel, Field


class SpecItem(BaseModel):
    """Individual specification item in the plan response.

    This model represents an immutable contract for specification structure.
    Field names and types should not be modified.

    Attributes:
        purpose: High-level purpose of this specification.
        vision: Vision or goal statement.
        must: List of must-have requirements.
        dont: List of things to avoid.
        nice: List of nice-to-have features.
    """

    purpose: str = Field(..., description="High-level purpose of this specification")
    vision: str = Field(..., description="Vision or goal statement")
    must: list[str] = Field(default_factory=list, description="Must-have requirements")
    dont: list[str] = Field(default_factory=list, description="Things to avoid")
    nice: list[str] = Field(default_factory=list, description="Nice-to-have features")


class PlanResponse(BaseModel):
    """Response model for the /plan endpoint.

    This is an immutable contract - field names and types must not change.

    Attributes:
        specs: List of specification items.
    """

    specs: list[SpecItem] = Field(
        ..., min_length=1, description="List of specification items (at least one required)"
    )
