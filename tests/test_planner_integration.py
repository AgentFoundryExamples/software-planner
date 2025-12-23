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

from unittest.mock import Mock

import pytest

from app.services.job_store import JobStore
from app.services.planner import generate_plan, _normalize_specs
from app.services.llm_client import (
    LLMConfigurationError,
    LLMRequestError,
    LLMResponseError,
)


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
                "nice": ["Add rate limiting", "Include logging"]
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
                    "nice": ["item3"]
                }
            ]
        }
        result = _normalize_specs(data)
        assert result == data
    
    def test_normalize_single_spec_object_to_list(self):
        """Test that single spec object is wrapped in a list."""
        data = {
            "specs": {
                "purpose": "Test",
                "vision": "Vision",
                "must": ["item1"],
                "dont": ["item2"],
                "nice": ["item3"]
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
                    "nice": []
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
                    "nice": []
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
                    "nice": []
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
                {
                    "purpose": large_string,
                    "vision": "Vision",
                    "must": [],
                    "dont": [],
                    "nice": []
                }
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
                    "nice": []
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
                    "nice": []
                }
            ]
        }
        result = _normalize_specs(data)
        assert result["specs"][0]["must"] == ["item1", "item2"]


class TestPlannerWithLLMMock:
    """Test planner with mocked LLM client."""
    
    def test_generate_plan_calls_llm_client(self, mock_llm_client):
        """Test that generate_plan calls the LLM client."""
        response = generate_plan("Build a REST API", llm_client=mock_llm_client)
        
        assert response is not None
        assert hasattr(response, 'specs')
        assert len(response.specs) >= 1
        mock_llm_client.generate_specs.assert_called_once()
    
    def test_generate_plan_passes_description_to_llm(self, mock_llm_client):
        """Test that description is passed to LLM client."""
        description = "Build a REST API"
        generate_plan(description, llm_client=mock_llm_client)
        
        call_args = mock_llm_client.generate_specs.call_args
        assert call_args[1]["description"] == description
    
    def test_generate_plan_uses_system_prompt(self, mock_llm_client):
        """Test that system prompt is passed to LLM client."""
        generate_plan("Build a REST API", llm_client=mock_llm_client)
        
        call_args = mock_llm_client.generate_specs.call_args
        assert "system_prompt" in call_args[1]
        assert call_args[1]["system_prompt"] is not None


class TestPlannerWithJobStore:
    """Test planner integration with JobStore."""
    
    def test_generate_plan_updates_job_to_running(self, mock_llm_client):
        """Test that generate_plan updates job status to running."""
        store = JobStore()
        job = store.create_job()
        
        assert job.status == "pending"
        
        generate_plan("Build a REST API", job_store=store, job_id=job.job_id, llm_client=mock_llm_client)
        
        updated_job = store.get_job(job.job_id)
        assert updated_job is not None
        assert updated_job.status == "succeeded"  # Will be succeeded after completion
    
    def test_generate_plan_records_success_status(self, mock_llm_client):
        """Test that successful plan generation updates status to succeeded."""
        store = JobStore()
        job = store.create_job()
        
        response = generate_plan("Build a REST API", job_store=store, job_id=job.job_id, llm_client=mock_llm_client)
        
        updated_job = store.get_job(job.job_id)
        assert updated_job is not None
        assert updated_job.status == "succeeded"
        assert response is not None
    
    def test_generate_plan_stores_result_with_specs(self, mock_llm_client):
        """Test that plan result is stored with top-level 'specs' field."""
        store = JobStore()
        job = store.create_job()
        
        response = generate_plan("Build a REST API", job_store=store, job_id=job.job_id, llm_client=mock_llm_client)
        
        updated_job = store.get_job(job.job_id)
        assert updated_job is not None
        assert updated_job.result is not None
        assert "specs" in updated_job.result
        assert isinstance(updated_job.result["specs"], list)
        assert len(updated_job.result["specs"]) >= 1
    
    def test_generate_plan_result_matches_response(self, mock_llm_client):
        """Test that stored result matches the returned response."""
        store = JobStore()
        job = store.create_job()
        
        response = generate_plan("Build a REST API", job_store=store, job_id=job.job_id, llm_client=mock_llm_client)
        
        updated_job = store.get_job(job.job_id)
        assert updated_job is not None
        assert updated_job.result is not None
        
        # Result should match response structure
        response_dict = response.model_dump()
        assert updated_job.result == response_dict
    
    def test_generate_plan_updates_timestamp(self, mock_llm_client):
        """Test that generate_plan updates the job timestamp."""
        store = JobStore()
        job = store.create_job()
        original_updated_at = job.updated_at
        
        generate_plan("Build a REST API", job_store=store, job_id=job.job_id, llm_client=mock_llm_client)
        
        updated_job = store.get_job(job.job_id)
        assert updated_job is not None
        assert updated_job.updated_at >= original_updated_at
    
    def test_generate_plan_with_nonexistent_job_id_does_not_crash(self, mock_llm_client):
        """Test that using non-existent job ID doesn't crash planner."""
        store = JobStore()
        
        # Should not raise exception
        response = generate_plan("Build a REST API", job_store=store, job_id="non-existent", llm_client=mock_llm_client)
        
        assert response is not None
        assert hasattr(response, 'specs')
    
    def test_generate_plan_preserves_json_serializability(self, mock_llm_client):
        """Test that stored result remains JSON-serializable."""
        store = JobStore()
        job = store.create_job()
        
        generate_plan("Build a REST API", job_store=store, job_id=job.job_id, llm_client=mock_llm_client)
        
        updated_job = store.get_job(job.job_id)
        assert updated_job is not None
        
        # Should be able to serialize to JSON
        json_str = updated_job.model_dump_json()
        assert json_str is not None
        assert len(json_str) > 0
    
    def test_generate_plan_with_job_store_but_no_job_id(self, mock_llm_client):
        """Test that providing job_store without job_id is handled gracefully."""
        store = JobStore()
        
        # Should not raise exception
        response = generate_plan("Build a REST API", job_store=store, job_id=None, llm_client=mock_llm_client)
        
        assert response is not None
        assert hasattr(response, 'specs')
    
    def test_generate_plan_with_job_id_but_no_job_store(self, mock_llm_client):
        """Test that providing job_id without job_store is handled gracefully."""
        # Should not raise exception
        response = generate_plan("Build a REST API", job_store=None, job_id="some-id", llm_client=mock_llm_client)
        
        assert response is not None
        assert hasattr(response, 'specs')
    
    def test_generate_plan_multiple_jobs(self, mock_llm_client):
        """Test that multiple jobs can be tracked independently."""
        store = JobStore()
        job1 = store.create_job()
        job2 = store.create_job()
        
        generate_plan("Build a REST API", job_store=store, job_id=job1.job_id, llm_client=mock_llm_client)
        generate_plan("Create a web service", job_store=store, job_id=job2.job_id, llm_client=mock_llm_client)
        
        updated_job1 = store.get_job(job1.job_id)
        updated_job2 = store.get_job(job2.job_id)
        
        assert updated_job1 is not None
        assert updated_job2 is not None
        assert updated_job1.status == "succeeded"
        assert updated_job2.status == "succeeded"
        assert updated_job1.result is not None
        assert updated_job2.result is not None
    
    def test_generate_plan_with_nonexistent_job_id_still_returns_plan(self, mock_llm_client):
        """Test that providing non-existent job_id still returns a plan."""
        store = JobStore()
        
        # Should not raise exception and should return a plan
        response = generate_plan("Build a REST API", job_store=store, job_id="non-existent-id", llm_client=mock_llm_client)
        
        assert response is not None
        assert hasattr(response, 'specs')
        assert len(response.specs) > 0
        
        # Job should not exist in store
        job = store.get_job("non-existent-id")
        assert job is None


class TestPlannerErrorHandling:
    """Test planner error handling with LLM failures."""
    
    def test_generate_plan_handles_llm_configuration_error(self):
        """Test that LLMConfigurationError is handled and job is marked failed."""
        store = JobStore()
        job = store.create_job()
        
        mock_client = Mock()
        mock_client.generate_specs.side_effect = LLMConfigurationError("Missing API key")
        
        with pytest.raises(LLMConfigurationError):
            generate_plan("Build a REST API", job_store=store, job_id=job.job_id, llm_client=mock_client)
        
        updated_job = store.get_job(job.job_id)
        assert updated_job is not None
        assert updated_job.status == "failed"
        assert updated_job.error is not None
        assert "configuration error" in updated_job.error["error"].lower()
    
    def test_generate_plan_handles_llm_request_error(self):
        """Test that LLMRequestError is handled and job is marked failed."""
        store = JobStore()
        job = store.create_job()
        
        mock_client = Mock()
        mock_client.generate_specs.side_effect = LLMRequestError("API timeout")
        
        with pytest.raises(LLMRequestError):
            generate_plan("Build a REST API", job_store=store, job_id=job.job_id, llm_client=mock_client)
        
        updated_job = store.get_job(job.job_id)
        assert updated_job is not None
        assert updated_job.status == "failed"
        assert updated_job.error is not None
        assert "request error" in updated_job.error["error"].lower()
    
    def test_generate_plan_handles_llm_response_error(self):
        """Test that LLMResponseError is handled and job is marked failed."""
        store = JobStore()
        job = store.create_job()
        
        mock_client = Mock()
        mock_client.generate_specs.side_effect = LLMResponseError("Invalid JSON")
        
        with pytest.raises(LLMResponseError):
            generate_plan("Build a REST API", job_store=store, job_id=job.job_id, llm_client=mock_client)
        
        updated_job = store.get_job(job.job_id)
        assert updated_job is not None
        assert updated_job.status == "failed"
        assert updated_job.error is not None
        assert "response error" in updated_job.error["error"].lower()
    
    def test_generate_plan_handles_empty_specs(self):
        """Test that empty specs from LLM is handled as error."""
        store = JobStore()
        job = store.create_job()
        
        mock_client = Mock()
        mock_client.generate_specs.return_value = {"specs": []}
        
        with pytest.raises(LLMResponseError, match="empty specs list"):
            generate_plan("Build a REST API", job_store=store, job_id=job.job_id, llm_client=mock_client)
        
        updated_job = store.get_job(job.job_id)
        assert updated_job is not None
        assert updated_job.status == "failed"
    
    def test_generate_plan_handles_unexpected_error(self):
        """Test that unexpected errors are handled and job is marked failed."""
        store = JobStore()
        job = store.create_job()
        
        mock_client = Mock()
        mock_client.generate_specs.side_effect = ValueError("Unexpected error")
        
        with pytest.raises(ValueError):
            generate_plan("Build a REST API", job_store=store, job_id=job.job_id, llm_client=mock_client)
        
        updated_job = store.get_job(job.job_id)
        assert updated_job is not None
        assert updated_job.status == "failed"
        assert updated_job.error is not None
        assert "Unexpected error" in updated_job.error["error"]
    
    def test_generate_plan_error_preserves_error_type(self):
        """Test that error type is preserved in job error."""
        store = JobStore()
        job = store.create_job()
        
        mock_client = Mock()
        mock_client.generate_specs.side_effect = LLMRequestError("Timeout")
        
        with pytest.raises(LLMRequestError):
            generate_plan("Build a REST API", job_store=store, job_id=job.job_id, llm_client=mock_client)
        
        updated_job = store.get_job(job.job_id)
        assert updated_job is not None
        assert updated_job.error is not None
        assert updated_job.error["type"] == "LLMRequestError"
