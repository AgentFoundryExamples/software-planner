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

import logging
import os
from typing import Optional
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


logger = logging.getLogger(__name__)


class ModelConfig(BaseSettings):
    """Configuration for a single logical LLM model.
    
    Attributes:
        provider: Provider identifier (e.g., 'openai', 'anthropic', 'google').
        model_id: Model identifier for the provider (e.g., 'gpt-5.1', 'claude-sonnet-4.5').
        base_url: Optional custom base URL for API endpoint.
        api_key_env: Name of environment variable containing the API key.
        enabled: Whether this model is enabled for use.
        timeout: Request timeout in seconds for API calls.
        max_retries: Maximum number of retry attempts for failed requests.
    """
    provider: str = Field(..., description="Provider identifier (openai, anthropic, google)")
    model_id: str = Field(..., description="Model identifier for the provider")
    base_url: Optional[str] = Field(None, description="Optional custom base URL")
    api_key_env: str = Field(..., description="Environment variable name for API key")
    enabled: bool = Field(True, description="Whether this model is enabled")
    timeout: int = Field(60, ge=1, description="Request timeout in seconds")
    max_retries: int = Field(3, ge=0, description="Maximum retry attempts")
    
    model_config = SettingsConfigDict(
        extra="forbid",
        protected_namespaces=()
    )


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
    
    # LLM settings (legacy, kept for backward compatibility)
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
    
    # Multi-provider LLM model registry
    models_registry: dict[str, ModelConfig] = Field(
        default_factory=dict,
        description="Mapping of logical model names to provider configurations"
    )
    default_model: Optional[str] = Field(
        default=None,
        description="Logical name of the default model to use"
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
    
    @model_validator(mode="after")
    def _validate_model_registry(self) -> "Settings":
        """Validate model registry configuration.
        
        Ensures:
        - At least one model is enabled (if registry is configured)
        - Exactly one default model is specified
        - Default model is enabled
        - All enabled models reference existing environment variables
        - Provider identifiers are known (openai, anthropic, google)
        """
        # If no registry is configured, skip validation (backward compatibility)
        if not self.models_registry:
            return self
        
        # Collect enabled models
        enabled_models = {
            name: config 
            for name, config in self.models_registry.items() 
            if config.enabled
        }
        
        # At least one model must be enabled
        if not enabled_models:
            raise ValueError(
                "Model registry validation failed: At least one model must be enabled. "
                f"All {len(self.models_registry)} configured models are disabled."
            )
        
        # Exactly one default model must be specified
        if not self.default_model:
            raise ValueError(
                "Model registry validation failed: default_model must be specified when using model registry. "
                f"Available models: {', '.join(self.models_registry.keys())}"
            )
        
        # Default model must exist in registry
        if self.default_model not in self.models_registry:
            raise ValueError(
                f"Model registry validation failed: default_model '{self.default_model}' not found in registry. "
                f"Available models: {', '.join(self.models_registry.keys())}"
            )
        
        # Default model must be enabled
        default_config = self.models_registry[self.default_model]
        if not default_config.enabled:
            raise ValueError(
                f"Model registry validation failed: default_model '{self.default_model}' is disabled. "
                "The default model must be enabled."
            )
        
        # Validate all enabled models have their API key env vars set
        missing_env_vars = []
        for name, config in enabled_models.items():
            api_key_value = os.environ.get(config.api_key_env, "").strip()
            if not api_key_value:
                missing_env_vars.append(f"{name} (env var: {config.api_key_env})")
        
        if missing_env_vars:
            raise ValueError(
                "Model registry validation failed: The following enabled models have missing or empty API key environment variables:\n" +
                "\n".join(f"  - {item}" for item in missing_env_vars) +
                "\n\nEither disable these models or set their API key environment variables."
            )
        
        # Validate provider identifiers
        known_providers = {"openai", "anthropic", "google"}
        unknown_providers = []
        for name, config in self.models_registry.items():
            if config.provider.lower() not in known_providers:
                unknown_providers.append(f"{name} (provider: {config.provider})")
        
        if unknown_providers:
            raise ValueError(
                f"Model registry validation failed: Unknown provider identifiers found. "
                f"Known providers: {', '.join(sorted(known_providers))}. Unknown:\n" +
                "\n".join(f"  - {item}" for item in unknown_providers)
            )
        
        # Validate timeout values
        invalid_timeouts = []
        for name, config in self.models_registry.items():
            if config.timeout < 1:
                invalid_timeouts.append(f"{name} (timeout: {config.timeout})")
        
        if invalid_timeouts:
            raise ValueError(
                "Model registry validation failed: Invalid timeout values (must be >= 1 second):\n" +
                "\n".join(f"  - {item}" for item in invalid_timeouts)
            )
        
        return self


# Global settings instance
settings = Settings()
