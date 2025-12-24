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
"""Tests for logging helpers."""

import logging
import pytest

from app.utils.logging_helpers import (
    hash_api_key,
    create_structured_log_context,
    log_job_transition,
    log_llm_request,
    log_llm_response,
    log_http_request
)


class TestHashApiKey:
    """Tests for hash_api_key function."""
    
    def test_hash_api_key_none(self):
        """Test hashing None returns None."""
        assert hash_api_key(None) is None
    
    def test_hash_api_key_empty_string(self):
        """Test hashing empty string returns None."""
        assert hash_api_key("") is None
    
    def test_hash_api_key_valid(self):
        """Test hashing valid API key."""
        result = hash_api_key("sk-test-key-12345")
        
        assert result is not None
        assert len(result) == 16
        assert result != "sk-test-key-12345"
    
    def test_hash_api_key_consistent(self):
        """Test that same key produces same hash."""
        key = "sk-test-key-12345"
        hash1 = hash_api_key(key)
        hash2 = hash_api_key(key)
        
        assert hash1 == hash2
    
    def test_hash_api_key_different_keys(self):
        """Test that different keys produce different hashes."""
        hash1 = hash_api_key("sk-test-key-1")
        hash2 = hash_api_key("sk-test-key-2")
        
        assert hash1 != hash2


class TestCreateStructuredLogContext:
    """Tests for create_structured_log_context function."""
    
    def test_empty_context(self):
        """Test creating context with no parameters."""
        context = create_structured_log_context()
        
        assert context == {}
    
    def test_request_id(self):
        """Test adding request_id to context."""
        context = create_structured_log_context(request_id="req-123")
        
        assert context == {"request_id": "req-123"}
    
    def test_job_id(self):
        """Test adding job_id to context."""
        context = create_structured_log_context(job_id="job-456")
        
        assert context == {"job_id": "job-456"}
    
    def test_api_key_hashed(self):
        """Test that API key is hashed in context."""
        context = create_structured_log_context(api_key="sk-secret")
        
        assert "api_key" not in context
        assert "api_key_hash" in context
        assert context["api_key_hash"] != "sk-secret"
    
    def test_model(self):
        """Test adding model to context."""
        context = create_structured_log_context(model="gpt-4")
        
        assert context == {"model": "gpt-4"}
    
    def test_status(self):
        """Test adding status to context."""
        context = create_structured_log_context(status="RUNNING")
        
        assert context == {"status": "RUNNING"}
    
    def test_error_type(self):
        """Test adding error_type to context."""
        context = create_structured_log_context(error_type="ValueError")
        
        assert context == {"error_type": "ValueError"}
    
    def test_extra_fields(self):
        """Test adding extra custom fields."""
        context = create_structured_log_context(
            request_id="req-123",
            custom_field="value",
            another_field=42
        )
        
        assert context["request_id"] == "req-123"
        assert context["custom_field"] == "value"
        assert context["another_field"] == 42
    
    def test_none_values_excluded(self):
        """Test that None values are excluded from context."""
        context = create_structured_log_context(
            request_id="req-123",
            job_id=None,
            custom_field=None
        )
        
        assert "request_id" in context
        assert "job_id" not in context
        assert "custom_field" not in context


class TestLogJobTransition:
    """Tests for log_job_transition function."""
    
    def test_log_job_created(self, caplog):
        """Test logging job creation (from_status is None)."""
        logger = logging.getLogger("test")
        
        with caplog.at_level(logging.INFO):
            log_job_transition(
                logger=logger,
                job_id="job-123",
                from_status=None,
                to_status="QUEUED"
            )
        
        assert len(caplog.records) == 1
        assert "created" in caplog.records[0].message.lower()
        assert "job-123" in caplog.records[0].message
        assert "QUEUED" in caplog.records[0].message
    
    def test_log_job_transition(self, caplog):
        """Test logging job status transition."""
        logger = logging.getLogger("test")
        
        with caplog.at_level(logging.INFO):
            log_job_transition(
                logger=logger,
                job_id="job-123",
                from_status="QUEUED",
                to_status="RUNNING"
            )
        
        assert len(caplog.records) == 1
        assert "transitioned" in caplog.records[0].message.lower()
        assert "QUEUED -> RUNNING" in caplog.records[0].message


class TestLogLlmRequest:
    """Tests for log_llm_request function."""
    
    def test_log_llm_request(self, caplog):
        """Test logging LLM request."""
        logger = logging.getLogger("test")
        
        with caplog.at_level(logging.INFO):
            log_llm_request(
                logger=logger,
                provider="openai",
                model="gpt-4",
                description_length=1000
            )
        
        assert len(caplog.records) == 1
        assert "openai" in caplog.records[0].message.lower()
        assert "gpt-4" in caplog.records[0].message


class TestLogLlmResponse:
    """Tests for log_llm_response function."""
    
    def test_log_llm_response_success(self, caplog):
        """Test logging successful LLM response."""
        logger = logging.getLogger("test")
        
        with caplog.at_level(logging.INFO):
            log_llm_response(
                logger=logger,
                provider="openai",
                model="gpt-4",
                duration=2.5,
                status="success",
                prompt_tokens=100,
                completion_tokens=150
            )
        
        assert len(caplog.records) == 1
        assert "success" in caplog.records[0].message.lower()
        assert "openai" in caplog.records[0].message.lower()
    
    def test_log_llm_response_error(self, caplog):
        """Test logging failed LLM response."""
        logger = logging.getLogger("test")
        
        with caplog.at_level(logging.INFO):
            log_llm_response(
                logger=logger,
                provider="anthropic",
                model="claude-sonnet",
                duration=1.0,
                status="error"
            )
        
        assert len(caplog.records) == 1
        assert "error" in caplog.records[0].message.lower()


class TestLogHttpRequest:
    """Tests for log_http_request function."""
    
    def test_log_http_request(self, caplog):
        """Test logging HTTP request."""
        logger = logging.getLogger("test")
        
        with caplog.at_level(logging.INFO):
            log_http_request(
                logger=logger,
                method="POST",
                endpoint="/api/v1/plans",
                status=202,
                duration=0.5
            )
        
        assert len(caplog.records) == 1
        assert "POST" in caplog.records[0].message
        assert "/api/v1/plans" in caplog.records[0].message
        assert "202" in caplog.records[0].message
    
    def test_log_http_request_with_api_key(self, caplog):
        """Test logging HTTP request with API key (should be hashed)."""
        logger = logging.getLogger("test")
        
        with caplog.at_level(logging.INFO):
            log_http_request(
                logger=logger,
                method="GET",
                endpoint="/api/v1/models",
                status=200,
                duration=0.1,
                api_key="sk-secret"
            )
        
        assert len(caplog.records) == 1
        # API key should not appear in message
        assert "sk-secret" not in caplog.records[0].message
