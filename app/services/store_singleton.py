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
"""Global job repository singleton for dependency injection.

This module provides a centralized location for the global job repository instance,
avoiding circular import issues between main.py and routes.py.
"""

import asyncio
import logging
import threading
from typing import Optional

from app.core.config import settings
from app.services.job_repository import JobRepository
from app.services.llm_client import BaseLLMClient, LLMConfigurationError
from app.services.llm_openai import OpenAIClient
from app.services.model_registry import get_model_registry

logger = logging.getLogger(__name__)

# Global job repository instance (lazily initialized)
_job_repository: Optional[JobRepository] = None
_job_repository_lock = threading.Lock()

# Global LLM client instance (lazily initialized)
_llm_client: Optional[BaseLLMClient] = None
_llm_client_lock = threading.Lock()

# Flag to track if registry status has been logged
_registry_logged = False
_registry_log_lock = threading.Lock()


def get_job_store() -> JobRepository:
    """Get the global job repository instance for dependency injection.
    
    This function is used as a FastAPI dependency to provide the global
    job repository instance. Uses thread-safe lazy initialization.
    
    Returns:
        JobRepository: The global job repository instance.
    """
    global _job_repository
    
    # Fast path: return existing repository without acquiring lock
    if _job_repository is not None:
        return _job_repository
    
    # Slow path: acquire lock and initialize repository
    with _job_repository_lock:
        # Check again after acquiring lock (double-checked locking)
        if _job_repository is not None:
            return _job_repository
        
        logger.info("Initializing job repository")
        _job_repository = JobRepository()
        logger.info("Job repository initialized successfully")
        
        return _job_repository


def get_llm_client() -> BaseLLMClient:
    """Get the global LLM client instance for dependency injection.
    
    This function returns a singleton LLM client instance configured from
    application settings. The client is lazily initialized on first access.
    Uses thread-safe double-checked locking to ensure only one instance is created.
    
    The client is configured based on settings:
    - If a model registry is configured, uses the default model from registry
      with router-based multi-provider support
    - Otherwise, falls back to legacy single-model configuration:
      - API key from settings.llm_api_key
      - Model from settings.llm_model
      - Base URL from settings.llm_base_url (optional)
      - Timeout from settings.llm_timeout
    
    Returns:
        BaseLLMClient: The global LLM client instance.
        
    Raises:
        LLMConfigurationError: If LLM client cannot be initialized due to
            missing or invalid configuration.
    
    Note:
        Tests can override this dependency to provide a mock client.
        The implementation uses synchronous calls (time.sleep for backoff).
        If using in async contexts, consider running in a thread pool executor.
        
    Example:
        >>> from app.services.store_singleton import get_llm_client
        >>> client = get_llm_client()
        >>> result = client.generate_specs("Build a REST API")
    """
    global _llm_client, _registry_logged
    
    # Log model registry status once at startup
    with _registry_log_lock:
        if not _registry_logged:
            registry = get_model_registry()
            registry.log_registry_status()
            _registry_logged = True
    
    # Fast path: return existing client without acquiring lock
    if _llm_client is not None:
        return _llm_client
    
    # Slow path: acquire lock and initialize client
    with _llm_client_lock:
        # Check again after acquiring lock (double-checked locking)
        if _llm_client is not None:
            return _llm_client
        
        # Check if model registry is configured
        registry = get_model_registry()
        
        if registry.has_registry() and settings.default_model:
            # Use router-based multi-provider approach
            logger.info(
                "Initializing LLM client via model registry",
                extra={"default_model": settings.default_model}
            )
            
            try:
                # Import here to avoid circular dependency
                from app.services.llm_client import get_llm_client_for_model
                
                _llm_client = get_llm_client_for_model(
                    logical_model_id=settings.default_model,
                    cache_clients=True
                )
                
                logger.info(
                    "LLM client initialized via model registry",
                    extra={"default_model": settings.default_model}
                )
                
                return _llm_client
                
            except LLMConfigurationError:
                # Re-raise configuration errors as-is
                raise
            except Exception as e:
                logger.error(
                    "Failed to initialize LLM client via registry",
                    extra={"error": str(e), "error_type": type(e).__name__}
                )
                raise LLMConfigurationError(f"Failed to initialize LLM client: {e}")
        elif registry.has_registry() and not settings.default_model:
            # Registry exists but default_model is not set - log warning and fall back
            logger.warning(
                "Model registry is configured but default_model is not set, falling back to legacy configuration",
                extra={
                    "registry_size": len(registry._registry),
                    "available_models": list(registry._registry.keys())
                }
            )
            # Fall through to legacy configuration below
        else:
            # No registry configured - use legacy approach
            logger.info("No model registry configured, using legacy single-model configuration")
        
        # Legacy single-model configuration (used when registry not configured or default_model not set)
        # Validate API key is provided
        if not settings.llm_api_key:
            logger.error("LLM API key not configured")
            raise LLMConfigurationError(
                "LLM API key is not configured. Please set LLM_API_KEY environment variable."
            )
        
        # Initialize OpenAI client with settings (legacy default)
        try:
            _llm_client = OpenAIClient(
                api_key=settings.llm_api_key,
                model=settings.llm_model,
                base_url=settings.llm_base_url,
                timeout=settings.llm_timeout,
            )
            
            logger.info(
                "LLM client initialized from legacy settings",
                extra={
                    "model": settings.llm_model,
                    "has_base_url": bool(settings.llm_base_url),
                    "timeout": settings.llm_timeout,
                }
            )
            
            return _llm_client
            
        except LLMConfigurationError:
            # Re-raise configuration errors as-is
            raise
        except Exception as e:
            logger.error(
                "Failed to initialize LLM client",
                extra={"error": str(e), "error_type": type(e).__name__}
            )
            raise LLMConfigurationError(f"Failed to initialize LLM client: {e}")
