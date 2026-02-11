"""
InstantRisk V3 - Base Connector Interface

Abstract base class for all external system connectors.
Provides common functionality for authentication, error handling,
retry logic, and health monitoring.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import asyncio
import logging

logger = logging.getLogger(__name__)


class ConnectorStatus(Enum):
    """Connector connection status."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


class ConnectorHealth(Enum):
    """Connector health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ConnectorConfig:
    """Configuration for a connector."""
    connector_type: str
    name: str
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    timeout: int = 30
    retry_attempts: int = 3
    retry_delay: float = 1.0
    headers: Dict[str, str] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConnectorConfig":
        """Create config from dictionary."""
        return cls(
            connector_type=data.get("connector_type", "unknown"),
            name=data.get("name", "unnamed"),
            base_url=data.get("base_url"),
            api_key=data.get("api_key"),
            username=data.get("username"),
            password=data.get("password"),
            timeout=data.get("timeout", 30),
            retry_attempts=data.get("retry_attempts", 3),
            retry_delay=data.get("retry_delay", 1.0),
            headers=data.get("headers", {}),
            extra=data.get("extra", {}),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (exclude sensitive data)."""
        return {
            "connector_type": self.connector_type,
            "name": self.name,
            "base_url": self.base_url,
            "timeout": self.timeout,
            "retry_attempts": self.retry_attempts,
            # Note: Excluding api_key, username, password for security
        }


@dataclass
class SyncResult:
    """Result of a sync operation."""
    success: bool
    records_processed: int = 0
    records_created: int = 0
    records_updated: int = 0
    records_failed: int = 0
    errors: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    data: Optional[Dict[str, Any]] = None


class BaseConnector(ABC):
    """
    Abstract base class for external system connectors.

    Provides common functionality:
    - Connection management
    - Authentication
    - Retry logic with exponential backoff
    - Health monitoring
    - Error handling and logging
    """

    def __init__(self, config: ConnectorConfig):
        """
        Initialize connector with configuration.

        Args:
            config: Connector configuration.
        """
        self.config = config
        self.status = ConnectorStatus.DISCONNECTED
        self.health = ConnectorHealth.UNKNOWN
        self.last_error: Optional[str] = None
        self.last_connected_at: Optional[datetime] = None
        self.last_sync_at: Optional[datetime] = None
        self._connection: Optional[Any] = None

    @property
    def connector_type(self) -> str:
        """Get connector type identifier."""
        return self.config.connector_type

    @property
    def name(self) -> str:
        """Get connector name."""
        return self.config.name

    # ==========================================================================
    # Abstract methods - must be implemented by subclasses
    # ==========================================================================

    @abstractmethod
    async def _connect(self) -> bool:
        """
        Establish connection to external system.

        Returns:
            True if connection successful.
        """
        pass

    @abstractmethod
    async def _disconnect(self) -> bool:
        """
        Close connection to external system.

        Returns:
            True if disconnection successful.
        """
        pass

    @abstractmethod
    async def _push(self, data: Dict[str, Any], endpoint: str) -> Dict[str, Any]:
        """
        Push data to external system.

        Args:
            data: Data to push.
            endpoint: Target endpoint/resource.

        Returns:
            Response from external system.
        """
        pass

    @abstractmethod
    async def _pull(self, query: Dict[str, Any]) -> Dict[str, Any]:
        """
        Pull data from external system.

        Args:
            query: Query parameters.

        Returns:
            Data from external system.
        """
        pass

    @abstractmethod
    async def _healthcheck(self) -> bool:
        """
        Check health of external system connection.

        Returns:
            True if healthy.
        """
        pass

    # ==========================================================================
    # Public methods with retry and error handling
    # ==========================================================================

    async def connect(self) -> bool:
        """
        Connect to external system with retry logic.

        Returns:
            True if connected successfully.
        """
        self.status = ConnectorStatus.CONNECTING
        self.last_error = None

        for attempt in range(self.config.retry_attempts):
            try:
                if await self._connect():
                    self.status = ConnectorStatus.CONNECTED
                    self.health = ConnectorHealth.HEALTHY
                    self.last_connected_at = datetime.now(timezone.utc)
                    logger.info(f"Connector {self.name} connected successfully")
                    return True
            except Exception as e:
                self.last_error = str(e)
                logger.warning(
                    f"Connector {self.name} connection attempt {attempt + 1} failed: {e}"
                )
                if attempt < self.config.retry_attempts - 1:
                    await asyncio.sleep(
                        self.config.retry_delay * (2 ** attempt)  # Exponential backoff
                    )

        self.status = ConnectorStatus.ERROR
        self.health = ConnectorHealth.UNHEALTHY
        logger.error(f"Connector {self.name} failed to connect after {self.config.retry_attempts} attempts")
        return False

    async def disconnect(self) -> bool:
        """
        Disconnect from external system.

        Returns:
            True if disconnected successfully.
        """
        try:
            result = await self._disconnect()
            self.status = ConnectorStatus.DISCONNECTED
            self._connection = None
            logger.info(f"Connector {self.name} disconnected")
            return result
        except Exception as e:
            self.last_error = str(e)
            logger.error(f"Connector {self.name} disconnect error: {e}")
            return False

    async def push(self, data: Dict[str, Any], endpoint: str) -> Dict[str, Any]:
        """
        Push data to external system with retry logic.

        Args:
            data: Data to push.
            endpoint: Target endpoint.

        Returns:
            Response from external system.

        Raises:
            ConnectionError: If not connected.
            Exception: If push fails after retries.
        """
        if self.status != ConnectorStatus.CONNECTED:
            if not await self.connect():
                raise ConnectionError(f"Connector {self.name} not connected")

        for attempt in range(self.config.retry_attempts):
            try:
                result = await self._push(data, endpoint)
                self.last_sync_at = datetime.now(timezone.utc)
                return result
            except Exception as e:
                self.last_error = str(e)
                logger.warning(f"Connector {self.name} push attempt {attempt + 1} failed: {e}")
                if attempt < self.config.retry_attempts - 1:
                    await asyncio.sleep(self.config.retry_delay * (2 ** attempt))
                else:
                    self.health = ConnectorHealth.DEGRADED
                    raise

    async def pull(self, query: Dict[str, Any]) -> Dict[str, Any]:
        """
        Pull data from external system with retry logic.

        Args:
            query: Query parameters.

        Returns:
            Data from external system.

        Raises:
            ConnectionError: If not connected.
            Exception: If pull fails after retries.
        """
        if self.status != ConnectorStatus.CONNECTED:
            if not await self.connect():
                raise ConnectionError(f"Connector {self.name} not connected")

        for attempt in range(self.config.retry_attempts):
            try:
                result = await self._pull(query)
                self.last_sync_at = datetime.now(timezone.utc)
                return result
            except Exception as e:
                self.last_error = str(e)
                logger.warning(f"Connector {self.name} pull attempt {attempt + 1} failed: {e}")
                if attempt < self.config.retry_attempts - 1:
                    await asyncio.sleep(self.config.retry_delay * (2 ** attempt))
                else:
                    self.health = ConnectorHealth.DEGRADED
                    raise

    async def sync(self, direction: str = "bidirectional", **kwargs) -> SyncResult:
        """
        Synchronize data with external system.

        Args:
            direction: "push", "pull", or "bidirectional".
            **kwargs: Additional sync parameters.

        Returns:
            SyncResult with statistics.
        """
        start_time = datetime.now(timezone.utc)
        result = SyncResult(success=True)

        try:
            if direction in ("pull", "bidirectional"):
                pull_data = await self.pull(kwargs.get("pull_query", {}))
                result.records_processed += pull_data.get("count", 0)
                result.data = pull_data

            if direction in ("push", "bidirectional"):
                push_data = kwargs.get("push_data", {})
                if push_data:
                    await self.push(push_data, kwargs.get("endpoint", "/"))
                    result.records_processed += 1

            self.last_sync_at = datetime.now(timezone.utc)

        except Exception as e:
            result.success = False
            result.errors.append(str(e))
            self.last_error = str(e)
            logger.error(f"Connector {self.name} sync error: {e}")

        result.duration_seconds = (datetime.now(timezone.utc) - start_time).total_seconds()
        return result

    async def healthcheck(self) -> ConnectorHealth:
        """
        Check connector health.

        Returns:
            ConnectorHealth status.
        """
        try:
            if await self._healthcheck():
                self.health = ConnectorHealth.HEALTHY
                self.last_error = None
            else:
                self.health = ConnectorHealth.DEGRADED
        except Exception as e:
            self.health = ConnectorHealth.UNHEALTHY
            self.last_error = str(e)
            logger.error(f"Connector {self.name} healthcheck failed: {e}")

        return self.health

    def get_status(self) -> Dict[str, Any]:
        """
        Get current connector status.

        Returns:
            Status dictionary.
        """
        return {
            "connector_type": self.connector_type,
            "name": self.name,
            "status": self.status.value,
            "health": self.health.value,
            "last_error": self.last_error,
            "last_connected_at": self.last_connected_at.isoformat() if self.last_connected_at else None,
            "last_sync_at": self.last_sync_at.isoformat() if self.last_sync_at else None,
        }
