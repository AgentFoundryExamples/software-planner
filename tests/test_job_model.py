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
"""Tests for the Job model."""

import json
from datetime import datetime, timezone

import pytest

from app.models.job import Job, JobStatus


class TestJobModel:
    """Test cases for the Job model."""
    
    def test_job_creation_with_all_fields(self):
        """Test creating a job with all fields."""
        now = datetime.now(timezone.utc)
        job = Job(
            job_id="test-uuid-123",
            status="pending",
            created_at=now,
            updated_at=now,
            result=None,
            error=None
        )
        
        assert job.job_id == "test-uuid-123"
        assert job.status == "pending"
        assert job.created_at == now
        assert job.updated_at == now
        assert job.result is None
        assert job.error is None
    
    def test_job_status_enum_values(self):
        """Test that only valid status values are accepted."""
        now = datetime.now(timezone.utc)
        valid_statuses: list[JobStatus] = ["pending", "running", "succeeded", "failed"]
        
        for status in valid_statuses:
            job = Job(
                job_id=f"test-{status}",
                status=status,
                created_at=now,
                updated_at=now
            )
            assert job.status == status
    
    def test_job_with_result_dict(self):
        """Test job with result containing specs."""
        now = datetime.now(timezone.utc)
        result = {
            "specs": [
                {
                    "purpose": "Test",
                    "vision": "Test vision",
                    "must": ["item1"],
                    "dont": ["item2"],
                    "nice": ["item3"]
                }
            ]
        }
        
        job = Job(
            job_id="test-with-result",
            status="succeeded",
            created_at=now,
            updated_at=now,
            result=result,
            error=None
        )
        
        assert job.result == result
        assert "specs" in job.result
    
    def test_job_with_error_dict(self):
        """Test job with error information."""
        now = datetime.now(timezone.utc)
        error = {
            "error": "Something went wrong",
            "type": "ValueError"
        }
        
        job = Job(
            job_id="test-with-error",
            status="failed",
            created_at=now,
            updated_at=now,
            result=None,
            error=error
        )
        
        assert job.error == error
        assert job.error["error"] == "Something went wrong"
        assert job.error["type"] == "ValueError"
    
    def test_job_json_serialization(self):
        """Test that job can be serialized to JSON."""
        now = datetime.now(timezone.utc)
        job = Job(
            job_id="test-serialization",
            status="pending",
            created_at=now,
            updated_at=now,
            result=None,
            error=None
        )
        
        # Serialize to JSON
        json_str = job.model_dump_json()
        assert json_str is not None
        
        # Parse back to verify structure
        data = json.loads(json_str)
        assert data["job_id"] == "test-serialization"
        assert data["status"] == "pending"
        assert "created_at" in data
        assert "updated_at" in data
    
    def test_job_model_dump(self):
        """Test that job can be dumped to dict."""
        now = datetime.now(timezone.utc)
        result = {"specs": []}
        
        job = Job(
            job_id="test-dump",
            status="succeeded",
            created_at=now,
            updated_at=now,
            result=result,
            error=None
        )
        
        data = job.model_dump()
        assert isinstance(data, dict)
        assert data["job_id"] == "test-dump"
        assert data["status"] == "succeeded"
        assert data["result"] == result
        assert data["error"] is None
    
    def test_job_with_large_result(self):
        """Test job with large result payload remains JSON-serializable."""
        now = datetime.now(timezone.utc)
        
        # Create a large result with many specs
        large_result = {
            "specs": [
                {
                    "purpose": f"Purpose {i}",
                    "vision": f"Vision {i}",
                    "must": [f"must-{i}-{j}" for j in range(10)],
                    "dont": [f"dont-{i}-{j}" for j in range(10)],
                    "nice": [f"nice-{i}-{j}" for j in range(10)]
                }
                for i in range(100)
            ]
        }
        
        job = Job(
            job_id="test-large-result",
            status="succeeded",
            created_at=now,
            updated_at=now,
            result=large_result,
            error=None
        )
        
        # Should be JSON-serializable
        json_str = job.model_dump_json()
        assert json_str is not None
        
        # Should be parseable
        data = json.loads(json_str)
        assert len(data["result"]["specs"]) == 100
    
    def test_job_timestamps_are_datetime_objects(self):
        """Test that timestamps are datetime objects."""
        now = datetime.now(timezone.utc)
        job = Job(
            job_id="test-timestamps",
            status="pending",
            created_at=now,
            updated_at=now
        )
        
        assert isinstance(job.created_at, datetime)
        assert isinstance(job.updated_at, datetime)
    
    def test_job_optional_fields_default_to_none(self):
        """Test that result and error default to None."""
        now = datetime.now(timezone.utc)
        job = Job(
            job_id="test-defaults",
            status="pending",
            created_at=now,
            updated_at=now
        )
        
        assert job.result is None
        assert job.error is None
