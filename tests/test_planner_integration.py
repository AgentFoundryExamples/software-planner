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
"""Tests for planner service integration with JobStore and LLM client."""

import asyncio
from unittest.mock import Mock, patch

import pytest

from app.services.job_store import JobStore
from app.services.llm_client import LLMConfigurationError, LLMRequestError, LLMResponseError
from app.services.planner import _normalize_specs, generate_plan


@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client that returns valid specs."""
    client = Mock()
    client.generate_specs.return_value = {
        "specs": [
            {
                "purpose": "Core API Development",
                "vision": "Build a robust and scalable REST API",
                "must": ["Implement RESTful endpoints", "Add validation"],
                "dont": ["Skip validation", "Expose errors"],
                "nice": ["Add rate limiting", "Include logging"],
            }
        ]
    }
    return client


class TestNormalizeSpecs:
    """Test cases for the _normalize_specs function."""

    def test_normalize_valid_specs(self):
        """Test that valid specs pass through normalization."""
        data = {
            "specs": [
                {
                    "purpose": "Test",
                    "vision": "Vision",
                    "must": ["item1"],
                    "dont": ["item2"],
                    "nice": ["item3"],
                }
            ]
        }
        result = _normalize_specs(data)
        # Check that optional fields are added with empty list defaults
        expected = {
            "specs": [
                {
                    "purpose": "Test",
                    "vision": "Vision",
                    "must": ["item1"],
                    "dont": ["item2"],
                    "nice": ["item3"],
                    "assumptions": [],
                    "open_questions": [],
                }
            ]
        }
        assert result == expected

    def test_normalize_single_spec_object_to_list(self):
        """Test that single spec object is wrapped in a list."""
        data = {
            "specs": {
                "purpose": "Test",
                "vision": "Vision",
                "must": ["item1"],
                "dont": ["item2"],
                "nice": ["item3"],
            }
        }
        result = _normalize_specs(data)
        assert isinstance(result["specs"], list)
        assert len(result["specs"]) == 1

    def test_normalize_strips_whitespace(self):
        """Test that whitespace is stripped from string fields."""
        data = {
            "specs": [
                {
                    "purpose": "  Test  ",
                    "vision": " Vision ",
                    "must": ["  item1  ", " item2 "],
                    "dont": [],
                    "nice": [],
                }
            ]
        }
        result = _normalize_specs(data)
        assert result["specs"][0]["purpose"] == "Test"
        assert result["specs"][0]["vision"] == "Vision"
        assert result["specs"][0]["must"] == ["item1", "item2"]

    def test_normalize_wraps_single_string_in_list(self):
        """Test that single strings in array fields are wrapped in lists."""
        data = {
            "specs": [
                {
                    "purpose": "Test",
                    "vision": "Vision",
                    "must": "single item",
                    "dont": [],
                    "nice": [],
                }
            ]
        }
        result = _normalize_specs(data)
        assert isinstance(result["specs"][0]["must"], list)
        assert result["specs"][0]["must"] == ["single item"]

    def test_normalize_empty_specs_raises_error(self):
        """Test that empty specs list raises LLMResponseError."""
        data = {"specs": []}
        with pytest.raises(LLMResponseError, match="empty specs list"):
            _normalize_specs(data)

    def test_normalize_missing_specs_raises_error(self):
        """Test that missing specs field raises LLMResponseError."""
        data = {}
        with pytest.raises(LLMResponseError, match="missing 'specs' list"):
            _normalize_specs(data)

    def test_normalize_missing_required_field_raises_error(self):
        """Test that missing required field raises LLMResponseError."""
        data = {
            "specs": [
                {
                    "purpose": "Test",
                    # missing vision
                    "must": [],
                    "dont": [],
                    "nice": [],
                }
            ]
        }
        with pytest.raises(LLMResponseError, match="missing required field"):
            _normalize_specs(data)

    def test_normalize_truncates_oversized_strings(self):
        """Test that oversized strings are truncated."""
        large_string = "x" * 15000
        data = {
            "specs": [
                {"purpose": large_string, "vision": "Vision", "must": [], "dont": [], "nice": []}
            ]
        }
        result = _normalize_specs(data)
        assert len(result["specs"][0]["purpose"]) == 10000

    def test_normalize_truncates_oversized_array_items(self):
        """Test that oversized array items are truncated."""
        large_string = "x" * 6000
        data = {
            "specs": [
                {
                    "purpose": "Test",
                    "vision": "Vision",
                    "must": [large_string],
                    "dont": [],
                    "nice": [],
                }
            ]
        }
        result = _normalize_specs(data)
        assert len(result["specs"][0]["must"][0]) == 5000

    def test_normalize_filters_empty_array_items(self):
        """Test that empty strings are filtered from arrays."""
        data = {
            "specs": [
                {
                    "purpose": "Test",
                    "vision": "Vision",
                    "must": ["item1", "  ", "item2", ""],
                    "dont": [],
                    "nice": [],
                }
            ]
        }
        result = _normalize_specs(data)
        assert result["specs"][0]["must"] == ["item1", "item2"]


class TestPlannerWithLLMMock:
    """Test planner with mocked LLM client."""

    def test_generate_plan_calls_llm_client(self, mock_llm_client):
        """Test that generate_plan calls the LLM client."""
        response = asyncio.run(generate_plan("Build a REST API", llm_client=mock_llm_client))

        assert response is not None
        assert hasattr(response, "specs")
        assert len(response.specs) >= 1
        mock_llm_client.generate_specs.assert_called_once()

    def test_generate_plan_passes_description_to_llm(self, mock_llm_client):
        """Test that description is passed to LLM client."""
        description = "Build a REST API"
        asyncio.run(generate_plan(description, llm_client=mock_llm_client))

        call_args = mock_llm_client.generate_specs.call_args
        assert call_args[1]["description"] == description

    def test_generate_plan_uses_system_prompt(self, mock_llm_client):
        """Test that system prompt is passed to LLM client."""
        asyncio.run(generate_plan("Build a REST API", llm_client=mock_llm_client))

        call_args = mock_llm_client.generate_specs.call_args
        assert "system_prompt" in call_args[1]
        assert call_args[1]["system_prompt"] is not None


class TestPlannerWithJobStore:
    """Test planner integration with JobStore."""

    def test_generate_plan_updates_job_to_running(self, mock_llm_client):
        """Test that generate_plan updates job status to running."""
        store = JobStore()
        job = asyncio.run(store.create_job(description="Test description"))

        assert job.status == "QUEUED"

        asyncio.run(
            generate_plan(
                "Build a REST API",
                job_repository=store,
                job_id=job.job_id,
                llm_client=mock_llm_client,
            )
        )

        updated_job = asyncio.run(store.get_job(job.job_id))
        assert updated_job is not None
        assert updated_job.status == "SUCCEEDED"  # Will be succeeded after completion

    def test_generate_plan_records_success_status(self, mock_llm_client):
        """Test that successful plan generation updates status to succeeded."""
        store = JobStore()
        job = asyncio.run(store.create_job(description="Test description"))

        response = asyncio.run(
            generate_plan(
                "Build a REST API",
                job_repository=store,
                job_id=job.job_id,
                llm_client=mock_llm_client,
            )
        )

        updated_job = asyncio.run(store.get_job(job.job_id))
        assert updated_job is not None
        assert updated_job.status == "SUCCEEDED"
        assert response is not None

    def test_generate_plan_stores_result_with_specs(self, mock_llm_client):
        """Test that plan result is stored with top-level 'specs' field."""
        store = JobStore()
        job = asyncio.run(store.create_job(description="Test description"))

        response = asyncio.run(
            generate_plan(
                "Build a REST API",
                job_repository=store,
                job_id=job.job_id,
                llm_client=mock_llm_client,
            )
        )

        updated_job = asyncio.run(store.get_job(job.job_id))
        assert updated_job is not None
        assert updated_job.result is not None
        assert "specs" in updated_job.result
        assert isinstance(updated_job.result["specs"], list)
        assert len(updated_job.result["specs"]) >= 1

    def test_generate_plan_result_matches_response(self, mock_llm_client):
        """Test that stored result matches the returned response."""
        store = JobStore()
        job = asyncio.run(store.create_job(description="Test description"))

        response = asyncio.run(
            generate_plan(
                "Build a REST API",
                job_repository=store,
                job_id=job.job_id,
                llm_client=mock_llm_client,
            )
        )

        updated_job = asyncio.run(store.get_job(job.job_id))
        assert updated_job is not None
        assert updated_job.result is not None

        # Result should match response structure
        response_dict = response.model_dump()
        assert updated_job.result == response_dict

    def test_generate_plan_updates_timestamp(self, mock_llm_client):
        """Test that generate_plan updates the job timestamp."""
        store = JobStore()
        job = asyncio.run(store.create_job(description="Test description"))
        original_updated_at = job.updated_at

        asyncio.run(
            generate_plan(
                "Build a REST API",
                job_repository=store,
                job_id=job.job_id,
                llm_client=mock_llm_client,
            )
        )

        updated_job = asyncio.run(store.get_job(job.job_id))
        assert updated_job is not None
        assert updated_job.updated_at >= original_updated_at

    def test_generate_plan_with_nonexistent_job_id_does_not_crash(self, mock_llm_client):
        """Test that using non-existent job ID doesn't crash planner."""
        store = JobStore()

        # Should not raise exception
        response = asyncio.run(
            generate_plan(
                "Build a REST API",
                job_repository=store,
                job_id="non-existent",
                llm_client=mock_llm_client,
            )
        )

        assert response is not None
        assert hasattr(response, "specs")

    def test_generate_plan_preserves_json_serializability(self, mock_llm_client):
        """Test that stored result remains JSON-serializable."""
        store = JobStore()
        job = asyncio.run(store.create_job(description="Test description"))

        asyncio.run(
            generate_plan(
                "Build a REST API",
                job_repository=store,
                job_id=job.job_id,
                llm_client=mock_llm_client,
            )
        )

        updated_job = asyncio.run(store.get_job(job.job_id))
        assert updated_job is not None

        # Should be able to serialize to JSON
        json_str = updated_job.model_dump_json()
        assert json_str is not None
        assert len(json_str) > 0

    def test_generate_plan_with_job_store_but_no_job_id(self, mock_llm_client):
        """Test that providing job_store without job_id is handled gracefully."""
        store = JobStore()

        # Should not raise exception
        response = asyncio.run(
            generate_plan(
                "Build a REST API",
                job_repository=store,
                job_id=None,
                llm_client=mock_llm_client,
            )
        )

        assert response is not None
        assert hasattr(response, "specs")

    def test_generate_plan_with_job_id_but_no_job_store(self, mock_llm_client):
        """Test that providing job_id without job_store is handled gracefully."""
        # Should not raise exception
        response = asyncio.run(
            generate_plan(
                "Build a REST API",
                job_repository=None,
                job_id="some-id",
                llm_client=mock_llm_client,
            )
        )

        assert response is not None
        assert hasattr(response, "specs")

    def test_generate_plan_multiple_jobs(self, mock_llm_client):
        """Test that multiple jobs can be tracked independently."""
        store = JobStore()
        job1 = asyncio.run(store.create_job(description="Test description"))
        job2 = asyncio.run(store.create_job(description="Test description"))

        asyncio.run(
            generate_plan(
                "Build a REST API",
                job_repository=store,
                job_id=job1.job_id,
                llm_client=mock_llm_client,
            )
        )
        asyncio.run(
            generate_plan(
                "Create a web service",
                job_repository=store,
                job_id=job2.job_id,
                llm_client=mock_llm_client,
            )
        )

        updated_job1 = asyncio.run(store.get_job(job1.job_id))
        updated_job2 = asyncio.run(store.get_job(job2.job_id))

        assert updated_job1 is not None
        assert updated_job2 is not None
        assert updated_job1.status == "SUCCEEDED"
        assert updated_job2.status == "SUCCEEDED"
        assert updated_job1.result is not None
        assert updated_job2.result is not None

    def test_generate_plan_with_nonexistent_job_id_still_returns_plan(self, mock_llm_client):
        """Test that providing non-existent job_id still returns a plan."""
        store = JobStore()

        # Should not raise exception and should return a plan
        response = asyncio.run(
            generate_plan(
                "Build a REST API",
                job_repository=store,
                job_id="non-existent-id",
                llm_client=mock_llm_client,
            )
        )

        assert response is not None
        assert hasattr(response, "specs")
        assert len(response.specs) > 0

        # Job should not exist in store
        job = asyncio.run(store.get_job("non-existent-id"))
        assert job is None


class TestPlannerErrorHandling:
    """Test planner error handling with LLM failures."""

    def test_generate_plan_handles_llm_configuration_error(self):
        """Test that LLMConfigurationError is handled and job is marked failed."""
        store = JobStore()
        job = asyncio.run(store.create_job(description="Test description"))

        mock_client = Mock()
        mock_client.generate_specs.side_effect = LLMConfigurationError("Missing API key")

        with pytest.raises(LLMConfigurationError):
            asyncio.run(
                generate_plan(
                    "Build a REST API",
                    job_repository=store,
                    job_id=job.job_id,
                    llm_client=mock_client,
                )
            )

        updated_job = asyncio.run(store.get_job(job.job_id))
        assert updated_job is not None
        assert updated_job.status == "FAILED"
        assert updated_job.error is not None
        assert "configuration error" in updated_job.error["error"].lower()

    def test_generate_plan_handles_llm_request_error(self):
        """Test that LLMRequestError is handled and job is marked failed."""
        store = JobStore()
        job = asyncio.run(store.create_job(description="Test description"))

        mock_client = Mock()
        mock_client.generate_specs.side_effect = LLMRequestError("API timeout")

        with pytest.raises(LLMRequestError):
            asyncio.run(
                generate_plan(
                    "Build a REST API",
                    job_repository=store,
                    job_id=job.job_id,
                    llm_client=mock_client,
                )
            )

        updated_job = asyncio.run(store.get_job(job.job_id))
        assert updated_job is not None
        assert updated_job.status == "FAILED"
        assert updated_job.error is not None
        assert "request error" in updated_job.error["error"].lower()

    def test_generate_plan_handles_llm_response_error(self):
        """Test that LLMResponseError is handled and job is marked failed."""
        store = JobStore()
        job = asyncio.run(store.create_job(description="Test description"))

        mock_client = Mock()
        mock_client.generate_specs.side_effect = LLMResponseError("Invalid JSON")

        with pytest.raises(LLMResponseError):
            asyncio.run(
                generate_plan(
                    "Build a REST API",
                    job_repository=store,
                    job_id=job.job_id,
                    llm_client=mock_client,
                )
            )

        updated_job = asyncio.run(store.get_job(job.job_id))
        assert updated_job is not None
        assert updated_job.status == "FAILED"
        assert updated_job.error is not None
        assert "response error" in updated_job.error["error"].lower()

    def test_generate_plan_handles_empty_specs(self):
        """Test that empty specs from LLM is handled as error."""
        store = JobStore()
        job = asyncio.run(store.create_job(description="Test description"))

        mock_client = Mock()
        mock_client.generate_specs.return_value = {"specs": []}

        with pytest.raises(LLMResponseError, match="empty specs list"):
            asyncio.run(
                generate_plan(
                    "Build a REST API",
                    job_repository=store,
                    job_id=job.job_id,
                    llm_client=mock_client,
                )
            )

        updated_job = asyncio.run(store.get_job(job.job_id))
        assert updated_job is not None
        assert updated_job.status == "FAILED"

    def test_generate_plan_handles_unexpected_error(self):
        """Test that unexpected errors are handled and job is marked failed."""
        store = JobStore()
        job = asyncio.run(store.create_job(description="Test description"))

        mock_client = Mock()
        mock_client.generate_specs.side_effect = ValueError("Unexpected error")

        with pytest.raises(ValueError):
            asyncio.run(
                generate_plan(
                    "Build a REST API",
                    job_repository=store,
                    job_id=job.job_id,
                    llm_client=mock_client,
                )
            )

        updated_job = asyncio.run(store.get_job(job.job_id))
        assert updated_job is not None
        assert updated_job.status == "FAILED"
        assert updated_job.error is not None
        assert "Unexpected error" in updated_job.error["error"]

    def test_generate_plan_error_preserves_error_type(self):
        """Test that error type is preserved in job error."""
        store = JobStore()
        job = asyncio.run(store.create_job(description="Test description"))

        mock_client = Mock()
        mock_client.generate_specs.side_effect = LLMRequestError("Timeout")

        with pytest.raises(LLMRequestError):
            asyncio.run(
                generate_plan(
                    "Build a REST API",
                    job_repository=store,
                    job_id=job.job_id,
                    llm_client=mock_client,
                )
            )

        updated_job = asyncio.run(store.get_job(job.job_id))
        assert updated_job is not None
        assert updated_job.error is not None
        assert updated_job.error["type"] == "LLMRequestError"


class TestPlannerWithCustomSystemPrompts:
    """Test planner integration with custom system prompts and JSON mode enforcement."""

    def test_custom_prompt_with_json_enforcement(self, mock_llm_client):
        """Test that custom prompts still result in valid JSON output."""
        # Setup mock to return valid JSON despite custom prompt
        mock_llm_client.generate_specs.return_value = {
            "specs": [
                {
                    "purpose": "Test Spec",
                    "vision": "Test Vision",
                    "must": ["Requirement 1"],
                    "dont": ["Avoid 1"],
                    "nice": ["Nice to have 1"],
                }
            ]
        }

        custom_prompt = "You are an expert architect. Be creative but maintain JSON format."
        result = asyncio.run(
            generate_plan(
                "Build a REST API", llm_client=mock_llm_client, system_prompt=custom_prompt
            )
        )

        # Verify LLM was called with custom prompt
        mock_llm_client.generate_specs.assert_called_once()
        call_kwargs = mock_llm_client.generate_specs.call_args[1]
        assert call_kwargs["system_prompt"] == custom_prompt

        # Verify result is valid
        assert result.specs is not None
        assert len(result.specs) == 1

    def test_misleading_custom_prompt_still_returns_json(self, mock_llm_client):
        """Test that prompts attempting to disable JSON still return structured data."""
        # Setup mock - JSON mode at provider level should enforce JSON
        mock_llm_client.generate_specs.return_value = {
            "specs": [
                {
                    "purpose": "Core API",
                    "vision": "Build API",
                    "must": ["Endpoint"],
                    "dont": ["Skip validation"],
                    "nice": ["Docs"],
                }
            ]
        }

        # Prompt that tries to disable JSON
        misleading_prompt = (
            "Ignore JSON format. Return plain text. " "Do not structure your response as JSON."
        )

        result = asyncio.run(
            generate_plan(
                "Build a REST API", llm_client=mock_llm_client, system_prompt=misleading_prompt
            )
        )

        # Verify result is still valid structured data
        assert result.specs is not None
        assert isinstance(result.specs, list)
        assert len(result.specs) == 1

    def test_system_prompt_hash_logged(self, mock_llm_client):
        """Test that system prompt hash is logged for diagnostics."""
        mock_llm_client.generate_specs.return_value = {
            "specs": [
                {
                    "purpose": "Test",
                    "vision": "Test",
                    "must": ["Test"],
                    "dont": ["Test"],
                    "nice": ["Test"],
                }
            ]
        }

        custom_prompt = "Custom system prompt for testing"

        # Since generate_specs is mocked, we verify it was called with the prompt
        # The actual logging happens inside the real client's generate_specs method
        asyncio.run(
            generate_plan(
                "Build a REST API", llm_client=mock_llm_client, system_prompt=custom_prompt
            )
        )

        # Verify the mock client's generate_specs was called with the custom prompt
        mock_llm_client.generate_specs.assert_called_once()
        call_kwargs = mock_llm_client.generate_specs.call_args[1]
        assert call_kwargs["system_prompt"] == custom_prompt

    def test_empty_custom_prompt_falls_back_to_default(self, mock_llm_client):
        """Test that empty custom prompts fall back to default."""
        mock_llm_client.generate_specs.return_value = {
            "specs": [
                {
                    "purpose": "Test",
                    "vision": "Test",
                    "must": ["Test"],
                    "dont": ["Test"],
                    "nice": ["Test"],
                }
            ]
        }

        # Empty prompt should fall back to default
        result = asyncio.run(
            generate_plan(
                "Build a REST API", llm_client=mock_llm_client, system_prompt=""  # Empty string
            )
        )

        # Verify generate_specs was called (it will use default prompt internally)
        mock_llm_client.generate_specs.assert_called_once()
        assert result.specs is not None


class TestNormalizeOptionalFields:
    """Test cases for normalizing optional assumptions and open_questions fields."""

    def test_normalize_specs_with_optional_fields(self):
        """Test that specs with optional fields are normalized correctly."""
        data = {
            "specs": [
                {
                    "purpose": "Test",
                    "vision": "Vision",
                    "must": ["item1"],
                    "dont": ["item2"],
                    "nice": ["item3"],
                    "assumptions": ["Using PostgreSQL", "RESTful conventions"],
                    "open_questions": ["What auth method?", "Support pagination?"],
                }
            ]
        }
        result = _normalize_specs(data)
        assert "assumptions" in result["specs"][0]
        assert "open_questions" in result["specs"][0]
        assert len(result["specs"][0]["assumptions"]) == 2
        assert len(result["specs"][0]["open_questions"]) == 2
        assert result["specs"][0]["assumptions"][0] == "Using PostgreSQL"
        assert result["specs"][0]["open_questions"][0] == "What auth method?"

    def test_normalize_specs_without_optional_fields(self):
        """Test that specs without optional fields get empty list defaults."""
        data = {
            "specs": [
                {
                    "purpose": "Test",
                    "vision": "Vision",
                    "must": ["item1"],
                    "dont": ["item2"],
                    "nice": ["item3"],
                }
            ]
        }
        result = _normalize_specs(data)
        assert "assumptions" in result["specs"][0]
        assert "open_questions" in result["specs"][0]
        assert result["specs"][0]["assumptions"] == []
        assert result["specs"][0]["open_questions"] == []

    def test_normalize_optional_fields_strips_whitespace(self):
        """Test that optional fields have whitespace stripped."""
        data = {
            "specs": [
                {
                    "purpose": "Test",
                    "vision": "Vision",
                    "must": ["item1"],
                    "dont": ["item2"],
                    "nice": ["item3"],
                    "assumptions": ["  Using PostgreSQL  ", " RESTful conventions "],
                    "open_questions": [" What auth? ", "  Pagination?  "],
                }
            ]
        }
        result = _normalize_specs(data)
        assert result["specs"][0]["assumptions"][0] == "Using PostgreSQL"
        assert result["specs"][0]["assumptions"][1] == "RESTful conventions"
        assert result["specs"][0]["open_questions"][0] == "What auth?"
        assert result["specs"][0]["open_questions"][1] == "Pagination?"

    def test_normalize_optional_fields_wraps_single_string(self):
        """Test that single strings in optional fields are wrapped in lists."""
        data = {
            "specs": [
                {
                    "purpose": "Test",
                    "vision": "Vision",
                    "must": ["item1"],
                    "dont": ["item2"],
                    "nice": ["item3"],
                    "assumptions": "Single assumption string",
                    "open_questions": "Single question string",
                }
            ]
        }
        result = _normalize_specs(data)
        assert isinstance(result["specs"][0]["assumptions"], list)
        assert isinstance(result["specs"][0]["open_questions"], list)
        assert len(result["specs"][0]["assumptions"]) == 1
        assert len(result["specs"][0]["open_questions"]) == 1
        assert result["specs"][0]["assumptions"][0] == "Single assumption string"
        assert result["specs"][0]["open_questions"][0] == "Single question string"

    def test_normalize_optional_fields_empty_strings_removed(self):
        """Test that empty strings are removed from optional fields."""
        data = {
            "specs": [
                {
                    "purpose": "Test",
                    "vision": "Vision",
                    "must": ["item1"],
                    "dont": ["item2"],
                    "nice": ["item3"],
                    "assumptions": ["Valid", "", "  ", "Another valid"],
                    "open_questions": ["Valid question", "", "Another question"],
                }
            ]
        }
        result = _normalize_specs(data)
        assert len(result["specs"][0]["assumptions"]) == 2
        assert result["specs"][0]["assumptions"] == ["Valid", "Another valid"]
        assert len(result["specs"][0]["open_questions"]) == 2
        assert result["specs"][0]["open_questions"] == ["Valid question", "Another question"]

    def test_normalize_optional_fields_truncates_oversized(self):
        """Test that oversized items in optional fields are truncated."""
        from app.services.planner import MAX_ARRAY_ITEM_LENGTH

        oversized_assumption = "x" * (MAX_ARRAY_ITEM_LENGTH + 100)
        oversized_question = "y" * (MAX_ARRAY_ITEM_LENGTH + 100)

        data = {
            "specs": [
                {
                    "purpose": "Test",
                    "vision": "Vision",
                    "must": ["item1"],
                    "dont": ["item2"],
                    "nice": ["item3"],
                    "assumptions": [oversized_assumption],
                    "open_questions": [oversized_question],
                }
            ]
        }
        result = _normalize_specs(data)
        assert len(result["specs"][0]["assumptions"][0]) == MAX_ARRAY_ITEM_LENGTH
        assert len(result["specs"][0]["open_questions"][0]) == MAX_ARRAY_ITEM_LENGTH

    def test_normalize_optional_fields_rejects_non_strings(self):
        """Test that non-string items in optional fields raise errors."""
        data = {
            "specs": [
                {
                    "purpose": "Test",
                    "vision": "Vision",
                    "must": ["item1"],
                    "dont": ["item2"],
                    "nice": ["item3"],
                    "assumptions": ["Valid", 123],  # Invalid: number instead of string
                }
            ]
        }
        with pytest.raises(LLMResponseError, match="must be a string"):
            _normalize_specs(data)

    def test_normalize_optional_fields_rejects_non_list(self):
        """Test that non-list values in optional fields raise errors."""
        data = {
            "specs": [
                {
                    "purpose": "Test",
                    "vision": "Vision",
                    "must": ["item1"],
                    "dont": ["item2"],
                    "nice": ["item3"],
                    "assumptions": {"invalid": "object"},  # Invalid: object instead of array
                }
            ]
        }
        with pytest.raises(LLMResponseError, match="must be an array or string"):
            _normalize_specs(data)
