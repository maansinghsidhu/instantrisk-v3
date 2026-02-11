"""
InstantRisk V3 - Integration Connectors

Framework for integrating with external Lloyd's market systems.
Enables "no rip and replace" strategy - syndicates use InstantRisk
as an enhancement layer alongside existing systems.

Supported connector types:
- REST API: Generic REST endpoint integration
- Webhook: Outbound event notifications
- PPL: Lloyd's Placing Platform Limited
- ECOT: Electronic Claims Office
- Crystal: Market reporting
- SFTP: File-based integrations
"""

from app.services.connectors.base_connector import (
    BaseConnector,
    ConnectorConfig,
    ConnectorStatus,
    ConnectorHealth,
    SyncResult,
)
from app.services.connectors.generic_rest_connector import GenericRESTConnector
from app.services.connectors.webhook_connector import WebhookConnector

__all__ = [
    "BaseConnector",
    "ConnectorConfig",
    "ConnectorStatus",
    "ConnectorHealth",
    "SyncResult",
    "GenericRESTConnector",
    "WebhookConnector",
]
