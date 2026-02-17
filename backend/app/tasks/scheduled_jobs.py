"""
Scheduled Background Jobs

Uses APScheduler to run recurring tasks on a fixed schedule.
Jobs are started during FastAPI lifespan startup and stopped on shutdown.

Current jobs:
- event_monitoring_job: runs every hour, fetches global events from
  GDELT, USGS, NOAA, NASA FIRMS, CISA and analyzes portfolio impact.
"""

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger("instantrisk.scheduler")

# Module-level scheduler instance (singleton)
scheduler = AsyncIOScheduler(timezone="UTC")

# Track last run results for status endpoint
_job_status: dict[str, dict] = {}


# ---------------------------------------------------------------------------
# Job functions
# ---------------------------------------------------------------------------

async def event_monitoring_job() -> None:
    """
    Hourly job: fetch global events and analyze portfolio impact.

    Runs every 60 minutes. On startup it fires immediately (next_run_time=now)
    to ensure fresh data is available as soon as the service starts.
    """
    job_name = "event_monitoring"
    started_at = datetime.now(timezone.utc)
    logger.info("[scheduler] event_monitoring_job started at %s", started_at.isoformat())

    try:
        from app.services.event_monitor import run_event_monitoring
        result = await run_event_monitoring()

        _job_status[job_name] = {
            "last_run": started_at.isoformat(),
            "status": "success",
            "summary": result,
        }

        logger.info(
            "[scheduler] event_monitoring_job completed: %d new events, %d alerts",
            result.get("total_new_events", 0),
            result.get("total_alerts_created", 0),
        )

    except Exception as exc:
        logger.error("[scheduler] event_monitoring_job failed: %s", exc, exc_info=True)
        _job_status[job_name] = {
            "last_run": started_at.isoformat(),
            "status": "error",
            "error": str(exc),
        }


# ---------------------------------------------------------------------------
# Scheduler lifecycle
# ---------------------------------------------------------------------------

def start_scheduler() -> None:
    """
    Register all jobs and start the APScheduler.

    Called from FastAPI lifespan startup.
    """
    if scheduler.running:
        logger.warning("[scheduler] Already running - skipping start")
        return

    # Event monitoring: every 60 minutes
    # misfire_grace_time=300 means if the job misses its window by up to 5 min
    # it will still run (handles brief server overload).
    scheduler.add_job(
        event_monitoring_job,
        trigger=IntervalTrigger(hours=1),
        id="event_monitoring",
        name="Global Event Intelligence Monitor",
        replace_existing=True,
        misfire_grace_time=300,
        max_instances=1,  # Prevent overlap if previous run takes > 1h
        # Run immediately on startup, then every hour
        next_run_time=datetime.now(timezone.utc),
    )

    scheduler.start()
    logger.info("[scheduler] APScheduler started with %d jobs", len(scheduler.get_jobs()))
    for job in scheduler.get_jobs():
        logger.info("[scheduler]   - %s (next run: %s)", job.name, job.next_run_time)


def stop_scheduler() -> None:
    """
    Gracefully shut down the scheduler.

    Called from FastAPI lifespan shutdown.
    """
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("[scheduler] APScheduler stopped")


def get_job_status(job_id: str = None) -> dict:
    """Return last known status for a job, or all jobs."""
    if job_id:
        return _job_status.get(job_id, {"status": "never_run"})
    return _job_status.copy()


def get_scheduler_info() -> dict:
    """Return scheduler state and registered job list."""
    jobs = []
    if scheduler.running:
        for job in scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger),
            })

    return {
        "running": scheduler.running,
        "jobs": jobs,
        "job_statuses": get_job_status(),
    }
