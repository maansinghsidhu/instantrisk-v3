"""
File Validation Utility

Provides comprehensive file validation to prevent:
- Malicious file uploads (executables, scripts)
- File type spoofing (wrong extension for content)
- Embedded scripts in documents (PDF JavaScript, macros)
- Oversized files that could cause resource exhaustion
"""

import logging
from pathlib import Path
from typing import Tuple, Optional, Set

logger = logging.getLogger("security.file_validator")


class FileValidationError(Exception):
    """Raised when file validation fails."""

    def __init__(self, message: str, code: str = "INVALID_FILE"):
        self.message = message
        self.code = code
        super().__init__(self.message)


# Allowed MIME types for document processing
ALLOWED_MIME_TYPES: Set[str] = {
    # PDF
    "application/pdf",

    # Images
    "image/jpeg",
    "image/png",
    "image/tiff",
    "image/gif",

    # Microsoft Office
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # .xlsx
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",  # .pptx
    "application/msword",  # .doc
    "application/vnd.ms-excel",  # .xls

    # Text
    "text/plain",
    "text/csv",
}

# Allowed file extensions
ALLOWED_EXTENSIONS: Set[str] = {
    ".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".gif",
    ".doc", ".docx", ".xls", ".xlsx", ".pptx",
    ".txt", ".csv",
}

# Dangerous extensions that should never be allowed
DANGEROUS_EXTENSIONS: Set[str] = {
    # Executables
    ".exe", ".dll", ".so", ".dylib", ".bin", ".com", ".msi",

    # Scripts
    ".sh", ".bash", ".zsh", ".bat", ".cmd", ".ps1", ".vbs", ".vbe",
    ".js", ".jse", ".ws", ".wsf", ".wsc", ".wsh",

    # Programming
    ".py", ".pyc", ".pyo", ".php", ".asp", ".aspx", ".jsp",
    ".pl", ".cgi", ".rb", ".lua",

    # Archives that could contain executables
    ".jar", ".war", ".ear",

    # Other dangerous
    ".scr", ".pif", ".application", ".gadget", ".hta", ".cpl",
    ".msc", ".inf", ".reg", ".lnk",
}

# Maximum file sizes
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB per file
MAX_TOTAL_SIZE = 50 * 1024 * 1024  # 50MB total per upload session

# Magic bytes for common file types
MAGIC_BYTES = {
    b"%PDF": "application/pdf",
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"GIF87a": "image/gif",
    b"GIF89a": "image/gif",
    b"II*\x00": "image/tiff",  # Little-endian TIFF
    b"MM\x00*": "image/tiff",  # Big-endian TIFF
    b"PK\x03\x04": "application/zip",  # ZIP (also docx, xlsx, pptx)
    b"\xd0\xcf\x11\xe0": "application/msword",  # Old Office format
}


def _get_mime_from_magic(content: bytes) -> Optional[str]:
    """Detect MIME type from magic bytes."""
    for magic, mime in MAGIC_BYTES.items():
        if content.startswith(magic):
            return mime
    return None


def _check_pdf_for_scripts(content: bytes) -> bool:
    """
    Check if PDF contains potentially dangerous JavaScript.

    Returns:
        True if dangerous content found
    """
    dangerous_patterns = [
        b"/JavaScript",
        b"/JS",
        b"/AA",  # Additional Actions
        b"/OpenAction",
        b"/Launch",
        b"/URI",
        b"/SubmitForm",
        b"/ImportData",
    ]

    for pattern in dangerous_patterns:
        if pattern in content:
            logger.warning(f"PDF contains suspicious pattern: {pattern}")
            return True

    return False


def _check_office_for_macros(content: bytes) -> bool:
    """
    Check if Office document contains macros.

    Returns:
        True if macros found
    """
    # VBA macro signatures
    macro_patterns = [
        b"vbaProject.bin",
        b"xl/vbaProject",
        b"word/vbaProject",
        b"_VBA_PROJECT",
    ]

    for pattern in macro_patterns:
        if pattern in content:
            logger.warning(f"Office document contains macros: {pattern}")
            return True

    return False


async def validate_file(
    content: bytes,
    filename: str,
    check_scripts: bool = True,
    max_size: int = MAX_FILE_SIZE,
) -> Tuple[bool, str, Optional[str]]:
    """
    Validate a file for security.

    Args:
        content: File content as bytes
        filename: Original filename
        check_scripts: Whether to check for embedded scripts
        max_size: Maximum allowed file size

    Returns:
        Tuple of (is_valid, message, detected_mime_type)

    Raises:
        FileValidationError: If validation fails
    """
    # 1. Check file size
    if len(content) > max_size:
        raise FileValidationError(
            f"File too large: {len(content) / 1024 / 1024:.1f}MB exceeds {max_size / 1024 / 1024:.1f}MB limit",
            code="FILE_TOO_LARGE"
        )

    if len(content) == 0:
        raise FileValidationError("Empty file", code="EMPTY_FILE")

    # 2. Check extension
    ext = Path(filename).suffix.lower()

    if ext in DANGEROUS_EXTENSIONS:
        raise FileValidationError(
            f"Dangerous file type not allowed: {ext}",
            code="DANGEROUS_EXTENSION"
        )

    if ext not in ALLOWED_EXTENSIONS:
        raise FileValidationError(
            f"File type not supported: {ext}",
            code="UNSUPPORTED_EXTENSION"
        )

    # 3. Check MIME type from magic bytes
    detected_mime = _get_mime_from_magic(content)

    # Try python-magic if available
    try:
        import magic
        detected_mime = magic.from_buffer(content, mime=True)
    except ImportError:
        pass  # Use our basic detection
    except Exception as e:
        logger.warning(f"Magic library error: {e}")

    if detected_mime and detected_mime not in ALLOWED_MIME_TYPES:
        # Special case for ZIP-based formats (docx, xlsx, pptx)
        if detected_mime == "application/zip" and ext in {".docx", ".xlsx", ".pptx"}:
            pass  # OK - these are ZIP-based
        else:
            raise FileValidationError(
                f"File content type not allowed: {detected_mime}",
                code="INVALID_MIME_TYPE"
            )

    # 4. Check for extension/content mismatch
    if detected_mime:
        expected_mimes = {
            ".pdf": {"application/pdf"},
            ".jpg": {"image/jpeg"},
            ".jpeg": {"image/jpeg"},
            ".png": {"image/png"},
            ".gif": {"image/gif"},
            ".tiff": {"image/tiff"},
            ".tif": {"image/tiff"},
            ".docx": {"application/zip", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
            ".xlsx": {"application/zip", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
            ".doc": {"application/msword"},
            ".xls": {"application/vnd.ms-excel"},
        }

        if ext in expected_mimes and detected_mime not in expected_mimes[ext]:
            raise FileValidationError(
                f"File extension {ext} does not match content type {detected_mime}",
                code="MIME_MISMATCH"
            )

    # 5. Check for embedded scripts/macros
    if check_scripts:
        if detected_mime == "application/pdf":
            if _check_pdf_for_scripts(content):
                raise FileValidationError(
                    "PDF contains embedded scripts which are not allowed",
                    code="PDF_SCRIPTS"
                )

        if ext in {".docx", ".xlsx", ".pptx", ".doc", ".xls"}:
            if _check_office_for_macros(content):
                raise FileValidationError(
                    "Office document contains macros which are not allowed",
                    code="OFFICE_MACROS"
                )

    logger.info(f"File validated: {filename}, size={len(content)}, mime={detected_mime}")
    return True, "File validated successfully", detected_mime


async def validate_upload_batch(
    files: list,
    max_total_size: int = MAX_TOTAL_SIZE,
    max_files: int = 10,
) -> Tuple[bool, str]:
    """
    Validate a batch of files.

    Args:
        files: List of (content, filename) tuples
        max_total_size: Maximum total size for all files
        max_files: Maximum number of files

    Returns:
        Tuple of (is_valid, message)
    """
    if len(files) > max_files:
        raise FileValidationError(
            f"Too many files: {len(files)} exceeds limit of {max_files}",
            code="TOO_MANY_FILES"
        )

    total_size = sum(len(content) for content, _ in files)
    if total_size > max_total_size:
        raise FileValidationError(
            f"Total size {total_size / 1024 / 1024:.1f}MB exceeds limit of {max_total_size / 1024 / 1024:.1f}MB",
            code="TOTAL_SIZE_EXCEEDED"
        )

    # Validate each file
    for content, filename in files:
        await validate_file(content, filename)

    return True, f"Validated {len(files)} files successfully"
