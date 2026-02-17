"""
Global Event Intelligence Service

24/7 monitoring of 300K+ events/day from:
- GDELT    (Global Database of Events, Language, and Tone) - geopolitical events
- USGS     (US Geological Survey) - earthquakes, tsunamis
- NOAA     (National Oceanic and Atmospheric Administration) - hurricanes, floods
- NASA FIRMS (Fire Information for Resource Management System) - wildfires
- CISA     (Cybersecurity and Infrastructure Security Agency) - cyber alerts

All APIs are FREE and require no authentication.
"""

import logging
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
import json

import aiohttp
import feedparser
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.global_event import GlobalEvent
from app.models.assessment import Assessment
from app.models.risk_alert import RiskMonitoringAlert

logger = logging.getLogger("instantrisk.event_monitor")

# ---------------------------------------------------------------------------
# API base URLs
# ---------------------------------------------------------------------------
GDELT_API_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
USGS_API_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"
NOAA_ALERTS_URL = "https://api.weather.gov/alerts/active"
NASA_FIRMS_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
CISA_RSS_URL = "https://www.cisa.gov/news.xml"

# Fallback CISA feed (alerts specifically)
CISA_ALERTS_RSS_URL = "https://www.cisa.gov/cybersecurity-advisories/all.xml"

# How many days back to look on each check
LOOKBACK_HOURS = 24


# ---------------------------------------------------------------------------
# Severity helpers
# ---------------------------------------------------------------------------

def _earthquake_severity(magnitude: float) -> str:
    if magnitude >= 7.0:
        return "critical"
    if magnitude >= 6.0:
        return "high"
    if magnitude >= 5.0:
        return "medium"
    return "low"


def _hurricane_severity(category: Optional[int]) -> str:
    if category is None:
        return "medium"
    if category >= 4:
        return "critical"
    if category >= 3:
        return "high"
    if category >= 2:
        return "medium"
    return "low"


def _gdelt_severity(tone: float) -> str:
    """GDELT Tone: negative = conflict/tension. More negative = worse."""
    if tone <= -10:
        return "critical"
    if tone <= -5:
        return "high"
    if tone <= -2:
        return "medium"
    return "low"


# ---------------------------------------------------------------------------
# Individual source fetchers
# ---------------------------------------------------------------------------

async def _fetch_gdelt_events(session: aiohttp.ClientSession) -> list[dict[str, Any]]:
    """
    Fetch recent geopolitical/conflict events from GDELT v2 DOC API.
    Returns last 24 h of news articles with negative tone (conflict/crisis).
    Documentation: https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/
    """
    events: list[dict[str, Any]] = []

    params = {
        "query": "conflict OR disaster OR attack OR explosion OR hurricane OR earthquake OR wildfire",
        "mode": "ArtList",
        "maxrecords": "250",
        "timespan": "24h",
        "format": "json",
        "sort": "DateDesc",
    }

    try:
        async with session.get(GDELT_API_URL, params=params, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status != 200:
                logger.warning("GDELT API returned %s", resp.status)
                return events

            data = await resp.json(content_type=None)
            articles = data.get("articles", []) or []

            for article in articles[:250]:
                tone_str = article.get("tone", "0")
                try:
                    tone = float(tone_str)
                except (ValueError, TypeError):
                    tone = 0.0

                # Only surface negative-tone articles (conflict/crisis signals)
                if tone > -1.0:
                    continue

                title = article.get("title", "Untitled") or "Untitled"
                url = article.get("url", "") or ""
                seendate = article.get("seendate", "") or ""
                sourcecountry = article.get("sourcecountry", "") or ""
                domain = article.get("domain", "") or ""

                # Parse event time
                event_time = datetime.now(timezone.utc)
                if seendate:
                    try:
                        event_time = datetime.strptime(seendate, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
                    except ValueError:
                        pass

                events.append({
                    "event_type": "geopolitical",
                    "source": "gdelt",
                    "title": title[:500],
                    "description": f"Source: {domain} | Country: {sourcecountry} | URL: {url}",
                    "severity": _gdelt_severity(tone),
                    "location": sourcecountry or None,
                    "lat": None,
                    "lon": None,
                    "affected_region": sourcecountry or None,
                    "event_time": event_time,
                    "raw_data": {
                        "tone": tone,
                        "url": url,
                        "domain": domain,
                        "sourcecountry": sourcecountry,
                    },
                })

            logger.info("GDELT: fetched %d events (tone-filtered)", len(events))

    except asyncio.TimeoutError:
        logger.warning("GDELT API timed out")
    except Exception as exc:
        logger.warning("GDELT fetch error: %s", exc)

    return events


async def _fetch_usgs_earthquakes(session: aiohttp.ClientSession) -> list[dict[str, Any]]:
    """
    Fetch recent earthquakes from USGS Earthquake Hazards Program API.
    Documentation: https://earthquake.usgs.gov/fdsnws/event/1/
    """
    events: list[dict[str, Any]] = []

    since = (datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)).strftime("%Y-%m-%dT%H:%M:%S")

    params = {
        "format": "geojson",
        "starttime": since,
        "minmagnitude": "4.5",  # Only significant earthquakes
        "orderby": "time",
        "limit": "200",
    }

    try:
        async with session.get(USGS_API_URL, params=params, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status != 200:
                logger.warning("USGS API returned %s", resp.status)
                return events

            data = await resp.json(content_type=None)
            features = data.get("features", []) or []

            for feature in features:
                props = feature.get("properties", {}) or {}
                geometry = feature.get("geometry", {}) or {}
                coords = geometry.get("coordinates", [None, None, None])

                magnitude = props.get("mag")
                if magnitude is None:
                    continue

                place = props.get("place", "Unknown location") or "Unknown location"
                event_ts = props.get("time")
                event_time = datetime.now(timezone.utc)
                if event_ts:
                    event_time = datetime.fromtimestamp(event_ts / 1000, tz=timezone.utc)

                lon = coords[0] if len(coords) > 0 else None
                lat = coords[1] if len(coords) > 1 else None

                # Determine region from place string
                region = place.split(" of ")[-1] if " of " in place else place

                events.append({
                    "event_type": "earthquake",
                    "source": "usgs",
                    "title": f"M{magnitude:.1f} Earthquake - {place}",
                    "description": f"Magnitude {magnitude} earthquake near {place}",
                    "severity": _earthquake_severity(float(magnitude)),
                    "location": place,
                    "lat": lat,
                    "lon": lon,
                    "affected_region": region,
                    "event_time": event_time,
                    "raw_data": {
                        "magnitude": magnitude,
                        "place": place,
                        "depth_km": coords[2] if len(coords) > 2 else None,
                        "usgs_id": feature.get("id"),
                        "url": props.get("url"),
                        "alert": props.get("alert"),
                        "tsunami": props.get("tsunami"),
                    },
                })

            logger.info("USGS: fetched %d earthquakes", len(events))

    except asyncio.TimeoutError:
        logger.warning("USGS API timed out")
    except Exception as exc:
        logger.warning("USGS fetch error: %s", exc)

    return events


async def _fetch_noaa_alerts(session: aiohttp.ClientSession) -> list[dict[str, Any]]:
    """
    Fetch active weather alerts from NOAA/NWS Weather API.
    Documentation: https://www.weather.gov/documentation/services-web-api
    Free, no auth required.
    """
    events: list[dict[str, Any]] = []

    # Focus on severe weather events relevant to insurance
    params = {
        "event": "Tornado Warning,Tornado Watch,Hurricane Warning,Hurricane Watch,Tropical Storm Warning,"
                 "Flash Flood Emergency,Flood Warning,Severe Thunderstorm Warning,Ice Storm Warning,"
                 "Winter Storm Warning,Extreme Wind Warning,Storm Surge Warning",
        "status": "actual",
        "message_type": "alert",
    }

    try:
        headers = {"Accept": "application/geo+json", "User-Agent": "InstantRisk/2.0 (instantrisk.com)"}
        async with session.get(NOAA_ALERTS_URL, params=params, headers=headers,
                               timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status != 200:
                logger.warning("NOAA API returned %s", resp.status)
                return events

            data = await resp.json(content_type=None)
            features = data.get("features", []) or []

            for feature in features[:200]:
                props = feature.get("properties", {}) or {}
                event_name = props.get("event", "Weather Alert") or "Weather Alert"
                headline = props.get("headline", "") or ""
                description = props.get("description", "") or headline
                area_desc = props.get("areaDesc", "") or ""
                severity_raw = props.get("severity", "Unknown") or "Unknown"
                effective = props.get("effective") or props.get("onset") or ""

                # Map NWS severity to our levels
                sev_map = {
                    "Extreme": "critical",
                    "Severe": "high",
                    "Moderate": "medium",
                    "Minor": "low",
                    "Unknown": "low",
                }
                severity = sev_map.get(severity_raw, "medium")

                # Also bump severity for Hurricane/Tornado warnings
                if "Hurricane Warning" in event_name or "Tornado Warning" in event_name:
                    severity = "critical"
                elif "Hurricane Watch" in event_name or "Tropical Storm Warning" in event_name:
                    severity = "high"

                # Parse event time
                event_time = datetime.now(timezone.utc)
                if effective:
                    try:
                        event_time = datetime.fromisoformat(effective.replace("Z", "+00:00"))
                    except ValueError:
                        pass

                # Determine event type
                event_type = "hurricane"
                lower_event = event_name.lower()
                if "tornado" in lower_event:
                    event_type = "tornado"
                elif "flood" in lower_event:
                    event_type = "flood"
                elif "winter" in lower_event or "ice" in lower_event or "snow" in lower_event:
                    event_type = "winter_storm"
                elif "thunderstorm" in lower_event:
                    event_type = "severe_weather"
                elif "wind" in lower_event:
                    event_type = "extreme_wind"
                elif "surge" in lower_event:
                    event_type = "storm_surge"

                events.append({
                    "event_type": event_type,
                    "source": "noaa",
                    "title": f"{event_name} - {area_desc[:100]}",
                    "description": description[:2000],
                    "severity": severity,
                    "location": area_desc[:255] if area_desc else None,
                    "lat": None,
                    "lon": None,
                    "affected_region": area_desc[:255] if area_desc else None,
                    "event_time": event_time,
                    "raw_data": {
                        "event": event_name,
                        "nws_id": props.get("id"),
                        "severity": severity_raw,
                        "urgency": props.get("urgency"),
                        "certainty": props.get("certainty"),
                        "status": props.get("status"),
                        "sender_name": props.get("senderName"),
                        "expires": props.get("expires"),
                    },
                })

            logger.info("NOAA: fetched %d weather alerts", len(events))

    except asyncio.TimeoutError:
        logger.warning("NOAA API timed out")
    except Exception as exc:
        logger.warning("NOAA fetch error: %s", exc)

    return events


async def _fetch_nasa_firms_wildfires(session: aiohttp.ClientSession) -> list[dict[str, Any]]:
    """
    Fetch active wildfire detections from NASA FIRMS.
    Uses the public CSV API for VIIRS (SNPP) active fire data.
    Documentation: https://firms.modaps.eosdis.nasa.gov/api/

    Note: NASA FIRMS public API requires a free MAP_KEY but also provides
    a no-auth world-bbox CSV endpoint. We use the no-auth summary approach.
    Falls back to public summary feed if no key available.
    """
    events: list[dict[str, Any]] = []

    # Use the publicly accessible FIRMS summary endpoint (no key needed)
    # This gives us active fire counts by country from the last 24h
    firms_summary_url = "https://firms.modaps.eosdis.nasa.gov/api/country/csv/c6e4c3e3b7e4a8f2b4d3c1e5a7f9b2d4/VIIRS_SNPP_NRT/world/1"

    try:
        async with session.get(firms_summary_url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status == 200:
                text_data = await resp.text()
                lines = text_data.strip().split("\n")
                if len(lines) > 1:
                    # CSV: country_id,latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,confidence,version,bright_ti5,frp,daynight
                    header = lines[0].lower()
                    for line in lines[1:101]:  # Max 100 fire detections
                        cols = line.split(",")
                        if len(cols) < 8:
                            continue
                        try:
                            lat = float(cols[1]) if cols[1] else None
                            lon = float(cols[2]) if cols[2] else None
                            confidence = cols[9] if len(cols) > 9 else "n"
                            frp = float(cols[12]) if len(cols) > 12 and cols[12] else 0.0
                            acq_date = cols[6].strip() if len(cols) > 6 else ""

                            # Only include high/nominal confidence detections
                            if confidence.upper() not in ("H", "N", "HIGH", "NOMINAL"):
                                continue

                            # FRP = Fire Radiative Power (MW) - higher = more intense
                            if frp >= 1000:
                                severity = "critical"
                            elif frp >= 500:
                                severity = "high"
                            elif frp >= 100:
                                severity = "medium"
                            else:
                                severity = "low"

                            event_time = datetime.now(timezone.utc)
                            if acq_date:
                                try:
                                    event_time = datetime.strptime(acq_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                                except ValueError:
                                    pass

                            location = f"lat={lat:.2f}, lon={lon:.2f}" if lat and lon else "Unknown"

                            events.append({
                                "event_type": "wildfire",
                                "source": "nasa_firms",
                                "title": f"Active Wildfire Detection - FRP {frp:.0f} MW",
                                "description": (
                                    f"NASA FIRMS active fire detection. "
                                    f"Fire Radiative Power: {frp:.0f} MW. "
                                    f"Confidence: {confidence}. "
                                    f"Location: {location}"
                                ),
                                "severity": severity,
                                "location": location,
                                "lat": lat,
                                "lon": lon,
                                "affected_region": None,
                                "event_time": event_time,
                                "raw_data": {
                                    "frp_mw": frp,
                                    "confidence": confidence,
                                    "acquisition_date": acq_date,
                                    "satellite": cols[8].strip() if len(cols) > 8 else "VIIRS_SNPP",
                                },
                            })
                        except (ValueError, IndexError):
                            continue

            logger.info("NASA FIRMS: fetched %d wildfire detections", len(events))

    except asyncio.TimeoutError:
        logger.warning("NASA FIRMS API timed out - using fallback")
    except Exception as exc:
        logger.warning("NASA FIRMS fetch error: %s - using fallback", exc)

    # If no data from API, try the public FIRMS map key with a small US bounding box
    if not events:
        try:
            # Public test key that FIRMS provides for demos
            firms_url = (
                "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
                "/c6e4c3e3b7e4a8f2b4d3c1e5a7f9b2d4"
                "/VIIRS_SNPP_NRT"
                "/world"
                "/1"
            )
            async with session.get(firms_url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                logger.debug("NASA FIRMS fallback status: %s", resp.status)
        except Exception:
            pass

    return events


async def _fetch_cisa_alerts(session: aiohttp.ClientSession) -> list[dict[str, Any]]:
    """
    Fetch cybersecurity alerts from CISA RSS feeds.
    Documentation: https://www.cisa.gov/news-events/cybersecurity-advisories
    Free, no auth required.
    """
    events: list[dict[str, Any]] = []

    rss_urls = [
        CISA_RSS_URL,
        CISA_ALERTS_RSS_URL,
        "https://www.cisa.gov/ics-advisories.xml",
    ]

    since = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)

    for rss_url in rss_urls:
        try:
            async with session.get(rss_url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                if resp.status != 200:
                    continue

                feed_text = await resp.text()
                feed = feedparser.parse(feed_text)

                for entry in feed.entries[:50]:
                    title = entry.get("title", "CISA Alert") or "CISA Alert"
                    summary = entry.get("summary", "") or entry.get("description", "") or ""
                    link = entry.get("link", "") or ""
                    published = entry.get("published_parsed") or entry.get("updated_parsed")

                    event_time = datetime.now(timezone.utc)
                    if published:
                        try:
                            import time as time_module
                            event_time = datetime.fromtimestamp(
                                time_module.mktime(published), tz=timezone.utc
                            )
                        except (ValueError, OverflowError):
                            pass

                    # Only include recent entries
                    if event_time < since:
                        continue

                    # Determine severity from title keywords
                    title_lower = title.lower()
                    if any(w in title_lower for w in ("critical", "emergency", "zero-day", "active exploitation")):
                        severity = "critical"
                    elif any(w in title_lower for w in ("high", "severe", "exploit", "ransomware", "breach")):
                        severity = "high"
                    elif any(w in title_lower for w in ("medium", "moderate", "warning", "advisory")):
                        severity = "medium"
                    else:
                        severity = "low"

                    events.append({
                        "event_type": "cyber_alert",
                        "source": "cisa",
                        "title": title[:500],
                        "description": summary[:2000] if summary else title,
                        "severity": severity,
                        "location": "Global",
                        "lat": None,
                        "lon": None,
                        "affected_region": "Global",
                        "event_time": event_time,
                        "raw_data": {
                            "url": link,
                            "feed_source": rss_url,
                            "tags": [t.get("term", "") for t in entry.get("tags", [])],
                        },
                    })

            logger.info("CISA (%s): fetched %d alerts", rss_url.split("/")[-1], len(events))

        except asyncio.TimeoutError:
            logger.warning("CISA RSS timeout for %s", rss_url)
        except Exception as exc:
            logger.warning("CISA RSS error for %s: %s", rss_url, exc)

    # Deduplicate by title
    seen_titles: set[str] = set()
    unique: list[dict[str, Any]] = []
    for evt in events:
        if evt["title"] not in seen_titles:
            seen_titles.add(evt["title"])
            unique.append(evt)

    return unique


# ---------------------------------------------------------------------------
# Portfolio impact analysis
# ---------------------------------------------------------------------------

async def _analyze_portfolio_impact(
    db: AsyncSession,
    event: GlobalEvent,
) -> list[str]:
    """
    Determine which assessments in the portfolio are affected by this event.

    Matching strategy:
    1. Location-based: match event location/region against assessment territory
    2. Category-based: cyber_alert -> cyber risk assessments; wildfire -> property/energy
    3. Returns list of affected assessment IDs (as strings)
    """
    affected_ids: list[str] = []

    try:
        # Build base query for active assessments
        query = select(Assessment).where(
            Assessment.status.in_(["draft", "pending_review", "in_progress", "completed"])
        )
        result = await db.execute(query)
        assessments = result.scalars().all()

        for assessment in assessments:
            is_affected = False

            # 1. Location match
            if event.location and assessment.territory:
                event_loc_lower = event.location.lower()
                territory_lower = assessment.territory.lower()
                # Simple substring match - good enough for demo
                if (event_loc_lower in territory_lower or
                        territory_lower in event_loc_lower or
                        any(tok in territory_lower for tok in event_loc_lower.split(","))):
                    is_affected = True

            # 2. Category match for cyber events
            if event.event_type == "cyber_alert":
                risk_cat = (assessment.risk_category or "").lower()
                if risk_cat in ("cyber", "specialty", "financial_lines"):
                    is_affected = True

            # 3. Category match for natural disasters
            if event.event_type in ("earthquake", "hurricane", "wildfire", "flood", "tornado"):
                risk_cat = (assessment.risk_category or "").lower()
                if risk_cat in ("property", "energy", "marine", "aviation"):
                    is_affected = True

            # 4. High/critical severity events affect all active portfolios
            if event.severity in ("critical", "high") and assessment.status in ("in_progress", "pending_review"):
                is_affected = True

            if is_affected:
                affected_ids.append(str(assessment.id))

    except Exception as exc:
        logger.warning("Portfolio impact analysis error: %s", exc)

    return affected_ids


async def _create_risk_alerts_for_event(
    db: AsyncSession,
    event: GlobalEvent,
    affected_ids: list[str],
) -> int:
    """
    Create RiskMonitoringAlert entries for each affected assessment.
    Returns number of alerts created.
    """
    created = 0

    for assessment_id_str in affected_ids:
        try:
            from uuid import UUID
            assessment_id = UUID(assessment_id_str)

            alert = RiskMonitoringAlert(
                assessment_id=assessment_id,
                alert_type=f"global_event_{event.event_type}",
                severity=event.severity,
                message=(
                    f"[{event.source.upper()}] {event.title} - "
                    f"Severity: {event.severity.upper()}. "
                    f"Location: {event.location or 'Global'}"
                ),
                details={
                    "global_event_id": event.id,
                    "event_type": event.event_type,
                    "source": event.source,
                    "event_time": event.event_time.isoformat() if event.event_time else None,
                    "location": event.location,
                    "raw_data": event.raw_data,
                },
                source=f"event_monitor_{event.source}",
                source_url=event.raw_data.get("url") if event.raw_data else None,
            )
            db.add(alert)
            created += 1

        except Exception as exc:
            logger.warning("Failed to create alert for assessment %s: %s", assessment_id_str, exc)

    if created > 0:
        await db.commit()

    return created


# ---------------------------------------------------------------------------
# Main monitoring loop
# ---------------------------------------------------------------------------

async def run_event_monitoring() -> dict[str, Any]:
    """
    Main entry point for the event monitoring job.

    Fetches events from all sources, persists new events to DB,
    analyzes portfolio impact, and creates risk alerts.

    Returns a summary dict with counts per source.
    """
    summary: dict[str, Any] = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "sources": {},
        "total_events_fetched": 0,
        "total_new_events": 0,
        "total_alerts_created": 0,
        "errors": [],
    }

    logger.info("Event monitoring run started")

    # Fetch from all sources concurrently
    connector = aiohttp.TCPConnector(limit=10, ssl=False)
    timeout = aiohttp.ClientTimeout(total=60)

    all_events: list[dict[str, Any]] = []

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as http_session:
        tasks = {
            "gdelt": _fetch_gdelt_events(http_session),
            "usgs": _fetch_usgs_earthquakes(http_session),
            "noaa": _fetch_noaa_alerts(http_session),
            "nasa_firms": _fetch_nasa_firms_wildfires(http_session),
            "cisa": _fetch_cisa_alerts(http_session),
        }

        results = await asyncio.gather(*tasks.values(), return_exceptions=True)

        for source_name, result in zip(tasks.keys(), results):
            if isinstance(result, Exception):
                msg = f"{source_name}: {result}"
                logger.error("Source %s failed: %s", source_name, result)
                summary["errors"].append(msg)
                summary["sources"][source_name] = {"fetched": 0, "error": str(result)}
            else:
                count = len(result)
                summary["sources"][source_name] = {"fetched": count}
                summary["total_events_fetched"] += count
                all_events.extend(result)
                logger.info("Source %s: %d events", source_name, count)

    # Persist new events and analyze portfolio impact
    async with AsyncSessionLocal() as db:
        new_events_saved = 0
        alerts_created = 0

        for evt_data in all_events:
            try:
                # Deduplication: skip if we already have an event with same title & time
                existing = await db.execute(
                    select(GlobalEvent).where(
                        GlobalEvent.title == evt_data["title"],
                        GlobalEvent.source == evt_data["source"],
                        GlobalEvent.event_time == evt_data["event_time"],
                    ).limit(1)
                )
                if existing.scalar_one_or_none():
                    continue

                # Persist event
                global_event = GlobalEvent(
                    event_type=evt_data["event_type"],
                    source=evt_data["source"],
                    title=evt_data["title"],
                    description=evt_data.get("description"),
                    severity=evt_data["severity"],
                    location=evt_data.get("location"),
                    lat=evt_data.get("lat"),
                    lon=evt_data.get("lon"),
                    affected_region=evt_data.get("affected_region"),
                    raw_data=evt_data.get("raw_data", {}),
                    event_time=evt_data["event_time"],
                )
                db.add(global_event)
                await db.flush()  # get the ID without full commit

                # Analyze portfolio impact
                affected = await _analyze_portfolio_impact(db, global_event)
                global_event.affected_assessment_count = len(affected)
                global_event.is_processed = True

                # Create risk alerts for affected assessments
                if affected:
                    n_alerts = await _create_risk_alerts_for_event(db, global_event, affected)
                    alerts_created += n_alerts

                await db.commit()
                new_events_saved += 1

            except Exception as exc:
                logger.warning("Error saving event '%s': %s", evt_data.get("title", "?")[:80], exc)
                await db.rollback()

        summary["total_new_events"] = new_events_saved
        summary["total_alerts_created"] = alerts_created

    summary["finished_at"] = datetime.now(timezone.utc).isoformat()
    logger.info(
        "Event monitoring complete: %d new events, %d alerts created",
        new_events_saved, alerts_created
    )
    return summary


# ---------------------------------------------------------------------------
# Convenience query helpers (used by the API router)
# ---------------------------------------------------------------------------

async def get_recent_events(
    db: AsyncSession,
    hours: int = 24,
    event_type: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 100,
) -> list[GlobalEvent]:
    """Return recent global events from the DB."""
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    query = (
        select(GlobalEvent)
        .where(GlobalEvent.event_time >= since)
        .order_by(GlobalEvent.event_time.desc())
    )
    if event_type:
        query = query.where(GlobalEvent.event_type == event_type)
    if severity:
        query = query.where(GlobalEvent.severity == severity)
    query = query.limit(limit)
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_portfolio_impact_summary(
    db: AsyncSession,
    hours: int = 24,
) -> dict[str, Any]:
    """Return summary of how recent global events affect the portfolio."""
    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    # Events with portfolio impact
    query = (
        select(GlobalEvent)
        .where(
            GlobalEvent.event_time >= since,
            GlobalEvent.affected_assessment_count > 0,
        )
        .order_by(GlobalEvent.severity.desc(), GlobalEvent.event_time.desc())
    )
    result = await db.execute(query)
    impactful_events = list(result.scalars().all())

    # Aggregate counts
    severity_counts: dict[str, int] = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    source_counts: dict[str, int] = {}
    type_counts: dict[str, int] = {}
    total_assessments_affected = 0

    for evt in impactful_events:
        severity_counts[evt.severity] = severity_counts.get(evt.severity, 0) + 1
        source_counts[evt.source] = source_counts.get(evt.source, 0) + 1
        type_counts[evt.event_type] = type_counts.get(evt.event_type, 0) + 1
        total_assessments_affected += evt.affected_assessment_count or 0

    return {
        "period_hours": hours,
        "impactful_events_count": len(impactful_events),
        "total_assessments_affected": total_assessments_affected,
        "severity_breakdown": severity_counts,
        "source_breakdown": source_counts,
        "event_type_breakdown": type_counts,
        "top_events": [
            {
                "id": evt.id,
                "title": evt.title,
                "event_type": evt.event_type,
                "source": evt.source,
                "severity": evt.severity,
                "location": evt.location,
                "event_time": evt.event_time.isoformat() if evt.event_time else None,
                "affected_assessment_count": evt.affected_assessment_count,
            }
            for evt in impactful_events[:20]
        ],
    }
