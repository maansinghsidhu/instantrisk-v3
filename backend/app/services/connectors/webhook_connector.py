"""
InstantRisk V3 - Webhook Connector

Sends outbound webhook notifications to external systems.
Enables real-time event notifications for:
- Risk assessment completion
- Quote generation
- Placement updates
- Compliance alerts
"""

import aiohttp
import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import logging

from app.services.connectors.base_connector import (
    BaseConnector,
    ConnectorConfig,
    SyncResult,
)

logger = logging.getLogger(__name__)


class WebhookConnector(BaseConnector):
    """
    Outbound webhook connector for event notifications.

    Features:
    - HMAC signature verification
    - Retry with exponential backoff
    - Event filtering
    - Delivery tracking
    """

    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        self._session: Optional[aiohttp.ClientSession] = None
        self._delivery_log: List[Dict] = []

    @property
    def webhook_url(self) -> str:
        """Get target webhook URL."""
        return self.config.base_url or ""

    @property
    def secret_key(self) -> Optional[str]:
        """Get HMAC secret for signature."""
        return self.config.extra.get("secret_key")

    @property
    def event_filter(self) -> List[str]:
        """Get list of events to send (empty = all)."""
        return self.config.extra.get("event_filter", [])

    async def _connect(self) -> bool:
        """Create aiohttp session for webhook delivery."""
        headers = dict(self.config.headers)
        headers.setdefault("Content-Type", "application/json")
        headers.setdefault("User-Agent", "InstantRisk-Webhook/1.0")

        timeout = aiohttp.ClientTimeout(total=self.config.timeout)
        self._session = aiohttp.ClientSession(
            headers=headers,
            timeout=timeout,
        )
        return True

    async def _disconnect(self) -> bool:
        """Close aiohttp session."""
        if self._session:
            await self._session.close()
            self._session = None
        return True

    async def _push(self, data: Dict[str, Any], endpoint: str) -> Dict[str, Any]:
        """Send webhook payload."""
        if not self._session:
            raise ConnectionError("Not connected")

        url = endpoint if endpoint.startswith("http") else f"{self.webhook_url}{endpoint}"
        headers = {}

        # Add timestamp
        timestamp = datetime.now(timezone.utc).isoformat()
        data["timestamp"] = timestamp

        # Create signature if secret key configured
        if self.secret_key:
            payload_bytes = json.dumps(data, sort_keys=True).encode()
            signature = hmac.new(
                self.secret_key.encode(),
                payload_bytes,
                hashlib.sha256
            ).hexdigest()
            headers["X-InstantRisk-Signature"] = f"sha256={signature}"
            headers["X-InstantRisk-Timestamp"] = timestamp

        async with self._session.post(url, json=data, headers=headers) as response:
            delivery_record = {
                "url": url,
                "event": data.get("event_type"),
                "status_code": response.status,
                "timestamp": timestamp,
                "success": response.status < 400,
            }
            self._delivery_log.append(delivery_record)

            if response.status >= 400:
                error_text = await response.text()
                logger.warning(f"Webhook delivery failed: {response.status} - {error_text[:200]}")
                raise aiohttp.ClientResponseError(
                    response.request_info,
                    response.history,
                    status=response.status,
                    message=error_text[:200],
                )

            return {
                "delivered": True,
                "status_code": response.status,
                "timestamp": timestamp,
            }

    async def _pull(self, query: Dict[str, Any]) -> Dict[str, Any]:
        """Webhooks are push-only, return delivery log."""
        return {
            "delivery_log": self._delivery_log[-100:],  # Last 100 deliveries
            "total_deliveries": len(self._delivery_log),
        }

    async def _healthcheck(self) -> bool:
        """Verify webhook endpoint is reachable."""
        if not self._session or not self.webhook_url:
            return False

        try:
            # Try HEAD request first (less invasive)
            async with self._session.head(self.webhook_url) as response:
                return response.status < 500
        except aiohttp.ClientError:
            # Fall back to OPTIONS
            try:
                async with self._session.options(self.webhook_url) as response:
                    return response.status < 500
            except aiohttp.ClientError:
                return False

    async def send_event(
        self,
        event_type: str,
        payload: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Send a webhook event.

        Args:
            event_type: Type of event (e.g., "assessment.completed").
            payload: Event payload data.
            metadata: Optional metadata.

        Returns:
            Delivery result.
        """
        # Check event filter
        if self.event_filter and event_type not in self.event_filter:
            logger.debug(f"Event {event_type} filtered out for webhook {self.name}")
            return {"delivered": False, "reason": "filtered"}

        data = {
            "event_type": event_type,
            "payload": payload,
            "metadata": metadata or {},
            "source": "instantrisk",
        }

        return await self.push(data, self.webhook_url)

    def get_delivery_stats(self) -> Dict[str, Any]:
        """Get webhook delivery statistics."""
        if not self._delivery_log:
            return {
                "total": 0,
                "successful": 0,
                "failed": 0,
                "success_rate": 0.0,
            }

        successful = sum(1 for d in self._delivery_log if d.get("success"))
        total = len(self._delivery_log)

        return {
            "total": total,
            "successful": successful,
            "failed": total - successful,
            "success_rate": (successful / total * 100) if total > 0 else 0.0,
            "last_delivery": self._delivery_log[-1] if self._delivery_log else None,
        }


# Predefined event types
class WebhookEvents:
    """Standard webhook event types."""
    # Assessment events
    ASSESSMENT_CREATED = "assessment.created"
    ASSESSMENT_COMPLETED = "assessment.completed"
    ASSESSMENT_UPDATED = "assessment.updated"

    # Risk analysis events
    RISK_SCORED = "risk.scored"
    RISK_APPROVED = "risk.approved"
    RISK_DECLINED = "risk.declined"

    # Quote events
    QUOTE_GENERATED = "quote.generated"
    QUOTE_ACCEPTED = "quote.accepted"
    QUOTE_EXPIRED = "quote.expired"

    # Placement events
    PLACEMENT_CREATED = "placement.created"
    PLACEMENT_LINE_ADDED = "placement.line_added"
    PLACEMENT_BOUND = "placement.bound"

    # Compliance events
    COMPLIANCE_ALERT = "compliance.alert"
    COMPLIANCE_SUBMITTED = "compliance.submitted"

    # Exposure events
    EXPOSURE_THRESHOLD_BREACH = "exposure.threshold_breach"
    EXPOSURE_UPDATED = "exposure.updated"
