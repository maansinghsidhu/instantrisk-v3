"""
InstantRisk V5 - Security Utilities

Enterprise-grade security utilities:
- File validation (MIME, extensions, script detection)
- Input sanitization (XSS, prompt injection)
- Token blacklist (Redis-based)
- Antivirus scanning (ClamAV)
- CAPTCHA verification (mCaptcha / PoW)
"""

from .file_validator import (
    validate_file,
    validate_upload_batch,
    FileValidationError,
    ALLOWED_MIME_TYPES,
    ALLOWED_EXTENSIONS,
    MAX_FILE_SIZE,
)
from .sanitizer import (
    sanitize_user_input,
    sanitize_for_ai,
    sanitize_filename,
    sanitize_json_string,
    sanitize_log_message,
)
from .token_blacklist import (
    blacklist_token,
    is_token_blacklisted,
    get_blacklist_stats,
)
from .antivirus import (
    scan_file_content,
    get_scanner,
    test_antivirus,
    AntivirusScanner,
)
from .captcha import (
    verify_captcha,
    get_captcha_config,
    get_simple_challenge,
    verify_simple_solution,
)

__all__ = [
    # File Validation
    "validate_file",
    "validate_upload_batch",
    "FileValidationError",
    "ALLOWED_MIME_TYPES",
    "ALLOWED_EXTENSIONS",
    "MAX_FILE_SIZE",

    # Sanitization
    "sanitize_user_input",
    "sanitize_for_ai",
    "sanitize_filename",
    "sanitize_json_string",
    "sanitize_log_message",

    # Token Blacklist
    "blacklist_token",
    "is_token_blacklisted",
    "get_blacklist_stats",

    # Antivirus
    "scan_file_content",
    "get_scanner",
    "test_antivirus",
    "AntivirusScanner",

    # CAPTCHA
    "verify_captcha",
    "get_captcha_config",
    "get_simple_challenge",
    "verify_simple_solution",
]
