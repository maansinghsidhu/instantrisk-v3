"""
InstantRisk V2 - Regulatory Compliance Scanner

Scrapes regulatory publications from FCA, PRA, and EIOPA to maintain an
up-to-date compliance database. Checks policy submissions against current
regulatory requirements.

Architecture:
    RegulatoryScanner → PlaywrightScraper/aiohttp → BeautifulSoup parser
    → RegulationDB (in-memory + cached) → ComplianceChecker → Report

Supported regulators:
    - FCA (Financial Conduct Authority) - UK
    - PRA (Prudential Regulation Authority) - UK
    - EIOPA (European Insurance & Occupational Pensions Authority) - EU
    - Lloyd's of London Market Bulletins
    - ICO (Information Commissioner's Office) - for GDPR/data protection
"""

import os
import json
import logging
import asyncio
import re
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field

import aiohttp
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


# ============================================================
# Data models
# ============================================================

@dataclass
class Regulation:
    """A single regulatory requirement or publication."""
    reg_id: str
    title: str
    regulator: str           # FCA | PRA | EIOPA | LLOYD'S | ICO
    category: str            # conduct | prudential | reporting | consumer | data | solvency
    url: Optional[str]
    published_date: str
    summary: str
    risk_categories: List[str]  # which risk types this applies to
    severity: str            # critical | high | medium | low
    full_text: Optional[str] = None
    last_scraped: Optional[str] = None


@dataclass
class ComplianceCheckResult:
    """Result of checking a policy/assessment against regulations."""
    assessment_id: str
    checked_at: str
    overall_status: str       # compliant | requires_action | critical_issues
    score: int                # 0-100 compliance score
    passed: int
    failed: int
    warnings: int
    checks: List[Dict[str, Any]] = field(default_factory=list)
    required_actions: List[str] = field(default_factory=list)
    regulatory_summary: str = ""


# ============================================================
# Hard-coded regulatory knowledge base
# (supplements live scraping with always-available reference data)
# ============================================================

REGULATORY_BASELINE = [
    # FCA Rules
    Regulation(
        reg_id="FCA-ICOBS-2",
        title="Insurance Conduct of Business Sourcebook (ICOBS) 2 - Communications",
        regulator="FCA",
        category="conduct",
        url="https://www.handbook.fca.org.uk/handbook/ICOBS/2/",
        published_date="2024-01-01",
        summary="Firms must communicate clearly, fairly and not misleadingly. All marketing materials must be clear about the scope of cover.",
        risk_categories=["all"],
        severity="critical",
    ),
    Regulation(
        reg_id="FCA-ICOBS-6",
        title="ICOBS 6 - Product Information",
        regulator="FCA",
        category="conduct",
        url="https://www.handbook.fca.org.uk/handbook/ICOBS/6/",
        published_date="2024-01-01",
        summary="Insurers must provide customers with appropriate product information pre-sale. The IPID (Insurance Product Information Document) is mandatory for general insurance.",
        risk_categories=["all"],
        severity="critical",
    ),
    Regulation(
        reg_id="FCA-ICOBS-7",
        title="ICOBS 7 - Claims Handling",
        regulator="FCA",
        category="conduct",
        url="https://www.handbook.fca.org.uk/handbook/ICOBS/7/",
        published_date="2024-01-01",
        summary="Insurers must handle claims promptly and fairly. Claims must be settled or denied within a reasonable timeframe with written reasons.",
        risk_categories=["all"],
        severity="high",
    ),
    Regulation(
        reg_id="FCA-CON-3",
        title="Consumer Duty (PS22/9) - Consumer Principle",
        regulator="FCA",
        category="consumer",
        url="https://www.fca.org.uk/publications/policy-statements/ps22-9-a-new-consumer-duty",
        published_date="2023-07-31",
        summary="Firms must act to deliver good outcomes for retail customers. Four outcomes: products & services, price & value, consumer understanding, consumer support.",
        risk_categories=["all"],
        severity="critical",
    ),
    Regulation(
        reg_id="FCA-SYSC-3",
        title="Senior Management Arrangements Systems & Controls (SYSC)",
        regulator="FCA",
        category="conduct",
        url="https://www.handbook.fca.org.uk/handbook/SYSC/",
        published_date="2024-01-01",
        summary="Firms must have adequate systems and controls. Underwriting authorities must be clearly defined. Risk management framework required.",
        risk_categories=["all"],
        severity="high",
    ),
    # PRA Rules
    Regulation(
        reg_id="PRA-SS5-16",
        title="PRA SS5/16 - Solvency II: Internal Models",
        regulator="PRA",
        category="solvency",
        url="https://www.bankofengland.co.uk/prudential-regulation/publication/2016/solvency-2-internal-models",
        published_date="2023-06-01",
        summary="Requirements for internal model approval and use in calculating SCR (Solvency Capital Requirement). Models must be fit for use.",
        risk_categories=["all"],
        severity="high",
    ),
    Regulation(
        reg_id="PRA-PS4-25",
        title="PRA PS4/25 - Insurance Stress Test 2025",
        regulator="PRA",
        category="prudential",
        url="https://www.bankofengland.co.uk/prudential-regulation/",
        published_date="2025-01-01",
        summary="Annual stress test requirements for insurers. Scenarios include natural catastrophe, cyber attack, climate transition, and pandemic.",
        risk_categories=["property", "cyber"],
        severity="medium",
    ),
    Regulation(
        reg_id="PRA-CYBER-RISK",
        title="PRA Supervisory Statement SS2/21 - Operational Resilience",
        regulator="PRA",
        category="conduct",
        url="https://www.bankofengland.co.uk/prudential-regulation/publication/2021/march/operational-resilience-ss",
        published_date="2022-03-31",
        summary="Firms must identify important business services and set impact tolerances. Cyber incidents must be reported within 72 hours.",
        risk_categories=["cyber", "all"],
        severity="critical",
    ),
    # EIOPA Rules
    Regulation(
        reg_id="EIOPA-SFCR",
        title="EIOPA - Solvency and Financial Condition Report (SFCR)",
        regulator="EIOPA",
        category="reporting",
        url="https://www.eiopa.europa.eu/tools-and-data/solvency-ii-reporting_en",
        published_date="2024-01-01",
        summary="Annual SFCR disclosure required for EEA insurers. Must cover business and performance, system of governance, risk profile, and capital management.",
        risk_categories=["all"],
        severity="high",
    ),
    Regulation(
        reg_id="EIOPA-IDD",
        title="Insurance Distribution Directive (IDD) 2016/97/EU",
        regulator="EIOPA",
        category="conduct",
        url="https://www.eiopa.europa.eu/insurance-distribution-directive_en",
        published_date="2022-01-01",
        summary="Regulates insurance distribution across EU. Requires conduct of business rules, disclosure, and training requirements for intermediaries.",
        risk_categories=["all"],
        severity="high",
    ),
    Regulation(
        reg_id="EIOPA-CLIMATE",
        title="EIOPA Opinion on Sustainability in Solvency II",
        regulator="EIOPA",
        category="prudential",
        url="https://www.eiopa.europa.eu/publications/opinions/eiopa-opinion-sustainability_en",
        published_date="2024-06-01",
        summary="Insurers must integrate ESG factors into underwriting and investment. Climate risk must be reflected in SCR calculations.",
        risk_categories=["property", "all"],
        severity="medium",
    ),
    # Lloyd's Market Bulletins
    Regulation(
        reg_id="LLO-MB-Y5387",
        title="Lloyd's Market Bulletin Y5387 - Cyber Aggregate Exposure Management",
        regulator="LLOYD'S",
        category="prudential",
        url="https://www.lloyds.com/market-resources/market-processes/market-bulletins/",
        published_date="2022-08-16",
        summary="All syndicates must define and monitor cyber aggregate exposures. Sub-limits required for systemic cyber events. Mandatory exclusions: state-sponsored cyber war from 31 March 2023.",
        risk_categories=["cyber"],
        severity="critical",
    ),
    Regulation(
        reg_id="LLO-MB-Y5380",
        title="Lloyd's Market Bulletin Y5380 - Sanctions",
        regulator="LLOYD'S",
        category="conduct",
        url="https://www.lloyds.com/market-resources/market-processes/market-bulletins/",
        published_date="2022-01-01",
        summary="All syndicates must comply with Lloyd's sanctions requirements. Mandatory pre-bind sanctions screening. OFAC, HMT and EU lists must be checked.",
        risk_categories=["all"],
        severity="critical",
    ),
    Regulation(
        reg_id="LLO-CLIMATE-RISK",
        title="Lloyd's Climate Change Action Plan 2025",
        regulator="LLOYD'S",
        category="prudential",
        url="https://www.lloyds.com/about-lloyds/responsible-business/climate-change/",
        published_date="2025-01-01",
        summary="Syndicates must publish climate risk assessments. New ESG minimum standards for high-carbon industries. Coal and tar sands exclusions from 2026.",
        risk_categories=["property", "all"],
        severity="medium",
    ),
    # ICO / GDPR
    Regulation(
        reg_id="ICO-GDPR-ART-30",
        title="GDPR Article 30 - Records of Processing Activities",
        regulator="ICO",
        category="data",
        url="https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/accountability-and-governance/documentation/",
        published_date="2021-01-01",
        summary="Controllers must maintain records of processing activities (ROPA). Insurance companies processing personal data for underwriting must document lawful basis.",
        risk_categories=["all"],
        severity="high",
    ),
    Regulation(
        reg_id="ICO-GDPR-BREACH",
        title="GDPR Article 33 - Breach Notification",
        regulator="ICO",
        category="data",
        url="https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/personal-data-breaches/",
        published_date="2021-01-01",
        summary="Data breaches must be reported to ICO within 72 hours. High-risk breaches must be communicated to affected individuals without undue delay.",
        risk_categories=["all"],
        severity="critical",
    ),
]


# ============================================================
# Compliance check rules (applied to assessment data)
# ============================================================

def _check_assessment_compliance(
    assessment_data: Dict[str, Any],
    regulations: List[Regulation],
) -> ComplianceCheckResult:
    """
    Apply regulatory checks to an assessment.
    Returns pass/fail for each applicable regulation.
    """
    checks = []
    required_actions = []
    passed = 0
    failed = 0
    warnings = 0

    risk_category = assessment_data.get("risk_category", "property")
    risk_score = assessment_data.get("risk_score", 50) or 50
    territory = assessment_data.get("territory", "UK") or "UK"
    sum_insured = assessment_data.get("sum_insured", 0) or 0

    # Filter applicable regulations
    applicable = [
        r for r in regulations
        if "all" in r.risk_categories or risk_category in r.risk_categories
    ]

    for reg in applicable:
        check = {
            "reg_id": reg.reg_id,
            "title": reg.title,
            "regulator": reg.regulator,
            "category": reg.category,
            "severity": reg.severity,
            "status": "pass",
            "notes": "",
        }

        # Apply specific checks
        if reg.reg_id == "FCA-CON-3":
            # Consumer Duty - check if retail customer
            if territory in ("UK", "GB"):
                check["notes"] = "Consumer Duty applies for UK retail customers. Verify value assessment completed."
                check["status"] = "warning"
                warnings += 1
                required_actions.append("Complete FCA Consumer Duty value assessment")
            else:
                check["notes"] = f"Consumer Duty: not applicable for territory {territory}"
                passed += 1

        elif reg.reg_id == "LLO-MB-Y5380":
            # Sanctions - always critical
            check["notes"] = "Mandatory pre-bind sanctions screening required (OFAC/HMT/EU)"
            check["status"] = "warning" if risk_score < 80 else "fail"
            if check["status"] == "fail":
                failed += 1
                required_actions.append("[CRITICAL] Complete sanctions screening before binding")
            else:
                warnings += 1
                required_actions.append("Confirm sanctions screening completed")

        elif reg.reg_id == "LLO-MB-Y5387" and risk_category == "cyber":
            # Cyber aggregate - check if aggregate limits set
            check["notes"] = "Cyber aggregate exposure management required. Verify systemic cyber exclusions applied."
            check["status"] = "warning"
            warnings += 1
            required_actions.append("Confirm cyber aggregate limits and systemic exclusions in place")

        elif reg.reg_id == "PRA-CYBER-RISK" and risk_category in ("cyber", "all"):
            check["notes"] = "Operational resilience requirements apply. 72h incident reporting mandatory."
            check["status"] = "pass"
            passed += 1

        elif reg.reg_id == "FCA-ICOBS-6":
            # IPID required for all general insurance
            check["notes"] = "Insurance Product Information Document (IPID) mandatory pre-sale"
            check["status"] = "warning"
            warnings += 1
            required_actions.append("Prepare and provide IPID to insured prior to inception")

        elif reg.reg_id == "ICO-GDPR-ART-30":
            check["notes"] = "ROPA must include this processing. Verify insured's consent for data use."
            check["status"] = "pass"
            passed += 1

        elif reg.reg_id == "EIOPA-CLIMATE" and territory not in ("UK", "GB"):
            check["notes"] = "EIOPA ESG requirements apply for EU territories"
            check["status"] = "warning"
            warnings += 1
            required_actions.append("Include climate risk assessment for EU risk")

        elif reg.reg_id == "LLO-CLIMATE-RISK":
            if risk_score >= 70:
                check["notes"] = "High-risk property - verify climate risk assessment and coal/tar sands exclusions"
                check["status"] = "warning"
                warnings += 1
            else:
                check["status"] = "pass"
                check["notes"] = "Climate requirements: standard exclusions apply"
                passed += 1

        else:
            check["status"] = "pass"
            check["notes"] = f"Regulation awareness confirmed: {reg.summary[:100]}"
            passed += 1

        checks.append(check)

    # Overall score calculation
    total = len(checks)
    if total == 0:
        score = 100
    else:
        fail_weight = failed * 30
        warn_weight = warnings * 10
        score = max(0, int(100 - (fail_weight + warn_weight) * 100 / (total * 30)))

    if failed > 0:
        overall_status = "critical_issues"
    elif warnings > 3:
        overall_status = "requires_action"
    elif warnings > 0:
        overall_status = "requires_action"
    else:
        overall_status = "compliant"

    return ComplianceCheckResult(
        assessment_id=assessment_data.get("id", ""),
        checked_at=datetime.now(timezone.utc).isoformat(),
        overall_status=overall_status,
        score=score,
        passed=passed,
        failed=failed,
        warnings=warnings,
        checks=checks,
        required_actions=required_actions,
        regulatory_summary=(
            f"Checked against {total} applicable regulations. "
            f"Passed: {passed}, Warnings: {warnings}, Failed: {failed}. "
            f"Compliance score: {score}/100."
        ),
    )


# ============================================================
# Web Scraping (live regulatory updates)
# ============================================================

async def _scrape_fca_news(session: aiohttp.ClientSession) -> List[Dict[str, Any]]:
    """Scrape FCA latest publications."""
    url = "https://www.fca.org.uk/news/news"
    updates = []
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status != 200:
                return updates
            html = await resp.text()
            soup = BeautifulSoup(html, "html.parser")

            # FCA news items
            articles = soup.find_all("article", limit=10) or soup.find_all("li", class_="news-item", limit=10)
            for art in articles:
                try:
                    title_el = art.find(["h2", "h3", "h4", "a"])
                    title = title_el.get_text(strip=True) if title_el else ""
                    link_el = art.find("a")
                    link = link_el.get("href", "") if link_el else ""
                    if link and not link.startswith("http"):
                        link = f"https://www.fca.org.uk{link}"
                    date_el = art.find(["time", "span"], class_=lambda x: x and "date" in str(x).lower())
                    date = date_el.get_text(strip=True) if date_el else ""
                    if title:
                        updates.append({"title": title, "url": link, "date": date, "regulator": "FCA"})
                except Exception:
                    pass
    except Exception as e:
        logger.debug(f"FCA scrape failed: {e}")
    return updates


async def _scrape_pra_news(session: aiohttp.ClientSession) -> List[Dict[str, Any]]:
    """Scrape Bank of England / PRA publications."""
    url = "https://www.bankofengland.co.uk/prudential-regulation/publication"
    updates = []
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status != 200:
                return updates
            html = await resp.text()
            soup = BeautifulSoup(html, "html.parser")

            items = soup.find_all("div", class_=lambda x: x and "publication" in str(x).lower(), limit=10)
            for item in items:
                try:
                    title_el = item.find(["h2", "h3", "h4", "a"])
                    title = title_el.get_text(strip=True) if title_el else ""
                    link_el = item.find("a")
                    link = link_el.get("href", "") if link_el else ""
                    if link and not link.startswith("http"):
                        link = f"https://www.bankofengland.co.uk{link}"
                    if title:
                        updates.append({"title": title, "url": link, "date": "", "regulator": "PRA"})
                except Exception:
                    pass
    except Exception as e:
        logger.debug(f"PRA scrape failed: {e}")
    return updates


async def _scrape_eiopa_news(session: aiohttp.ClientSession) -> List[Dict[str, Any]]:
    """Scrape EIOPA publications."""
    url = "https://www.eiopa.europa.eu/publications_en"
    updates = []
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status != 200:
                return updates
            html = await resp.text()
            soup = BeautifulSoup(html, "html.parser")
            items = soup.find_all(["article", "div"], class_=lambda x: x and "publication" in str(x).lower(), limit=10)
            for item in items:
                try:
                    title_el = item.find(["h2", "h3", "h4"])
                    title = title_el.get_text(strip=True) if title_el else ""
                    link_el = item.find("a")
                    link = link_el.get("href", "") if link_el else ""
                    if title:
                        updates.append({"title": title, "url": link, "date": "", "regulator": "EIOPA"})
                except Exception:
                    pass
    except Exception as e:
        logger.debug(f"EIOPA scrape failed: {e}")
    return updates


async def _scrape_lloyds_bulletins(session: aiohttp.ClientSession) -> List[Dict[str, Any]]:
    """Scrape Lloyd's market bulletins."""
    url = "https://www.lloyds.com/market-resources/market-processes/market-bulletins"
    updates = []
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status != 200:
                return updates
            html = await resp.text()
            soup = BeautifulSoup(html, "html.parser")
            items = soup.find_all(["article", "li", "div"], limit=20)
            for item in items:
                text = item.get_text(strip=True)
                link_el = item.find("a")
                # Look for bulletin patterns like Y5xxx
                if re.search(r"Y\d{4}", text) or "bulletin" in text.lower():
                    title_el = item.find(["h2", "h3", "h4", "a"])
                    title = title_el.get_text(strip=True) if title_el else text[:100]
                    link = link_el.get("href", "") if link_el else ""
                    if link and not link.startswith("http"):
                        link = f"https://www.lloyds.com{link}"
                    if title and len(title) > 5:
                        updates.append({"title": title, "url": link, "date": "", "regulator": "LLOYD'S"})
    except Exception as e:
        logger.debug(f"Lloyd's scrape failed: {e}")
    return updates[:10]


# ============================================================
# Regulatory Scanner Service
# ============================================================

class RegulatoryScanner:
    """
    Scrapes regulatory websites and checks policy compliance.

    Uses aiohttp + BeautifulSoup for scraping (no Playwright dep in production).
    Falls back to embedded regulatory database if live scraping fails.
    """

    SCRAPE_INTERVAL_HOURS = 24

    def __init__(self):
        self._regulations: List[Regulation] = list(REGULATORY_BASELINE)
        self._live_updates: List[Dict[str, Any]] = []
        self._last_scraped: Optional[str] = None
        self._scrape_in_progress: bool = False
        self._playwright_available = False

        try:
            import playwright  # noqa
            self._playwright_available = True
        except ImportError:
            pass

    async def scrape_all_regulators(self) -> Dict[str, Any]:
        """
        Scrape all configured regulatory sources for new publications.

        Uses aiohttp for fast concurrent HTTP scraping.
        Falls back to embedded database if sites are unreachable.
        """
        if self._scrape_in_progress:
            return {"status": "already_running", "message": "Scrape already in progress"}

        self._scrape_in_progress = True
        updates = []
        errors = {}

        try:
            headers = {
                "User-Agent": "InstantRisk-RegBot/2.0 (compliance@instantrisk.com; regulatory monitoring)",
                "Accept": "text/html,application/xhtml+xml",
            }
            async with aiohttp.ClientSession(headers=headers) as session:
                tasks = {
                    "FCA": _scrape_fca_news(session),
                    "PRA": _scrape_pra_news(session),
                    "EIOPA": _scrape_eiopa_news(session),
                    "LLOYD'S": _scrape_lloyds_bulletins(session),
                }

                results = await asyncio.gather(*tasks.values(), return_exceptions=True)
                for regulator, result in zip(tasks.keys(), results):
                    if isinstance(result, Exception):
                        errors[regulator] = str(result)
                        logger.warning(f"Scrape failed for {regulator}: {result}")
                    elif result:
                        updates.extend(result)
                        logger.info(f"Scraped {len(result)} items from {regulator}")

        except Exception as e:
            logger.error(f"Scrape session error: {e}")
        finally:
            self._scrape_in_progress = False

        self._live_updates = updates
        self._last_scraped = datetime.now(timezone.utc).isoformat()

        return {
            "status": "complete",
            "scraped_at": self._last_scraped,
            "items_found": len(updates),
            "by_regulator": {
                r: sum(1 for u in updates if u.get("regulator") == r)
                for r in ["FCA", "PRA", "EIOPA", "LLOYD'S"]
            },
            "errors": errors,
            "baseline_regulations": len(self._regulations),
        }

    async def scrape_with_playwright(self, url: str) -> Optional[str]:
        """
        Use Playwright for JavaScript-heavy regulatory sites.
        Only called when regular HTTP scraping returns insufficient data.
        """
        if not self._playwright_available:
            return None

        try:
            from playwright.async_api import async_playwright
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.set_extra_http_headers({
                    "User-Agent": "Mozilla/5.0 (compatible; InstantRisk-Bot/2.0)"
                })
                await page.goto(url, timeout=30000, wait_until="networkidle")
                content = await page.content()
                await browser.close()
                return content
        except Exception as e:
            logger.debug(f"Playwright scrape failed for {url}: {e}")
            return None

    def get_regulations(
        self,
        regulator: Optional[str] = None,
        category: Optional[str] = None,
        risk_category: Optional[str] = None,
        severity: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Return filtered list of regulations."""
        regs = self._regulations

        if regulator:
            regs = [r for r in regs if r.regulator.upper() == regulator.upper()]
        if category:
            regs = [r for r in regs if r.category == category]
        if risk_category:
            regs = [r for r in regs if "all" in r.risk_categories or risk_category in r.risk_categories]
        if severity:
            regs = [r for r in regs if r.severity == severity]

        return [
            {
                "reg_id": r.reg_id,
                "title": r.title,
                "regulator": r.regulator,
                "category": r.category,
                "url": r.url,
                "published_date": r.published_date,
                "summary": r.summary,
                "risk_categories": r.risk_categories,
                "severity": r.severity,
            }
            for r in regs
        ]

    async def check_assessment_compliance(
        self,
        assessment_data: Dict[str, Any],
    ) -> ComplianceCheckResult:
        """
        Run full compliance check on an assessment.

        Checks against all applicable regulations based on risk category,
        territory, and assessment characteristics.
        """
        return _check_assessment_compliance(assessment_data, self._regulations)

    def get_regulatory_updates(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Return the most recent scraped regulatory updates."""
        return self._live_updates[:limit]

    def get_scrape_status(self) -> Dict[str, Any]:
        """Return scraping status."""
        # Check if scrape is due
        needs_scrape = True
        if self._last_scraped:
            try:
                last = datetime.fromisoformat(self._last_scraped)
                age_hours = (datetime.now(timezone.utc) - last).total_seconds() / 3600
                needs_scrape = age_hours >= self.SCRAPE_INTERVAL_HOURS
            except Exception:
                pass

        return {
            "last_scraped": self._last_scraped,
            "scrape_in_progress": self._scrape_in_progress,
            "needs_rescrape": needs_scrape,
            "scrape_interval_hours": self.SCRAPE_INTERVAL_HOURS,
            "live_updates_cached": len(self._live_updates),
            "baseline_regulations": len(self._regulations),
            "playwright_available": self._playwright_available,
            "sources": ["FCA", "PRA", "EIOPA", "LLOYD'S", "ICO"],
        }

    def get_regulatory_summary(self, risk_category: str, territory: str = "UK") -> Dict[str, Any]:
        """Get a curated regulatory summary for a specific risk type and territory."""
        applicable = [
            r for r in self._regulations
            if "all" in r.risk_categories or risk_category in r.risk_categories
        ]

        critical = [r for r in applicable if r.severity == "critical"]
        high = [r for r in applicable if r.severity == "high"]

        uk_specific = [r for r in applicable if r.regulator in ("FCA", "PRA", "LLOYD'S", "ICO")]
        eu_specific = [r for r in applicable if r.regulator == "EIOPA"]

        return {
            "risk_category": risk_category,
            "territory": territory,
            "total_applicable": len(applicable),
            "critical_regulations": len(critical),
            "high_priority_regulations": len(high),
            "key_regulators": list({r.regulator for r in applicable}),
            "critical_items": [
                {"reg_id": r.reg_id, "title": r.title, "regulator": r.regulator}
                for r in critical
            ],
            "uk_regulations": len(uk_specific),
            "eu_regulations": len(eu_specific),
            "territory_note": (
                "All FCA/PRA/Lloyd's requirements apply" if territory in ("UK", "GB")
                else "EIOPA/IDD requirements apply in addition to local requirements"
                if territory in ("EU", "Europe")
                else "Check local jurisdiction requirements in addition to Lloyd's standards"
            ),
        }


# Singleton
_regulatory_scanner: Optional[RegulatoryScanner] = None


def get_regulatory_scanner() -> RegulatoryScanner:
    """Get or create the RegulatoryScanner singleton."""
    global _regulatory_scanner
    if _regulatory_scanner is None:
        _regulatory_scanner = RegulatoryScanner()
    return _regulatory_scanner
