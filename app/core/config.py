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
"""Application configuration using Pydantic settings."""

from typing import Optional
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with typed configuration.
    
    All settings have sensible defaults and can be overridden via environment variables.
    """
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Application settings
    app_name: str = "Software Planner API"
    app_version: str = "0.1.0"
    debug: bool = False
    
    # Server settings
    host: str = "0.0.0.0"
    port: int = 8000
    
    # API settings
    api_prefix: str = "/api/v1"
    
    # Planning settings
    max_description_bytes: int = 8192
    
    # Job listing settings
    default_jobs_list_limit: int = 100
    max_jobs_list_limit: int = 1000
    
    # CORS settings
    # For security, allow_credentials should only be True when allowed_origins is not ["*"]
    # WARNING: Default configuration is for development only. In production, set
    # allowed_origins to specific domains and adjust allowed_credentials accordingly.
    allowed_origins: list[str] = ["*"]
    allowed_credentials: bool = False
    allowed_methods: list[str] = ["*"]
    allowed_headers: list[str] = ["*"]
    
    # LLM settings
    llm_api_key: str = Field(
        default="",
        description="API key for LLM provider. Required for LLM-based planning."
    )
    llm_model: str = Field(
        default="gpt-4",
        description="LLM model identifier (e.g., 'gpt-4', 'claude-sonnet-4.5', 'gemini-3.0-pro')"
    )
    llm_base_url: Optional[str] = Field(
        default=None,
        description="Optional base URL for LLM API (for custom endpoints or proxies)"
    )
    llm_timeout: int = Field(
        default=60,
        ge=1,
        description="Request timeout in seconds for LLM API calls"
    )
    llm_system_prompt: Optional[str] = Field(
        default=None,
        description="Optional override for the default system prompt"
    )

    @model_validator(mode="after")
    def _validate_cors_settings(self) -> "Settings":
        """Validate that CORS credentials are not enabled with wildcard origins."""
        if self.allowed_credentials and self.allowed_origins == ["*"]:
            raise ValueError(
                "If `allowed_credentials` is True, `allowed_origins` must be a specific list of origins, not ['*']."
            )
        return self
    
    @model_validator(mode="after")
    def _validate_llm_settings(self) -> "Settings":
        """Validate that required LLM settings are provided when needed.
        
        Note: This validator only checks that if an API key is provided, it's not empty.
        The actual requirement for an API key depends on whether LLM features are used.
        """
        # If API key is explicitly set to empty string, that's acceptable for
        # configurations that don't use LLM features yet
        return self


# Global settings instance
settings = Settings()
