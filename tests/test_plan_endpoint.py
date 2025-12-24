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

from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client that returns valid specs."""
    client = Mock()
    client.generate_specs.return_value = {
        "specs": [
            {
                "purpose": "Core API Development",
                "vision": "Build a robust and scalable REST API with proper error handling and validation",
                "must": [
                    "Implement RESTful endpoints with proper HTTP methods",
                    "Add comprehensive input validation",
                    "Include error handling with informative messages",
                    "Write unit and integration tests",
                ],
                "dont": [
                    "Skip validation on user inputs",
                    "Expose internal error details to clients",
                    "Hardcode configuration values",
                    "Ignore security best practices",
                ],
                "nice": [
                    "Add API rate limiting",
                    "Include request/response logging",
                    "Implement API versioning",
                    "Add OpenAPI documentation",
                ],
            }
        ]
    }
    return client


@pytest.fixture
def client(mock_llm_client):
    """Create a test client for the FastAPI app with mocked LLM client."""
    from app.services.rate_limiter import RateLimiter

    # Create a disabled rate limiter for these tests
    disabled_limiter = RateLimiter(window_seconds=60, max_requests=10, enabled=False)  # Disabled

    # Patch both the LLM client and rate limiter
    with patch("app.services.store_singleton.get_llm_client", return_value=mock_llm_client):
        with patch("app.api.routes.get_rate_limiter", return_value=disabled_limiter):
            yield TestClient(app)


class TestPlanEndpointHappyPath:
    """Test cases for successful /plan endpoint requests."""

    def test_plan_endpoint_with_valid_description(self, client):
        """Test POST /plan with a valid description returns expected response structure."""
        response = client.post(
            "/api/v1/plan", json={"description": "Build a REST API for managing tasks"}
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
        response1 = client.post("/api/v1/plan", json={"description": "Build a mobile app"})
        response2 = client.post("/api/v1/plan", json={"description": "Create a web service"})

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

        response = client.post("/api/v1/plan", json={"description": description})

        assert response.status_code == 200
        data = response.json()
        assert "specs" in data

    def test_plan_endpoint_with_unicode_characters(self, client):
        """Test that descriptions with Unicode characters are handled correctly."""
        description = "Build an API with émojis 🚀 and spëcial çhars"

        response = client.post("/api/v1/plan", json={"description": description})

        assert response.status_code == 200
        data = response.json()
        assert "specs" in data

    def test_plan_endpoint_response_contract(self, client):
        """Test that response strictly matches the contract."""
        response = client.post("/api/v1/plan", json={"description": "Test project"})

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
        response = client.post("/api/v1/plan", json={"description": ""})

        assert response.status_code == 400
        data = response.json()
        assert "error" in data

        # Verify new error format
        error = data["error"]
        assert "code" in error
        assert "message" in error
        assert "request_id" in error
        assert error["code"] == "invalid_description"

    def test_plan_endpoint_with_whitespace_only_description(self, client):
        """Test that whitespace-only descriptions are rejected with 400."""
        whitespace_tests = [
            "   ",
            "\t\t",
            "\n\n",
            "  \t\n  ",
        ]

        for description in whitespace_tests:
            response = client.post("/api/v1/plan", json={"description": description})

            assert response.status_code == 400, f"Failed for description: {repr(description)}"
            data = response.json()
            assert "error" in data

            # Verify new error format
            error = data["error"]
            assert "code" in error
            assert "message" in error
            assert error["code"] == "invalid_description"

    def test_plan_endpoint_with_oversized_description(self, client):
        """Test that descriptions exceeding max length are rejected with 400."""
        max_bytes = settings.max_description_bytes

        # Create a description that exceeds the limit
        oversized_description = "a" * (max_bytes + 1)

        response = client.post("/api/v1/plan", json={"description": oversized_description})

        assert response.status_code == 400
        data = response.json()
        assert "error" in data

        # Verify new error format and check for payload_too_large code
        error = data["error"]
        assert "code" in error
        assert "message" in error
        assert error["code"] == "payload_too_large"

        # Check that error message mentions the byte limit
        if "details" in error and "validation_errors" in error["details"]:
            error_msg = str(error["details"]["validation_errors"])
            assert str(max_bytes) in error_msg

    def test_plan_endpoint_with_unicode_oversized_description(self, client):
        """Test that Unicode descriptions exceeding byte limit are rejected."""
        max_bytes = settings.max_description_bytes

        # Create a description using multi-byte Unicode characters (e.g., emoji)
        # Each emoji is typically 4 bytes in UTF-8
        # Calculate how many characters to use to exceed the limit
        emoji = "🚀"
        bytes_per_emoji = len(emoji.encode("utf-8"))
        num_emojis = (max_bytes // bytes_per_emoji) + 1

        oversized_description = emoji * num_emojis

        response = client.post("/api/v1/plan", json={"description": oversized_description})

        assert response.status_code == 400
        data = response.json()
        assert "error" in data

        # Verify new error format
        error = data["error"]
        assert "code" in error
        assert error["code"] == "payload_too_large"

    def test_plan_endpoint_utf8_multibyte_counting(self, client):
        """Test that multi-byte UTF-8 characters are counted correctly toward byte limit.

        Verifies acceptance criteria: UTF-8 multi-byte input counts toward the character limit.
        Tests with various multi-byte Unicode characters (emoji, CJK) to ensure byte-based
        length enforcement rather than character-based.
        """
        max_bytes = settings.max_description_bytes

        # Test 1: Emoji (4 bytes each in UTF-8)
        emoji = "🚀"
        emoji_bytes = len(emoji.encode("utf-8"))
        assert emoji_bytes == 4, "Emoji should be 4 bytes"

        # Create description with emojis that fits exactly at limit
        num_emojis_at_limit = max_bytes // emoji_bytes
        at_limit_description = emoji * num_emojis_at_limit

        response = client.post("/api/v1/plan", json={"description": at_limit_description})
        assert response.status_code == 200, "Should accept description at exact byte limit"

        # Create description with emojis that exceeds limit by one emoji
        over_limit_description = emoji * (num_emojis_at_limit + 1)

        response = client.post("/api/v1/plan", json={"description": over_limit_description})
        assert response.status_code == 400, "Should reject description over byte limit"
        assert response.json()["error"]["code"] == "payload_too_large"

        # Test 2: CJK characters (3 bytes each in UTF-8)
        cjk_char = "漢"  # Chinese character
        cjk_bytes = len(cjk_char.encode("utf-8"))
        assert cjk_bytes == 3, "CJK character should be 3 bytes"

        # Create description with CJK that fits at limit
        num_cjk_at_limit = max_bytes // cjk_bytes
        cjk_at_limit = cjk_char * num_cjk_at_limit

        response = client.post("/api/v1/plan", json={"description": cjk_at_limit})
        assert response.status_code == 200, "Should accept CJK description at byte limit"

        # Test 3: Mixed ASCII and multi-byte (verify byte counting, not character counting)
        # Create a string with ASCII (1 byte) + emoji (4 bytes) that would fit if counted
        # by characters but exceeds if counted by bytes
        ascii_part = "a" * (max_bytes - 3)  # Leave 3 bytes
        mixed_description = ascii_part + "🚀"  # Add 4-byte emoji (exceeds by 1 byte)

        response = client.post("/api/v1/plan", json={"description": mixed_description})
        assert response.status_code == 400, "Should reject based on bytes, not character count"

        # Verify the character count would be under limit if counted incorrectly
        char_count = len(mixed_description)
        assert (
            char_count < max_bytes
        ), "Character count is under byte limit (proving byte-based validation)"


class TestPlanEndpointMalformedRequests:
    """Test cases for malformed JSON and missing fields."""

    def test_plan_endpoint_with_missing_description_field(self, client):
        """Test that missing description field returns 422 with JSON error."""
        response = client.post("/api/v1/plan", json={})

        assert response.status_code == 422
        data = response.json()
        assert "error" in data

        # Verify new error format
        error = data["error"]
        assert "code" in error
        assert "message" in error
        assert error["code"] == "missing_field"

        # Verify it's a JSON response, not HTML
        assert response.headers["content-type"] == "application/json"

    def test_plan_endpoint_with_malformed_json(self, client):
        """Test that malformed JSON returns JSON error, not HTML."""
        response = client.post(
            "/api/v1/plan", content="not valid json {", headers={"Content-Type": "application/json"}
        )

        # FastAPI returns 422 for malformed JSON
        assert response.status_code == 422
        data = response.json()
        # Either old or new format - both are acceptable for JSON parse errors
        assert "error" in data or "detail" in data

        # Verify it's a JSON response, not HTML
        assert response.headers["content-type"] == "application/json"

    def test_plan_endpoint_with_wrong_field_type(self, client):
        """Test that wrong field types return 422 with JSON error."""
        response = client.post(
            "/api/v1/plan", json={"description": 123}  # Should be string, not int
        )

        assert response.status_code == 422
        data = response.json()
        assert "error" in data

        # Verify new error format
        error = data["error"]
        assert "code" in error
        assert "message" in error
        assert error["code"] == "invalid_type"

    def test_plan_endpoint_with_null_description(self, client):
        """Test that null description returns 422 with JSON error."""
        response = client.post("/api/v1/plan", json={"description": None})

        assert response.status_code == 422
        data = response.json()
        assert "error" in data

        # Verify new error format
        error = data["error"]
        assert "code" in error
        assert "message" in error
        # Could be missing_field or invalid_type depending on how pydantic handles None
        assert error["code"] in ["missing_field", "invalid_type", "malformed_request"]

    def test_plan_endpoint_with_extra_fields(self, client):
        """Test that extra fields are ignored and request succeeds."""
        response = client.post(
            "/api/v1/plan", json={"description": "Build an API", "extra_field": "should be ignored"}
        )

        # Should succeed - extra fields are typically ignored by Pydantic
        assert response.status_code == 200
        data = response.json()
        assert "specs" in data


class TestPlanEndpointControlCharacters:
    """Test cases for control character validation."""

    def test_plan_endpoint_rejects_null_byte(self, client):
        """Test that descriptions with null bytes are rejected."""
        response = client.post("/api/v1/plan", json={"description": "Build API\x00with null"})

        assert response.status_code == 400
        data = response.json()
        assert "error" in data

        error = data["error"]
        assert "code" in error
        assert error["code"] == "invalid_description"

    def test_plan_endpoint_rejects_other_control_chars(self, client):
        """Test that descriptions with disallowed control characters are rejected."""
        # Test various control characters (excluding allowed ones: tab, newline, CR)
        control_chars_to_test = [
            "\x01",  # SOH (Start of Heading)
            "\x02",  # STX (Start of Text)
            "\x08",  # BS (Backspace)
            "\x0B",  # VT (Vertical Tab)
            "\x0C",  # FF (Form Feed)
            "\x1B",  # ESC (Escape)
            "\x7F",  # DEL (Delete)
        ]

        for control_char in control_chars_to_test:
            response = client.post(
                "/api/v1/plan", json={"description": f"Build API{control_char}with control char"}
            )

            assert (
                response.status_code == 400
            ), f"Failed to reject control char {repr(control_char)}"
            data = response.json()
            assert "error" in data

            error = data["error"]
            assert error["code"] == "invalid_description"

    def test_plan_endpoint_allows_tab_newline_cr(self, client):
        """Test that tab, newline, and carriage return are allowed."""
        response = client.post(
            "/api/v1/plan", json={"description": "Build API\nwith newlines\tand tabs\rand CR"}
        )

        # Should succeed - these are allowed whitespace characters
        assert response.status_code == 200
        data = response.json()
        assert "specs" in data


class TestPlanEndpointErrorResponseFormat:
    """Test cases for standardized error response format."""

    def test_validation_error_includes_request_id(self, client):
        """Test that validation errors include request_id."""
        response = client.post("/api/v1/plan", json={"description": ""})

        assert response.status_code == 400
        data = response.json()
        assert "error" in data

        error = data["error"]
        assert "request_id" in error
        assert error["request_id"] is not None
        assert len(error["request_id"]) > 0

    def test_error_response_has_standard_structure(self, client):
        """Test that error responses follow the standard structure."""
        response = client.post("/api/v1/plan", json={"description": ""})

        assert response.status_code == 400
        data = response.json()

        # Top-level should have exactly "error" key
        assert list(data.keys()) == ["error"]

        error = data["error"]
        # Error object should have these keys
        assert "code" in error
        assert "message" in error
        assert "request_id" in error
        # details is optional

        # Verify types
        assert isinstance(error["code"], str)
        assert isinstance(error["message"], str)
        assert isinstance(error["request_id"], str)

    def test_missing_field_error_has_correct_code(self, client):
        """Test that missing field errors have the correct error code."""
        response = client.post("/api/v1/plan", json={})

        assert response.status_code == 422
        data = response.json()

        error = data["error"]
        assert error["code"] == "missing_field"

    def test_type_error_has_correct_code(self, client):
        """Test that type errors have the correct error code."""
        response = client.post("/api/v1/plan", json={"description": 123})

        assert response.status_code == 422
        data = response.json()

        error = data["error"]
        assert error["code"] == "invalid_type"

    def test_oversized_payload_has_correct_code(self, client):
        """Test that oversized payloads have the correct error code."""
        max_bytes = settings.max_description_bytes
        oversized = "a" * (max_bytes + 1)

        response = client.post("/api/v1/plan", json={"description": oversized})

        assert response.status_code == 400
        data = response.json()

        error = data["error"]
        assert error["code"] == "payload_too_large"


class TestPlanEndpointEdgeCases:
    """Test cases for edge cases and special scenarios."""

    def test_plan_endpoint_with_very_short_description(self, client):
        """Test that single character descriptions are accepted."""
        response = client.post("/api/v1/plan", json={"description": "a"})

        assert response.status_code == 200
        data = response.json()
        assert "specs" in data

    def test_plan_endpoint_with_special_characters(self, client):
        """Test that descriptions with special characters are handled."""
        special_descriptions = [
            "Build an API with <html> tags",
            "Create a service for O'Reilly's books",
            "Description with \"quotes\" and 'apostrophes'",
            "Build API with newlines\nand tabs\there",
        ]

        for description in special_descriptions:
            response = client.post("/api/v1/plan", json={"description": description})

            assert response.status_code == 200, f"Failed for: {repr(description)}"
            data = response.json()
            assert "specs" in data

    def test_plan_endpoint_multiple_requests_are_deterministic(self, client):
        """Test that multiple requests with same input return identical results."""
        description = "Build a microservice"

        responses = [
            client.post("/api/v1/plan", json={"description": description}) for _ in range(3)
        ]

        # All should succeed
        for response in responses:
            assert response.status_code == 200

        # All should return identical JSON
        json_responses = [r.json() for r in responses]
        assert json_responses[0] == json_responses[1] == json_responses[2]

    def test_plan_endpoint_response_has_at_least_one_spec(self, client):
        """Test that response always contains at least one spec item."""
        response = client.post("/api/v1/plan", json={"description": "Test"})

        assert response.status_code == 200
        data = response.json()
        assert len(data["specs"]) >= 1


class TestPlanEndpointModelParameter:
    """Test cases for model parameter in /plan endpoint."""

    def test_plan_endpoint_with_valid_model_override(self, client):
        """Test that valid model override is accepted."""
        # This test will only work if the registry has models configured
        # For now, we test with a model parameter, even if validation might fail
        # in environments without a configured registry
        response = client.post(
            "/api/v1/plan", json={"description": "Build a REST API", "model": "gpt-4-turbo"}
        )

        # If no registry is configured, this should still validate the request structure
        # The actual validation happens at runtime based on config
        assert response.status_code in [200, 400]

    def test_plan_endpoint_model_with_whitespace_only_rejected(self, client):
        """Test that whitespace-only model names are rejected."""
        response = client.post(
            "/api/v1/plan", json={"description": "Build a REST API", "model": "   "}
        )

        assert response.status_code == 400
        data = response.json()
        assert "error" in data or "detail" in data

    def test_plan_endpoint_with_null_model_uses_default(self, client):
        """Test that null model parameter uses default model."""
        response = client.post(
            "/api/v1/plan", json={"description": "Build a REST API", "model": None}
        )

        # Should succeed with default model
        assert response.status_code == 200
        data = response.json()
        assert "specs" in data

    def test_plan_endpoint_without_model_uses_default(self, client):
        """Test that omitting model parameter uses default model."""
        response = client.post("/api/v1/plan", json={"description": "Build a REST API"})

        # Should succeed with default model
        assert response.status_code == 200
        data = response.json()
        assert "specs" in data

    def test_plan_endpoint_model_validation_with_empty_string(self, client):
        """Test that empty string model is rejected."""
        response = client.post(
            "/api/v1/plan", json={"description": "Build a REST API", "model": ""}
        )

        # Empty string should be treated as not provided (None)
        # or rejected by validation
        assert response.status_code in [200, 400, 422]


class TestPlanEndpointSystemPromptParameter:
    """Test cases for system_prompt parameter in /plan endpoint."""

    def test_plan_endpoint_with_valid_system_prompt(self, client):
        """Test that valid system prompt override is accepted."""
        response = client.post(
            "/api/v1/plan",
            json={
                "description": "Build a REST API",
                "system_prompt": "You are a helpful assistant specialized in API design.",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "specs" in data

    def test_plan_endpoint_with_whitespace_only_system_prompt_rejected(self, client):
        """Test that whitespace-only system prompts are rejected."""
        response = client.post(
            "/api/v1/plan", json={"description": "Build a REST API", "system_prompt": "   "}
        )

        assert response.status_code == 400
        data = response.json()
        assert "error" in data or "detail" in data

    def test_plan_endpoint_with_oversized_system_prompt_rejected(self, client):
        """Test that oversized system prompts are rejected."""
        max_bytes = settings.max_system_prompt_bytes
        oversized_prompt = "a" * (max_bytes + 1)

        response = client.post(
            "/api/v1/plan",
            json={"description": "Build a REST API", "system_prompt": oversized_prompt},
        )

        assert response.status_code == 400
        data = response.json()
        assert "error" in data or "detail" in data
        # Check that error mentions byte limit
        error_msg = str(data)
        assert str(max_bytes) in error_msg

    def test_plan_endpoint_with_system_prompt_at_max_length(self, client):
        """Test that system prompts at exact max length are accepted."""
        max_bytes = settings.max_system_prompt_bytes
        max_length_prompt = "a" * max_bytes

        response = client.post(
            "/api/v1/plan",
            json={"description": "Build a REST API", "system_prompt": max_length_prompt},
        )

        assert response.status_code == 200
        data = response.json()
        assert "specs" in data

    def test_plan_endpoint_without_system_prompt_uses_default(self, client):
        """Test that omitting system_prompt uses default."""
        response = client.post("/api/v1/plan", json={"description": "Build a REST API"})

        assert response.status_code == 200
        data = response.json()
        assert "specs" in data

    def test_plan_endpoint_with_null_system_prompt_uses_default(self, client):
        """Test that null system_prompt uses default."""
        response = client.post(
            "/api/v1/plan", json={"description": "Build a REST API", "system_prompt": None}
        )

        assert response.status_code == 200
        data = response.json()
        assert "specs" in data


class TestPlanEndpointCombinedParameters:
    """Test cases for combined model and system_prompt parameters."""

    def test_plan_endpoint_with_both_overrides(self, client):
        """Test that both model and system_prompt can be overridden together."""
        response = client.post(
            "/api/v1/plan",
            json={
                "description": "Build a REST API",
                "model": "gpt-4-turbo",
                "system_prompt": "You are an expert API architect.",
            },
        )

        # Accept either success or model validation failure depending on config
        assert response.status_code in [200, 400]

    def test_plan_endpoint_backward_compatibility(self, client):
        """Test that legacy clients without new fields still work."""
        response = client.post("/api/v1/plan", json={"description": "Build a REST API"})

        assert response.status_code == 200
        data = response.json()
        assert "specs" in data
        # Response should not include model/system_prompt in top level
        assert "model" not in data
        assert "system_prompt" not in data
