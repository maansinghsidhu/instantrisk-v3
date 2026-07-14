"""
InstantRisk V3 - Email Integration Background Polling Worker

Polls active email connections at EMAIL_SYNC_INTERVAL_SECONDS without
blocking FastAPI startup. Runs as an asyncio task in the app lifespan.
"""

import asyncio
import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.database import AsyncSessionLocal
from app.models.email_integration import EmailConnection, ConnectionStatus
from app.services import email_integration as svc

logger = logging.getLogger("email_integration_polling")


async def start_email_polling():
    """
    Background task: poll all active email connections every
    EMAIL_SYNC_INTERVAL_SECONDS.

    Runs indefinitely until cancelled. Errors are logged but do not
    stop the polling loop.
    """
    interval = settings.EMAIL_SYNC_INTERVAL_SECONDS
    if interval <= 0:
        interval = 300  # fallback 5 minutes

    logger.info(f"Email polling worker started (interval={interval}s)")

    while True:
        try:
            await _poll_all_connections()
        except asyncio.CancelledError:
            logger.info("Email polling worker cancelled")
            raise
        except Exception as e:
            logger.error(f"Email polling loop error: {e}")

        await asyncio.sleep(interval)


async def _poll_all_connections():
    """Fetch all active connections and sync each one."""
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(EmailConnection).where(
                    EmailConnection.status == ConnectionStatus.ACTIVE
                )
            )
            connections = list(result.scalars().all())

        if not connections:
            return

        logger.debug(f"Email polling: {len(connections)} active connections")

        # Poll each connection concurrently
        tasks = [
            _sync_one(connection.id, connection.user_id)
            for connection in connections
        ]
        await asyncio.gather(*tasks, return_exceptions=True)

    except Exception as e:
        logger.error(f"Error in email polling cycle: {e}")


async def _sync_one(connection_id, user_id):
    """Sync one connection, handling errors gracefully."""
    try:
        async with AsyncSessionLocal() as db:
            result = await svc.sync_connection(db, connection_id, user_id)
            if "error" in result:
                logger.warning(
                    f"Sync skipped for connection {connection_id}: {result['error']}"
                )
            else:
                logger.debug(
                    f"Sync completed for {connection_id}: "
                    f"{result.get('messages_fetched', 0)} fetched, "
                    f"{result.get('new_assessments_created', 0)} assessments"
                )
    except Exception as e:
        logger.error(f"Sync error for connection {connection_id}: {e}")
