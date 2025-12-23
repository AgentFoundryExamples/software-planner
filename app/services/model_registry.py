"""Model registry helper for managing multi-provider LLM configurations.

This module provides utilities for accessing and managing the logical model registry,
allowing routing logic to query model configurations without duplicating parsing logic.
"""

import logging
from typing import Optional

from app.core.config import ModelConfig, settings


logger = logging.getLogger(__name__)


class ModelRegistry:
    """Helper class for accessing logical model configurations.
    
    Provides convenient methods for retrieving model configurations from the registry,
    checking model availability, and accessing the default model.
    """
    
    def __init__(self):
        """Initialize the model registry from application settings."""
        self._registry = settings.models_registry
        self._default_model = settings.default_model
    
    def get_model_config(self, logical_name: str) -> Optional[ModelConfig]:
        """Get configuration for a specific logical model.
        
        Args:
            logical_name: Logical name of the model to retrieve.
            
        Returns:
            ModelConfig if found, None otherwise.
        """
        return self._registry.get(logical_name)
    
    def get_enabled_models(self) -> dict[str, ModelConfig]:
        """Get all enabled model configurations.
        
        Returns:
            Dictionary mapping logical names to ModelConfig for all enabled models.
        """
        return {
            name: config 
            for name, config in self._registry.items() 
            if config.enabled
        }
    
    def get_disabled_models(self) -> dict[str, ModelConfig]:
        """Get all disabled model configurations.
        
        Returns:
            Dictionary mapping logical names to ModelConfig for all disabled models.
        """
        return {
            name: config 
            for name, config in self._registry.items() 
            if not config.enabled
        }
    
    def get_default_model(self) -> Optional[str]:
        """Get the logical name of the default model.
        
        Returns:
            Logical name of the default model, or None if not configured.
        """
        return self._default_model
    
    def get_default_model_config(self) -> Optional[ModelConfig]:
        """Get the configuration for the default model.
        
        Returns:
            ModelConfig for the default model, or None if not configured.
        """
        if not self._default_model:
            return None
        return self.get_model_config(self._default_model)
    
    def is_model_enabled(self, logical_name: str) -> bool:
        """Check if a model is enabled.
        
        Args:
            logical_name: Logical name of the model to check.
            
        Returns:
            True if the model exists and is enabled, False otherwise.
        """
        config = self.get_model_config(logical_name)
        return config is not None and config.enabled
    
    def get_models_by_provider(self, provider: str) -> dict[str, ModelConfig]:
        """Get all models for a specific provider.
        
        Args:
            provider: Provider identifier (e.g., 'openai', 'anthropic', 'google').
            
        Returns:
            Dictionary mapping logical names to ModelConfig for all models from the provider.
        """
        provider_lower = provider.lower()
        return {
            name: config 
            for name, config in self._registry.items() 
            if config.provider.lower() == provider_lower
        }
    
    def has_registry(self) -> bool:
        """Check if a model registry is configured.
        
        Returns:
            True if at least one model is in the registry, False otherwise.
        """
        return len(self._registry) > 0
    
    def log_registry_status(self) -> None:
        """Log the current status of the model registry.
        
        Emits INFO level logs summarizing enabled and disabled models,
        useful for startup diagnostics and telemetry.
        """
        if not self.has_registry():
            logger.info("Model registry: Not configured (using legacy single model configuration)")
            return
        
        enabled = self.get_enabled_models()
        disabled = self.get_disabled_models()
        
        logger.info(
            f"Model registry initialized: {len(enabled)} enabled, {len(disabled)} disabled",
            extra={
                "enabled_count": len(enabled),
                "disabled_count": len(disabled),
                "default_model": self._default_model,
                "total_models": len(self._registry)
            }
        )
        
        # Log each enabled model
        for name, config in enabled.items():
            is_default = (name == self._default_model)
            logger.info(
                f"Model enabled: {name}",
                extra={
                    "logical_name": name,
                    "provider": config.provider,
                    "model_id": config.model_id,
                    "is_default": is_default,
                    "timeout": config.timeout,
                    "max_retries": config.max_retries,
                    "has_base_url": config.base_url is not None
                }
            )
        
        # Log disabled models at debug level
        for name, config in disabled.items():
            logger.debug(
                f"Model disabled: {name}",
                extra={
                    "logical_name": name,
                    "provider": config.provider,
                    "model_id": config.model_id
                }
            )


# Global registry instance
_model_registry: Optional[ModelRegistry] = None


def get_model_registry() -> ModelRegistry:
    """Get the global model registry instance.
    
    This function returns a singleton ModelRegistry instance that provides
    access to the configured logical models and their metadata.
    
    Returns:
        ModelRegistry: The global model registry instance.
    """
    global _model_registry
    if _model_registry is None:
        _model_registry = ModelRegistry()
    return _model_registry
