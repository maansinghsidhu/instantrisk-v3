"""
Antivirus Scanning Utility

Integrates with ClamAV daemon for malware scanning of uploaded files.
ClamAV is an open-source antivirus engine.

Setup:
    apt-get install clamav-daemon clamav-freshclam
    systemctl enable clamav-daemon
    systemctl start clamav-daemon
    freshclam  # Update virus definitions
"""

from __future__ import annotations

import io
import logging
from typing import Tuple, Optional, Any
from pathlib import Path

logger = logging.getLogger("security.antivirus")

# Try to import clamd, gracefully handle if not installed
try:
    import clamd
    CLAMD_AVAILABLE = True
except ImportError:
    clamd = None  # type: ignore
    CLAMD_AVAILABLE = False
    logger.warning("clamd not installed. Antivirus scanning disabled.")


class AntivirusScanner:
    """ClamAV antivirus scanner wrapper."""

    def __init__(self, socket_path: str = "/var/run/clamav/clamd.ctl"):
        """
        Initialize ClamAV scanner.

        Args:
            socket_path: Path to ClamAV Unix socket
        """
        self.socket_path = socket_path
        self._client: Any = None
        self._available = CLAMD_AVAILABLE

    def _get_client(self) -> Any:
        """Get or create ClamAV client."""
        if not self._available:
            return None

        if self._client is None:
            try:
                self._client = clamd.ClamdUnixSocket(path=self.socket_path)
                # Test connection
                self._client.ping()
            except Exception as e:
                logger.error(f"Failed to connect to ClamAV: {e}")
                self._client = None

        return self._client

    async def scan_bytes(self, content: bytes) -> Tuple[bool, str]:
        """
        Scan file content for malware.

        Args:
            content: File content as bytes

        Returns:
            Tuple of (is_clean, message)
            is_clean: True if no malware detected
            message: "Clean" or description of threat
        """
        if not self._available:
            logger.debug("Antivirus not available, skipping scan")
            return True, "Scan skipped (ClamAV not available)"

        client = self._get_client()
        if client is None:
            logger.warning("ClamAV daemon not accessible, skipping scan")
            return True, "Scan skipped (daemon not running)"

        try:
            # Scan using instream (memory-based scanning)
            result = client.instream(io.BytesIO(content))

            # Result format: {'stream': ('OK', None)} or {'stream': ('FOUND', 'Virus.Name')}
            status, virus_name = result.get('stream', ('UNKNOWN', None))

            if status == 'OK':
                logger.debug("File scan: Clean")
                return True, "Clean"
            elif status == 'FOUND':
                logger.warning(f"MALWARE DETECTED: {virus_name}")
                return False, f"Malware detected: {virus_name}"
            else:
                logger.warning(f"Unexpected scan result: {status}")
                return True, f"Scan result: {status}"

        except Exception as e:
            logger.error(f"Antivirus scan error: {e}")
            # Fail open - allow file if scan fails
            # In high-security environments, you might want to fail closed instead
            return True, f"Scan error: {str(e)}"

    async def scan_file(self, file_path: str) -> Tuple[bool, str]:
        """
        Scan a file on disk for malware.

        Args:
            file_path: Path to file

        Returns:
            Tuple of (is_clean, message)
        """
        if not self._available:
            return True, "Scan skipped (ClamAV not available)"

        client = self._get_client()
        if client is None:
            return True, "Scan skipped (daemon not running)"

        try:
            # Use scan for file-based scanning
            result = client.scan(file_path)

            if result is None:
                return True, "Clean"

            # Result format: {'/path/to/file': ('FOUND', 'Virus.Name')}
            for path, (status, virus_name) in result.items():
                if status == 'FOUND':
                    logger.warning(f"MALWARE DETECTED in {path}: {virus_name}")
                    return False, f"Malware detected: {virus_name}"

            return True, "Clean"

        except Exception as e:
            logger.error(f"Antivirus scan error: {e}")
            return True, f"Scan error: {str(e)}"

    def is_available(self) -> bool:
        """Check if ClamAV is available and running."""
        if not self._available:
            return False

        client = self._get_client()
        if client is None:
            return False

        try:
            client.ping()
            return True
        except:
            return False

    def get_version(self) -> Optional[str]:
        """Get ClamAV version info."""
        if not self._available:
            return None

        client = self._get_client()
        if client is None:
            return None

        try:
            return client.version()
        except:
            return None


# Global scanner instance
_scanner: Optional[AntivirusScanner] = None


def get_scanner() -> AntivirusScanner:
    """Get global antivirus scanner instance."""
    global _scanner
    if _scanner is None:
        _scanner = AntivirusScanner()
    return _scanner


async def scan_file_content(content: bytes, filename: str = "unknown") -> Tuple[bool, str]:
    """
    Convenience function to scan file content.

    Args:
        content: File content as bytes
        filename: Original filename (for logging)

    Returns:
        Tuple of (is_clean, message)
    """
    scanner = get_scanner()
    is_clean, message = await scanner.scan_bytes(content)

    if not is_clean:
        logger.warning(f"Blocked malicious file upload: {filename} - {message}")

    return is_clean, message


# EICAR test string for testing antivirus detection
# This is a standard test file that all antivirus should detect
EICAR_TEST_STRING = (
    b'X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*'
)


async def test_antivirus() -> dict:
    """
    Test antivirus functionality using EICAR test file.

    Returns:
        Dict with test results
    """
    scanner = get_scanner()

    results = {
        "available": scanner.is_available(),
        "version": scanner.get_version(),
        "eicar_test": None,
        "clean_test": None,
    }

    if scanner.is_available():
        # Test with EICAR (should be detected)
        is_clean, message = await scanner.scan_bytes(EICAR_TEST_STRING)
        results["eicar_test"] = {
            "detected": not is_clean,
            "message": message,
            "passed": not is_clean,  # EICAR should be detected
        }

        # Test with clean content
        clean_content = b"This is a clean test file with no malware."
        is_clean, message = await scanner.scan_bytes(clean_content)
        results["clean_test"] = {
            "detected": not is_clean,
            "message": message,
            "passed": is_clean,  # Clean file should pass
        }

    return results
