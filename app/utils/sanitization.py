"""Sanitization utilities for user input."""

import logging
import re
import unicodedata
from typing import Optional

logger = logging.getLogger(__name__)


# Maximum lengths for sanitized output in logs
MAX_LOG_DESCRIPTION_LENGTH = 100
MAX_LOG_SYSTEM_PROMPT_LENGTH = 200


def has_control_characters(text: str) -> bool:
    """Check if text contains control characters (excluding common whitespace).
    
    Control characters can cause issues in logs and parsing. This function
    identifies ASCII control characters (0x00-0x1F except tab, newline, carriage return)
    and Unicode control characters in other categories.
    
    Args:
        text: The text to check.
        
    Returns:
        True if text contains disallowed control characters, False otherwise.
    """
    # Allow tab (0x09), newline (0x0A), and carriage return (0x0D)
    allowed_control_chars = {'\t', '\n', '\r'}
    
    for char in text:
        # Check ASCII control characters
        if ord(char) < 0x20 and char not in allowed_control_chars:
            return True
        
        # Check Unicode control characters (category Cc, excluding allowed ones)
        if unicodedata.category(char) == 'Cc' and char not in allowed_control_chars:
            return True
    
    return False


def count_unicode_codepoints(text: str) -> int:
    """Count Unicode code points in text.
    
    This counts actual characters rather than bytes, which is important
    for multi-byte UTF-8 characters like emojis.
    
    Args:
        text: The text to count.
        
    Returns:
        Number of Unicode code points.
    """
    return len(text)


def sanitize_for_logging(
    text: str, 
    max_length: int = MAX_LOG_DESCRIPTION_LENGTH,
    redact: bool = False
) -> str:
    """Sanitize text for safe logging.
    
    Truncates text to a reasonable length and optionally redacts content
    to avoid logging sensitive information.
    
    Args:
        text: The text to sanitize.
        max_length: Maximum length to keep (default: 100 chars).
        redact: If True, shows only length and hash instead of content.
        
    Returns:
        Sanitized text safe for logging.
    """
    if redact:
        return f"<redacted length={len(text)} chars>"
    
    if len(text) <= max_length:
        return text
    
    return f"{text[:max_length]}... (truncated, total length: {len(text)} chars)"


def validate_description_content(description: str) -> tuple[bool, Optional[str]]:
    """Validate description content for disallowed patterns.
    
    Checks for:
    - Control characters (except tab, newline, carriage return)
    - Null bytes
    
    Args:
        description: The description to validate.
        
    Returns:
        Tuple of (is_valid, error_message). error_message is None if valid.
    """
    # Check for control characters
    if has_control_characters(description):
        return False, "Description contains disallowed control characters"
    
    # Check for null bytes (should be caught by control char check but be explicit)
    if '\x00' in description:
        return False, "Description contains null bytes"
    
    return True, None


def validate_description_length(
    description: str, 
    max_bytes: int
) -> tuple[bool, Optional[str]]:
    """Validate description length in bytes.
    
    Args:
        description: The description to validate.
        max_bytes: Maximum allowed size in bytes (UTF-8 encoded).
        
    Returns:
        Tuple of (is_valid, error_message). error_message is None if valid.
    """
    byte_length = len(description.encode('utf-8'))
    
    if byte_length > max_bytes:
        return False, (
            f"Description exceeds maximum length of {max_bytes} bytes "
            f"(current: {byte_length} bytes)"
        )
    
    return True, None


def validate_string_not_empty(value: str, field_name: str = "Field") -> tuple[bool, Optional[str]]:
    """Validate that a string is not empty or whitespace-only.
    
    Args:
        value: The string to validate.
        field_name: Name of the field for error messages.
        
    Returns:
        Tuple of (is_valid, error_message). error_message is None if valid.
    """
    if not value or not value.strip():
        return False, f"{field_name} cannot be empty or whitespace-only"
    
    return True, None
