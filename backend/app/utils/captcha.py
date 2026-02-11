"""
CAPTCHA Verification Utility

Integrates with mCaptcha - a fully self-hosted, open-source CAPTCHA solution.
mCaptcha uses proof-of-work instead of image recognition.

Setup mCaptcha Server (Docker):
    docker run -d --name mcaptcha \
        -p 7000:7000 \
        -e MCAPTCHA_SERVER_DOMAIN=captcha.yourdomain.com \
        mcaptcha/mcaptcha:latest

Frontend Integration:
    <script src="https://captcha.yourdomain.com/widget/index.js"></script>
    <div class="mcaptcha" data-sitekey="YOUR_SITEKEY"></div>
"""

import logging
from typing import Optional, Tuple
import httpx

from app.config import settings

logger = logging.getLogger("security.captcha")


class CaptchaConfig:
    """CAPTCHA configuration."""

    # mCaptcha server URL (configure in .env)
    SERVER_URL: str = getattr(settings, 'MCAPTCHA_URL', 'http://localhost:7000')

    # Site key and secret (configure in .env)
    SITE_KEY: str = getattr(settings, 'MCAPTCHA_SITE_KEY', '')
    SECRET_KEY: str = getattr(settings, 'MCAPTCHA_SECRET_KEY', '')

    # Enable/disable CAPTCHA (useful for development)
    ENABLED: bool = getattr(settings, 'CAPTCHA_ENABLED', False)

    # Timeout for verification requests
    TIMEOUT: int = 10


async def verify_captcha(token: str, ip_address: Optional[str] = None) -> Tuple[bool, str]:
    """
    Verify a CAPTCHA token from the frontend.

    Args:
        token: CAPTCHA token from frontend widget
        ip_address: Client IP address (optional, for logging)

    Returns:
        Tuple of (is_valid, message)
    """
    # If CAPTCHA is disabled, always pass
    if not CaptchaConfig.ENABLED:
        logger.debug("CAPTCHA disabled, skipping verification")
        return True, "CAPTCHA disabled"

    if not token:
        logger.warning(f"Missing CAPTCHA token from IP: {ip_address}")
        return False, "CAPTCHA token required"

    if not CaptchaConfig.SECRET_KEY:
        logger.error("CAPTCHA secret key not configured")
        return True, "CAPTCHA not configured"

    try:
        async with httpx.AsyncClient(timeout=CaptchaConfig.TIMEOUT) as client:
            response = await client.post(
                f"{CaptchaConfig.SERVER_URL}/api/v1/pow/siteverify",
                json={
                    "secret": CaptchaConfig.SECRET_KEY,
                    "token": token,
                }
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("valid", False):
                    logger.debug(f"CAPTCHA verified successfully for IP: {ip_address}")
                    return True, "Valid"
                else:
                    logger.warning(f"CAPTCHA verification failed for IP: {ip_address}")
                    return False, "Invalid CAPTCHA"
            else:
                logger.error(f"CAPTCHA server error: {response.status_code}")
                # Fail open - allow if server error
                return True, "Verification server error"

    except httpx.TimeoutException:
        logger.error("CAPTCHA verification timeout")
        return True, "Verification timeout"
    except Exception as e:
        logger.error(f"CAPTCHA verification error: {e}")
        return True, f"Verification error: {str(e)}"


def get_captcha_config() -> dict:
    """
    Get CAPTCHA configuration for frontend.

    Returns:
        Dict with site key and server URL
    """
    return {
        "enabled": CaptchaConfig.ENABLED,
        "site_key": CaptchaConfig.SITE_KEY,
        "server_url": CaptchaConfig.SERVER_URL,
    }


# Alternative: Simple proof-of-work CAPTCHA (no external server needed)
# This is a fallback if mCaptcha is not set up

import hashlib
import secrets
import time


class SimplePoWCaptcha:
    """
    Simple proof-of-work CAPTCHA that doesn't require external server.

    The client must find a nonce that, when combined with the challenge,
    produces a hash with a certain number of leading zeros.
    """

    # Number of leading zeros required (difficulty)
    # 4 = ~16 attempts avg, 5 = ~32 attempts, 6 = ~64 attempts
    DIFFICULTY = 4

    # Challenge validity period (seconds)
    VALIDITY_PERIOD = 300  # 5 minutes

    @staticmethod
    def generate_challenge() -> dict:
        """
        Generate a new challenge for the client.

        Returns:
            Dict with challenge string and timestamp
        """
        challenge = secrets.token_hex(16)
        timestamp = int(time.time())

        return {
            "challenge": challenge,
            "timestamp": timestamp,
            "difficulty": SimplePoWCaptcha.DIFFICULTY,
        }

    @staticmethod
    def verify_solution(challenge: str, timestamp: int, nonce: str) -> Tuple[bool, str]:
        """
        Verify a proof-of-work solution.

        Args:
            challenge: Original challenge string
            timestamp: Challenge timestamp
            nonce: Client's solution

        Returns:
            Tuple of (is_valid, message)
        """
        # Check timestamp
        current_time = int(time.time())
        if current_time - timestamp > SimplePoWCaptcha.VALIDITY_PERIOD:
            return False, "Challenge expired"

        # Check proof of work
        data = f"{challenge}{timestamp}{nonce}"
        hash_result = hashlib.sha256(data.encode()).hexdigest()

        # Check for required leading zeros
        required_prefix = "0" * SimplePoWCaptcha.DIFFICULTY
        if hash_result.startswith(required_prefix):
            return True, "Valid"
        else:
            return False, "Invalid solution"


# Global simple CAPTCHA instance
_simple_captcha = SimplePoWCaptcha()


def get_simple_challenge() -> dict:
    """Get a simple PoW challenge."""
    return _simple_captcha.generate_challenge()


def verify_simple_solution(challenge: str, timestamp: int, nonce: str) -> Tuple[bool, str]:
    """Verify a simple PoW solution."""
    return _simple_captcha.verify_solution(challenge, timestamp, nonce)
