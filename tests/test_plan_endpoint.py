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
"""Tests for the /plan endpoint."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


class TestPlanEndpointHappyPath:
    """Test cases for successful /plan endpoint requests."""
    
    def test_plan_endpoint_with_valid_description(self, client):
        """Test POST /plan with a valid description returns expected response structure."""
        response = client.post(
            "/api/v1/plan",
            json={"description": "Build a REST API for managing tasks"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify top-level structure
        assert "specs" in data
        assert isinstance(data["specs"], list)
        assert len(data["specs"]) >= 1
        
        # Verify first spec item has required fields
        spec = data["specs"][0]
        assert "purpose" in spec
        assert "vision" in spec
        assert "must" in spec
        assert "dont" in spec
        assert "nice" in spec
        
        # Verify field types
        assert isinstance(spec["purpose"], str)
        assert isinstance(spec["vision"], str)
        assert isinstance(spec["must"], list)
        assert isinstance(spec["dont"], list)
        assert isinstance(spec["nice"], list)
        
    def test_plan_endpoint_returns_hard_coded_response(self, client):
        """Test that /plan returns deterministic hard-coded response."""
        # Make two requests with different descriptions
        response1 = client.post(
            "/api/v1/plan",
            json={"description": "Build a mobile app"}
        )
        response2 = client.post(
            "/api/v1/plan",
            json={"description": "Create a web service"}
        )
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        
        # Both should return the same hard-coded response
        assert response1.json() == response2.json()
    
    def test_plan_endpoint_at_max_length_boundary(self, client):
        """Test that descriptions exactly at max length boundary succeed."""
        max_bytes = settings.max_description_bytes
        
        # Create a description that's exactly at the boundary
        # Use simple ASCII characters (1 byte each)
        description = "a" * max_bytes
        
        response = client.post(
            "/api/v1/plan",
            json={"description": description}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "specs" in data
        
    def test_plan_endpoint_with_unicode_characters(self, client):
        """Test that descriptions with Unicode characters are handled correctly."""
        description = "Build an API with émojis 🚀 and spëcial çhars"
        
        response = client.post(
            "/api/v1/plan",
            json={"description": description}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "specs" in data
        
    def test_plan_endpoint_response_contract(self, client):
        """Test that response strictly matches the contract."""
        response = client.post(
            "/api/v1/plan",
            json={"description": "Test project"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Contract check: must have exactly "specs" key at top level
        assert list(data.keys()) == ["specs"]
        
        # Contract check: each spec must have exactly these fields
        for spec in data["specs"]:
            assert set(spec.keys()) == {"purpose", "vision", "must", "dont", "nice"}


class TestPlanEndpointValidationErrors:
    """Test cases for validation error scenarios."""
    
    def test_plan_endpoint_with_empty_description(self, client):
        """Test that empty descriptions are rejected with 400."""
        response = client.post(
            "/api/v1/plan",
            json={"description": ""}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "error" in data
        assert "status_code" in data
        assert data["status_code"] == 400
        assert "details" in data
        
    def test_plan_endpoint_with_whitespace_only_description(self, client):
        """Test that whitespace-only descriptions are rejected with 400."""
        whitespace_tests = [
            "   ",
            "\t\t",
            "\n\n",
            "  \t\n  ",
        ]
        
        for description in whitespace_tests:
            response = client.post(
                "/api/v1/plan",
                json={"description": description}
            )
            
            assert response.status_code == 400, f"Failed for description: {repr(description)}"
            data = response.json()
            assert "error" in data
            assert data["status_code"] == 400
            
    def test_plan_endpoint_with_oversized_description(self, client):
        """Test that descriptions exceeding max length are rejected with 400."""
        max_bytes = settings.max_description_bytes
        
        # Create a description that exceeds the limit
        oversized_description = "a" * (max_bytes + 1)
        
        response = client.post(
            "/api/v1/plan",
            json={"description": oversized_description}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "error" in data
        assert data["status_code"] == 400
        assert "details" in data
        
        # Check that error message mentions the byte limit
        error_msg = str(data["details"])
        assert str(max_bytes) in error_msg
        
    def test_plan_endpoint_with_unicode_oversized_description(self, client):
        """Test that Unicode descriptions exceeding byte limit are rejected."""
        max_bytes = settings.max_description_bytes
        
        # Create a description using multi-byte Unicode characters (e.g., emoji)
        # Each emoji is typically 4 bytes in UTF-8
        # Calculate how many characters to use to exceed the limit
        emoji = "🚀"
        bytes_per_emoji = len(emoji.encode('utf-8'))
        num_emojis = (max_bytes // bytes_per_emoji) + 1
        
        oversized_description = emoji * num_emojis
        
        response = client.post(
            "/api/v1/plan",
            json={"description": oversized_description}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "error" in data
        assert data["status_code"] == 400


class TestPlanEndpointMalformedRequests:
    """Test cases for malformed JSON and missing fields."""
    
    def test_plan_endpoint_with_missing_description_field(self, client):
        """Test that missing description field returns 422 with JSON error."""
        response = client.post(
            "/api/v1/plan",
            json={}
        )
        
        assert response.status_code == 422
        data = response.json()
        assert "error" in data
        assert "status_code" in data
        assert data["status_code"] == 422
        assert "details" in data
        
        # Verify it's a JSON response, not HTML
        assert response.headers["content-type"] == "application/json"
        
    def test_plan_endpoint_with_malformed_json(self, client):
        """Test that malformed JSON returns JSON error, not HTML."""
        response = client.post(
            "/api/v1/plan",
            content="not valid json {",
            headers={"Content-Type": "application/json"}
        )
        
        # FastAPI returns 422 for malformed JSON
        assert response.status_code == 422
        data = response.json()
        assert "error" in data or "detail" in data
        
        # Verify it's a JSON response, not HTML
        assert response.headers["content-type"] == "application/json"
        
    def test_plan_endpoint_with_wrong_field_type(self, client):
        """Test that wrong field types return 422 with JSON error."""
        response = client.post(
            "/api/v1/plan",
            json={"description": 123}  # Should be string, not int
        )
        
        assert response.status_code == 422
        data = response.json()
        assert "error" in data
        assert "status_code" in data
        assert data["status_code"] == 422
        
    def test_plan_endpoint_with_null_description(self, client):
        """Test that null description returns 422 with JSON error."""
        response = client.post(
            "/api/v1/plan",
            json={"description": None}
        )
        
        assert response.status_code == 422
        data = response.json()
        assert "error" in data
        assert data["status_code"] == 422
        
    def test_plan_endpoint_with_extra_fields(self, client):
        """Test that extra fields are ignored and request succeeds."""
        response = client.post(
            "/api/v1/plan",
            json={
                "description": "Build an API",
                "extra_field": "should be ignored"
            }
        )
        
        # Should succeed - extra fields are typically ignored by Pydantic
        assert response.status_code == 200
        data = response.json()
        assert "specs" in data


class TestPlanEndpointEdgeCases:
    """Test cases for edge cases and special scenarios."""
    
    def test_plan_endpoint_with_very_short_description(self, client):
        """Test that single character descriptions are accepted."""
        response = client.post(
            "/api/v1/plan",
            json={"description": "a"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "specs" in data
        
    def test_plan_endpoint_with_special_characters(self, client):
        """Test that descriptions with special characters are handled."""
        special_descriptions = [
            "Build an API with <html> tags",
            "Create a service for O'Reilly's books",
            'Description with "quotes" and \'apostrophes\'',
            "Build API with newlines\nand tabs\there",
        ]
        
        for description in special_descriptions:
            response = client.post(
                "/api/v1/plan",
                json={"description": description}
            )
            
            assert response.status_code == 200, f"Failed for: {repr(description)}"
            data = response.json()
            assert "specs" in data
            
    def test_plan_endpoint_multiple_requests_are_deterministic(self, client):
        """Test that multiple requests with same input return identical results."""
        description = "Build a microservice"
        
        responses = [
            client.post("/api/v1/plan", json={"description": description})
            for _ in range(3)
        ]
        
        # All should succeed
        for response in responses:
            assert response.status_code == 200
            
        # All should return identical JSON
        json_responses = [r.json() for r in responses]
        assert json_responses[0] == json_responses[1] == json_responses[2]
        
    def test_plan_endpoint_response_has_at_least_one_spec(self, client):
        """Test that response always contains at least one spec item."""
        response = client.post(
            "/api/v1/plan",
            json={"description": "Test"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["specs"]) >= 1
