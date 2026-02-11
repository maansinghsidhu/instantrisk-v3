"""
Input Sanitization Utility

Provides input sanitization to prevent:
- XSS attacks
- SQL injection (backup to ORM)
- Prompt injection attacks on AI
- Control character injection
"""

import re
import html
import logging
from typing import Optional

logger = logging.getLogger("security.sanitizer")


def sanitize_user_input(
    text: str,
    max_length: int = 10000,
    allow_html: bool = False,
    strip_control_chars: bool = True,
) -> str:
    """
    Sanitize general user input.

    Args:
        text: Input text to sanitize
        max_length: Maximum allowed length
        allow_html: Whether to preserve HTML (default: escape it)
        strip_control_chars: Whether to remove control characters

    Returns:
        Sanitized text
    """
    if not text:
        return ""

    # 1. Truncate to max length
    if len(text) > max_length:
        text = text[:max_length]
        logger.info(f"Input truncated to {max_length} characters")

    # 2. Remove null bytes
    text = text.replace("\x00", "")

    # 3. Remove control characters (except newline, tab, carriage return)
    if strip_control_chars:
        # Keep: \t (0x09), \n (0x0a), \r (0x0d)
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)

    # 4. Escape HTML entities
    if not allow_html:
        text = html.escape(text)

    # 5. Normalize whitespace (remove excessive spaces)
    text = re.sub(r' {3,}', '  ', text)  # Max 2 consecutive spaces
    text = re.sub(r'\n{4,}', '\n\n\n', text)  # Max 3 consecutive newlines

    return text.strip()


def sanitize_for_ai(
    text: str,
    max_length: int = 50000,
    filter_injection: bool = True,
) -> str:
    """
    Sanitize text before sending to AI models.

    Filters potential prompt injection patterns while preserving
    legitimate content.

    Args:
        text: Input text to sanitize
        max_length: Maximum allowed length
        filter_injection: Whether to filter prompt injection patterns

    Returns:
        Sanitized text safe for AI processing
    """
    if not text:
        return ""

    # Basic sanitization first
    text = sanitize_user_input(text, max_length=max_length, allow_html=False)

    if not filter_injection:
        return text

    # Prompt injection patterns to filter
    # These are common patterns used to manipulate AI behavior
    injection_patterns = [
        # Direct instruction override attempts
        (r'ignore\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions?|prompts?|rules?|text)', '[FILTERED]'),
        (r'disregard\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions?|prompts?)', '[FILTERED]'),
        (r'forget\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions?|prompts?)', '[FILTERED]'),

        # System prompt extraction attempts
        (r'(print|show|display|reveal|output)\s+(your\s+)?(system\s+)?(prompt|instructions?)', '[FILTERED]'),
        (r'what\s+(are|is)\s+your\s+(system\s+)?(prompt|instructions?)', '[FILTERED]'),

        # Role override attempts
        (r'you\s+are\s+now\s+(?:a|an|the)\s+', '[FILTERED]'),
        (r'act\s+as\s+(?:a|an|if)\s+', '[FILTERED]'),
        (r'pretend\s+(to\s+be|you\s+are)\s+', '[FILTERED]'),

        # System message injection
        (r'<\|?(system|assistant|user)\|?>', '[FILTERED]'),
        (r'\[\[(system|assistant|user)\]\]', '[FILTERED]'),
        (r'###\s*(system|assistant|user)\s*:', '[FILTERED]'),

        # Delimiter injection
        (r'-{5,}', '---'),  # Reduce long dashes
        (r'={5,}', '==='),  # Reduce long equals
        (r'\*{5,}', '***'),  # Reduce long asterisks
    ]

    for pattern, replacement in injection_patterns:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    # Log if filtering occurred
    if '[FILTERED]' in text:
        logger.warning("Potential prompt injection attempt filtered")

    return text


def sanitize_filename(filename: str, max_length: int = 255) -> str:
    """
    Sanitize a filename for safe storage.

    Args:
        filename: Original filename
        max_length: Maximum filename length

    Returns:
        Safe filename
    """
    if not filename:
        return "unnamed_file"

    # Remove path components
    filename = filename.replace("\\", "/").split("/")[-1]

    # Remove null bytes and control characters
    filename = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', filename)

    # Replace dangerous characters
    dangerous_chars = ['<', '>', ':', '"', '|', '?', '*', '/', '\\']
    for char in dangerous_chars:
        filename = filename.replace(char, '_')

    # Remove leading/trailing dots and spaces
    filename = filename.strip('. ')

    # Truncate if too long (preserve extension)
    if len(filename) > max_length:
        name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
        max_name_length = max_length - len(ext) - 1  # -1 for the dot
        filename = f"{name[:max_name_length]}.{ext}" if ext else name[:max_length]

    # Default name if empty
    if not filename or filename == '.':
        filename = "unnamed_file"

    return filename


def sanitize_json_string(text: str) -> str:
    """
    Sanitize a string for safe JSON inclusion.

    Args:
        text: Input text

    Returns:
        JSON-safe string
    """
    if not text:
        return ""

    # Escape special JSON characters
    text = text.replace('\\', '\\\\')
    text = text.replace('"', '\\"')
    text = text.replace('\n', '\\n')
    text = text.replace('\r', '\\r')
    text = text.replace('\t', '\\t')

    # Remove null bytes
    text = text.replace('\x00', '')

    return text


def sanitize_log_message(message: str, max_length: int = 1000) -> str:
    """
    Sanitize a message for safe logging.

    Prevents log injection attacks.

    Args:
        message: Message to log
        max_length: Maximum message length

    Returns:
        Safe log message
    """
    if not message:
        return ""

    # Truncate
    message = message[:max_length]

    # Remove newlines (prevent log injection)
    message = message.replace('\n', ' ').replace('\r', ' ')

    # Remove ANSI escape codes
    message = re.sub(r'\x1b\[[0-9;]*m', '', message)

    # Remove other control characters
    message = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', message)

    return message
