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

from pydantic import model_validator
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
    
    # CORS settings
    # For security, allow_credentials should only be True when allowed_origins is not ["*"]
    # WARNING: Default configuration is for development only. In production, set
    # allowed_origins to specific domains and adjust allowed_credentials accordingly.
    allowed_origins: list[str] = ["*"]
    allowed_credentials: bool = False
    allowed_methods: list[str] = ["*"]
    allowed_headers: list[str] = ["*"]

    @model_validator(mode="after")
    def _validate_cors_settings(self) -> "Settings":
        """Validate that CORS credentials are not enabled with wildcard origins."""
        if self.allowed_credentials and self.allowed_origins == ["*"]:
            raise ValueError(
                "If `allowed_credentials` is True, `allowed_origins` must be a specific list of origins, not ['*']."
            )
        return self


# Global settings instance
settings = Settings()
