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
from pydantic import Field, field_validator, model_validator, ValidationError as PydanticValidationError
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
    max_system_prompt_bytes: int = 32768  # Maximum length for custom system prompts
    
    # Security: API key authentication
    planner_api_keys: list[str] = Field(
        default_factory=list,
        description="List of valid API keys for planner authentication. Required for production use."
    )
    
    # Security: Request bounds
    planner_request_description_max_chars: int = Field(
        default=50000,
        ge=1,
        description="Maximum characters allowed in request descriptions"
    )
    
    # Security: Rate limiting
    planner_rate_limit_window_seconds: int = Field(
        default=60,
        ge=1,
        description="Rate limit time window in seconds"
    )
    planner_rate_limit_max_requests: int = Field(
        default=10,
        ge=1,
        description="Maximum requests allowed per rate limit window"
    )
    
    # Observability: Metrics and logging
    planner_metrics_enabled: bool = Field(
        default=False,
        description="Enable metrics collection and exposure"
    )
    
    # Job listing settings
    default_jobs_list_limit: int = 100
    max_jobs_list_limit: int = 1000
    
    # Database settings
    database_host: str = Field(
        default="localhost",
        description="PostgreSQL database host"
    )
    database_port: int = Field(
        default=5432,
        ge=1,
        le=65535,
        description="PostgreSQL database port"
    )
    database_name: str = Field(
        default="software_planner",
        description="PostgreSQL database name"
    )
    database_user: str = Field(
        default="",
        description="PostgreSQL database user"
    )
    database_password: str = Field(
        default="",
        description="PostgreSQL database password"
    )
    database_url: Optional[str] = Field(
        default=None,
        description="Complete PostgreSQL connection URL (overrides individual settings if provided)"
    )
    
    # CORS settings
    # For security, allow_credentials should only be True when allowed_origins is not ["*"]
    # WARNING: Default configuration is for development only. In production, set
    # allowed_origins to specific domains and adjust allowed_credentials accordingly.
    allowed_origins: list[str] = ["*"]
    allowed_credentials: bool = False
    allowed_methods: list[str] = ["*"]
    allowed_headers: list[str] = ["*"]
    
    # Security: Explicit wildcard control for CORS
    cors_wildcard_enabled: bool = Field(
        default=True,  # Default to True for backward compatibility with existing ["*"] default
        description="Explicitly enable wildcard (*) in allowed_origins. Set to False in production."
    )
    
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
    def _validate_planner_api_keys(self) -> "Settings":
        """Validate API keys for planner authentication.
        
        Ensures:
        - API keys are not empty strings or whitespace-only
        - No duplicate keys
        - Keys have reasonable format
        """
        if not self.planner_api_keys:
            # Empty list is allowed but will be flagged at runtime when auth is needed
            return self
        
        # Check for empty or whitespace-only keys
        invalid_keys = []
        for idx, key in enumerate(self.planner_api_keys):
            if not key or not key.strip():
                invalid_keys.append(idx)
        
        if invalid_keys:
            raise ValueError(
                f"Planner API key validation failed: Keys at indices {invalid_keys} are empty or contain only whitespace. "
                "All API keys must be non-empty strings."
            )
        
        # Check for duplicate keys
        stripped_keys = [key.strip() for key in self.planner_api_keys]
        if len(stripped_keys) != len(set(stripped_keys)):
            raise ValueError(
                "Planner API key validation failed: Duplicate API keys detected. "
                "Each API key must be unique."
            )
        
        return self
    
    @model_validator(mode="after")
    def _validate_planner_request_limits(self) -> "Settings":
        """Validate request description character limits.
        
        Ensures:
        - Max chars is within reasonable bounds for LLM processing
        - Value doesn't exceed typical LLM context window constraints
        """
        # Most LLMs have context windows of ~200K tokens, roughly 800K chars
        # Set a conservative upper limit of 500K characters
        MAX_REASONABLE_CHARS = 500000
        
        if self.planner_request_description_max_chars > MAX_REASONABLE_CHARS:
            raise ValueError(
                f"Planner request description max_chars validation failed: "
                f"Value {self.planner_request_description_max_chars} exceeds reasonable limit of {MAX_REASONABLE_CHARS} characters. "
                "This limit prevents exceeding LLM context window constraints."
            )
        
        return self
    
    @model_validator(mode="after")
    def _validate_cors_wildcard(self) -> "Settings":
        """Validate CORS wildcard configuration.
        
        Ensures:
        - Wildcard '*' in origins is only allowed when explicitly enabled
        - Provides clear security guidance
        """
        if "*" in self.allowed_origins and not self.cors_wildcard_enabled:
            raise ValueError(
                "CORS wildcard validation failed: allowed_origins contains '*' but cors_wildcard_enabled is False. "
                "To use wildcard origins, you must explicitly set cors_wildcard_enabled=True. "
                "WARNING: Wildcard CORS origins are insecure for production. Use specific domains instead."
            )
        
        return self
    
    @model_validator(mode="after")
    def _validate_database_settings(self) -> "Settings":
        """Validate database configuration and construct DATABASE_URL if needed.
        
        This validator ensures that database configuration is complete and valid when provided.
        If no database configuration is provided at all (both user and password empty),
        the validator allows it to pass - the application will fail at runtime when
        database operations are attempted.
        
        Ensures:
        - If database_url is provided, it has the correct format
        - If individual settings are provided, they are complete and valid
        - If no database configuration is provided at all, validation passes
          (fail-fast will happen when database operations are attempted)
        """
        # If database_url is explicitly provided, validate and use it
        if self.database_url:
            # Basic validation that it looks like a PostgreSQL URL
            if not self.database_url.startswith(("postgresql://", "postgresql+asyncpg://")):
                raise ValueError(
                    "database_url must start with 'postgresql://' or 'postgresql+asyncpg://'"
                )
            return self
        
        # Check if any database configuration was provided
        user_provided = self.database_user and self.database_user.strip()
        pass_provided = self.database_password and self.database_password.strip()
        
        # If neither user nor password provided, skip validation
        # This allows tests and development without database
        # The application will fail at runtime when DB operations are attempted
        if not user_provided and not pass_provided:
            return self
        
        # If partial configuration provided, validate it's complete
        if not user_provided:
            raise ValueError(
                "Database configuration error: database_user is required when database_password is set. "
                "Either set DATABASE_USER or provide a complete DATABASE_URL."
            )
        
        if not pass_provided:
            raise ValueError(
                "Database configuration error: database_password is required when database_user is set. "
                "Either set DATABASE_PASSWORD or provide a complete DATABASE_URL."
            )
        
        # Construct database URL from individual settings
        # Use asyncpg dialect for async operations
        self.database_url = (
            f"postgresql+asyncpg://{self.database_user}:{self.database_password}"
            f"@{self.database_host}:{self.database_port}/{self.database_name}"
        )
        
        return self
    
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
        
        This validation runs at Settings instantiation time (typically at application
        startup). It checks that environment variables exist at that moment, which is
        the intended behavior - we want to fail fast at startup if configuration is
        invalid rather than failing later when a model is actually used.
        
        The Settings object is typically created once at application startup and
        is immutable thereafter, so the validation timing is appropriate. If
        environment variables change after startup, the application should be
        restarted to pick up the new configuration.
        
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
        
        # Note: Timeout validation is handled by ModelConfig's Field(ge=1) constraint
        # and does not need to be checked here.
        
        return self
    
    # Helper methods for downstream dependencies
    
    def get_normalized_api_keys(self) -> set[str]:
        """Get normalized set of API keys with whitespace stripped.
        
        Returns:
            Set of normalized (stripped) API keys.
        """
        return {key.strip() for key in self.planner_api_keys if key and key.strip()}
    
    def get_rate_limit_config(self) -> dict[str, int]:
        """Get rate limit configuration as a dictionary.
        
        Returns:
            Dictionary with 'window_seconds' and 'max_requests' keys.
        """
        return {
            "window_seconds": self.planner_rate_limit_window_seconds,
            "max_requests": self.planner_rate_limit_max_requests
        }
    
    def is_api_key_valid(self, api_key: str) -> bool:
        """Check if an API key is valid.
        
        Args:
            api_key: The API key to validate.
            
        Returns:
            True if the key is valid, False otherwise.
        """
        if not api_key or not api_key.strip():
            return False
        return api_key.strip() in self.get_normalized_api_keys()


# Global settings instance
settings = Settings()
