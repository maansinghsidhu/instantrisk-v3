"""
Autonomous Investigation Agent for InstantRisk V2

Multi-agent system that autonomously investigates companies in 3 minutes using:
- LangGraph for orchestration
- Claude via Bedrock for synthesis
- Free public data sources (SEC EDGAR, OSHA, EPA, HIBP, Google News)

Architecture:
    State -> FinancialAgent -> RegulatoryAgent -> ReputationAgent
    -> CyberAgent -> SynthesisAgent -> Final Report
"""

import os
import json
import logging
import asyncio
import re
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, TypedDict
from urllib.parse import quote

import aiohttp
from bs4 import BeautifulSoup

# LangGraph imports
from langgraph.graph import StateGraph, END
from langchain_anthropic import ChatAnthropic

# Bedrock client for final synthesis
from app.services.bedrock_client import get_bedrock_client

logger = logging.getLogger(__name__)


# =============================================================================
# State Definition
# =============================================================================

class InvestigationState(TypedDict):
    """State passed between agents in the LangGraph workflow."""
    company_name: str
    assessment_id: str
    companies_house_number: Optional[str]

    # Agent outputs
    financial_data: Dict[str, Any]
    regulatory_data: Dict[str, Any]
    reputation_data: Dict[str, Any]
    cyber_data: Dict[str, Any]

    # Final report
    final_report: Dict[str, Any]

    # Metadata
    status: str
    errors: List[str]
    started_at: str
    completed_at: Optional[str]


# =============================================================================
# Free Data Source Helpers
# =============================================================================

async def fetch_sec_edgar_data(company_name: str) -> Dict[str, Any]:
    """
    Fetch SEC EDGAR 10-K filings for a company.

    Free API: https://data.sec.gov/submissions/
    Rate limit: Comply with SEC's fair access policy (identify with User-Agent)

    Returns:
        Dictionary with financial filings, recent forms, and key metrics
    """
    try:
        # SEC requires a User-Agent header with contact info
        headers = {
            "User-Agent": "InstantRisk-Bot/2.0 (compliance@instantrisk.com)"
        }

        # Search for company CIK using company name
        search_url = f"https://www.sec.gov/cgi-bin/browse-edgar?company={quote(company_name)}&action=getcompany&output=json"

        async with aiohttp.ClientSession(headers=headers) as session:
            # Note: SEC API doesn't have a direct JSON search endpoint
            # We'll parse the company search page for the CIK
            search_url_html = f"https://www.sec.gov/cgi-bin/browse-edgar?company={quote(company_name)}&action=getcompany"

            async with session.get(search_url_html, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status != 200:
                    return {"error": f"SEC search failed: {resp.status}", "filings": []}

                html = await resp.text()
                soup = BeautifulSoup(html, 'html.parser')

                # Extract CIK from the page
                cik_match = re.search(r'CIK=(\d{10})', html)
                if not cik_match:
                    return {"error": "Company not found in SEC database", "filings": []}

                cik = cik_match.group(1)

            # Fetch company submissions
            submissions_url = f"https://data.sec.gov/submissions/CIK{cik}.json"

            async with session.get(submissions_url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status != 200:
                    return {"error": f"Failed to fetch filings: {resp.status}", "cik": cik}

                data = await resp.json()

                # Extract recent 10-K and 10-Q filings
                recent_filings = data.get("filings", {}).get("recent", {})
                forms = recent_filings.get("form", [])
                filing_dates = recent_filings.get("filingDate", [])
                accession_numbers = recent_filings.get("accessionNumber", [])

                filings_10k = []
                for i, form in enumerate(forms[:20]):  # Check last 20 filings
                    if form in ["10-K", "10-Q"]:
                        filings_10k.append({
                            "form": form,
                            "filing_date": filing_dates[i] if i < len(filing_dates) else None,
                            "accession_number": accession_numbers[i] if i < len(accession_numbers) else None
                        })

                return {
                    "cik": cik,
                    "company_name": data.get("name", company_name),
                    "sic": data.get("sic", "Unknown"),
                    "sic_description": data.get("sicDescription", "Unknown"),
                    "recent_10k_filings": filings_10k[:5],  # Last 5 annual/quarterly reports
                    "business_address": data.get("addresses", {}).get("business", {}),
                    "fiscal_year_end": data.get("fiscalYearEnd", "Unknown")
                }

    except asyncio.TimeoutError:
        logger.warning(f"SEC EDGAR timeout for {company_name}")
        return {"error": "Request timeout", "filings": []}
    except Exception as e:
        logger.error(f"SEC EDGAR error for {company_name}: {e}")
        return {"error": str(e), "filings": []}


async def fetch_osha_violations(company_name: str) -> Dict[str, Any]:
    """
    Check OSHA violations database.

    Free API: https://data.osha.gov/

    Returns:
        Dictionary with violation count, severity, and recent cases
    """
    try:
        # OSHA Enforcement API
        headers = {"User-Agent": "InstantRisk-Bot/2.0"}

        # Search for inspections by establishment name
        url = f"https://data.dol.gov/get/inspection_detail/{quote(company_name)}"

        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                if resp.status != 200:
                    return {"violations_found": False, "message": "No OSHA data available"}

                data = await resp.json()

                # Parse violations
                violations = []
                if isinstance(data, list):
                    for record in data[:10]:  # Top 10 recent
                        violations.append({
                            "inspection_date": record.get("open_date"),
                            "citation_id": record.get("citation_id"),
                            "violation_type": record.get("violation_type"),
                            "penalty": record.get("current_penalty")
                        })

                return {
                    "violations_found": len(violations) > 0,
                    "total_violations": len(violations),
                    "recent_violations": violations,
                    "data_source": "OSHA Enforcement Database"
                }

    except Exception as e:
        logger.warning(f"OSHA API error for {company_name}: {e}")
        return {"violations_found": False, "error": str(e)}


async def fetch_epa_violations(company_name: str) -> Dict[str, Any]:
    """
    Check EPA violations database.

    Free API: https://echo.epa.gov/tools/web-services

    Returns:
        Dictionary with environmental violations and compliance status
    """
    try:
        headers = {"User-Agent": "InstantRisk-Bot/2.0"}

        # EPA ECHO API (Enforcement and Compliance History Online)
        # Search for facilities by name
        url = f"https://echodata.epa.gov/echo/facility_search.get_facility_info?output=JSON&p_fn={quote(company_name)}"

        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                if resp.status != 200:
                    return {"violations_found": False, "message": "No EPA data available"}

                data = await resp.json()
                results = data.get("Results", {}).get("Facilities", [])

                violations = []
                for facility in results[:5]:  # Top 5 facilities
                    violations.append({
                        "facility_name": facility.get("FacName"),
                        "registry_id": facility.get("RegistryID"),
                        "violations_3yr": facility.get("Violations3YrCnt", 0),
                        "compliance_status": facility.get("ComplianceStatus"),
                        "city": facility.get("FacCity"),
                        "state": facility.get("FacState")
                    })

                total_violations = sum(v.get("violations_3yr", 0) for v in violations)

                return {
                    "violations_found": total_violations > 0,
                    "total_violations_3yr": total_violations,
                    "facilities": violations,
                    "data_source": "EPA ECHO Database"
                }

    except Exception as e:
        logger.warning(f"EPA API error for {company_name}: {e}")
        return {"violations_found": False, "error": str(e)}


async def fetch_news_reputation(company_name: str) -> Dict[str, Any]:
    """
    Scrape Google News for company mentions.

    Free: Google News RSS feeds (no auth required)

    Returns:
        Dictionary with recent news articles and sentiment indicators
    """
    try:
        # Google News RSS feed
        search_query = quote(company_name)
        url = f"https://news.google.com/rss/search?q={search_query}&hl=en-US&gl=US&ceid=US:en"

        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                if resp.status != 200:
                    return {"articles_found": 0, "error": "News fetch failed"}

                xml = await resp.text()
                soup = BeautifulSoup(xml, 'xml')

                items = soup.find_all('item')[:10]  # Top 10 articles

                articles = []
                for item in items:
                    articles.append({
                        "title": item.title.text if item.title else "No title",
                        "link": item.link.text if item.link else "",
                        "pub_date": item.pubDate.text if item.pubDate else "",
                        "source": item.source.text if item.source else "Unknown"
                    })

                # Simple sentiment heuristics (negative keywords)
                negative_keywords = ["scandal", "lawsuit", "fraud", "breach", "violation", "fine", "penalty", "convicted", "investigation"]
                negative_count = sum(
                    1 for article in articles
                    if any(kw in article["title"].lower() for kw in negative_keywords)
                )

                return {
                    "articles_found": len(articles),
                    "recent_articles": articles,
                    "negative_mentions": negative_count,
                    "sentiment_score": max(0, 100 - (negative_count * 20)),  # 0-100 scale
                    "data_source": "Google News RSS"
                }

    except Exception as e:
        logger.warning(f"News scraping error for {company_name}: {e}")
        return {"articles_found": 0, "error": str(e)}


async def check_hibp_breaches(company_name: str) -> Dict[str, Any]:
    """
    Check Have I Been Pwned for data breaches.

    Free API: https://haveibeenpwned.com/API/v3
    Note: Requires API key for account searches, but breach list is free

    Returns:
        Dictionary with known breaches related to company domain
    """
    try:
        # Extract potential domain from company name
        domain = company_name.lower().replace(" ", "").replace(",", "").replace("inc", "").replace("ltd", "").strip()
        domain = f"{domain}.com"  # Simple heuristic

        headers = {"User-Agent": "InstantRisk-Bot/2.0"}

        # HIBP Breaches API (free, no key needed for breach list)
        url = "https://haveibeenpwned.com/api/v3/breaches"

        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                if resp.status != 200:
                    return {"breaches_found": False, "message": "HIBP API unavailable"}

                all_breaches = await resp.json()

                # Filter for breaches matching company domain
                company_breaches = [
                    breach for breach in all_breaches
                    if domain.replace(".com", "") in breach.get("Domain", "").lower()
                    or company_name.lower() in breach.get("Name", "").lower()
                ]

                return {
                    "breaches_found": len(company_breaches) > 0,
                    "total_breaches": len(company_breaches),
                    "breaches": [
                        {
                            "name": b.get("Name"),
                            "breach_date": b.get("BreachDate"),
                            "pwn_count": b.get("PwnCount"),
                            "data_classes": b.get("DataClasses", [])
                        }
                        for b in company_breaches[:5]
                    ],
                    "data_source": "Have I Been Pwned"
                }

    except Exception as e:
        logger.warning(f"HIBP error for {company_name}: {e}")
        return {"breaches_found": False, "error": str(e)}


async def check_cve_database(company_name: str) -> Dict[str, Any]:
    """
    Check CVE database for known vulnerabilities.

    Free API: https://cve.mitre.org/

    Returns:
        Dictionary with CVE vulnerabilities mentioning the company
    """
    try:
        # NVD API (National Vulnerability Database)
        url = f"https://services.nvd.nist.gov/rest/json/cves/2.0?keywordSearch={quote(company_name)}"

        headers = {"User-Agent": "InstantRisk-Bot/2.0"}

        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                if resp.status != 200:
                    return {"vulnerabilities_found": False, "message": "CVE database unavailable"}

                data = await resp.json()
                vulnerabilities = data.get("vulnerabilities", [])

                cves = []
                for vuln in vulnerabilities[:10]:
                    cve_data = vuln.get("cve", {})
                    cves.append({
                        "cve_id": cve_data.get("id"),
                        "published": cve_data.get("published"),
                        "severity": cve_data.get("metrics", {}).get("cvssMetricV31", [{}])[0].get("cvssData", {}).get("baseSeverity", "Unknown"),
                        "description": cve_data.get("descriptions", [{}])[0].get("value", "No description")[:200]
                    })

                return {
                    "vulnerabilities_found": len(cves) > 0,
                    "total_cves": len(cves),
                    "cves": cves,
                    "data_source": "NIST NVD"
                }

    except Exception as e:
        logger.warning(f"CVE database error for {company_name}: {e}")
        return {"vulnerabilities_found": False, "error": str(e)}


# =============================================================================
# Agent Nodes
# =============================================================================

async def financial_agent(state: InvestigationState) -> InvestigationState:
    """
    Financial Agent: Scrape SEC EDGAR for 10-K filings.
    """
    logger.info(f"Financial Agent investigating: {state['company_name']}")

    try:
        financial_data = await fetch_sec_edgar_data(state['company_name'])
        state['financial_data'] = financial_data
        state['status'] = 'financial_complete'
    except Exception as e:
        logger.error(f"Financial agent error: {e}")
        state['errors'].append(f"Financial agent: {str(e)}")
        state['financial_data'] = {"error": str(e)}

    return state


async def regulatory_agent(state: InvestigationState) -> InvestigationState:
    """
    Regulatory Agent: Check OSHA/EPA violations.
    """
    logger.info(f"Regulatory Agent investigating: {state['company_name']}")

    try:
        osha_data = await fetch_osha_violations(state['company_name'])
        epa_data = await fetch_epa_violations(state['company_name'])

        state['regulatory_data'] = {
            "osha": osha_data,
            "epa": epa_data
        }
        state['status'] = 'regulatory_complete'
    except Exception as e:
        logger.error(f"Regulatory agent error: {e}")
        state['errors'].append(f"Regulatory agent: {str(e)}")
        state['regulatory_data'] = {"error": str(e)}

    return state


async def reputation_agent(state: InvestigationState) -> InvestigationState:
    """
    Reputation Agent: Scrape Google News for mentions.
    """
    logger.info(f"Reputation Agent investigating: {state['company_name']}")

    try:
        news_data = await fetch_news_reputation(state['company_name'])
        state['reputation_data'] = news_data
        state['status'] = 'reputation_complete'
    except Exception as e:
        logger.error(f"Reputation agent error: {e}")
        state['errors'].append(f"Reputation agent: {str(e)}")
        state['reputation_data'] = {"error": str(e)}

    return state


async def cyber_agent(state: InvestigationState) -> InvestigationState:
    """
    Cyber Agent: Check HIBP + CVE database.
    """
    logger.info(f"Cyber Agent investigating: {state['company_name']}")

    try:
        hibp_data = await check_hibp_breaches(state['company_name'])
        cve_data = await check_cve_database(state['company_name'])

        state['cyber_data'] = {
            "hibp": hibp_data,
            "cve": cve_data
        }
        state['status'] = 'cyber_complete'
    except Exception as e:
        logger.error(f"Cyber agent error: {e}")
        state['errors'].append(f"Cyber agent: {str(e)}")
        state['cyber_data'] = {"error": str(e)}

    return state


async def synthesis_agent(state: InvestigationState) -> InvestigationState:
    """
    Synthesis Agent: Use Bedrock Claude to create comprehensive 20-page report.
    """
    logger.info(f"Synthesis Agent creating report for: {state['company_name']}")

    try:
        # Prepare all collected data
        investigation_summary = {
            "company_name": state['company_name'],
            "financial_findings": state.get('financial_data', {}),
            "regulatory_findings": state.get('regulatory_data', {}),
            "reputation_findings": state.get('reputation_data', {}),
            "cyber_findings": state.get('cyber_data', {})
        }

        # Build prompt for Claude
        prompt = f"""You are a senior insurance underwriter conducting a comprehensive risk investigation.

Company: {state['company_name']}
Assessment ID: {state['assessment_id']}

Investigation Data Collected:

FINANCIAL DATA (SEC EDGAR):
{json.dumps(state.get('financial_data', {}), indent=2)}

REGULATORY DATA (OSHA/EPA):
{json.dumps(state.get('regulatory_data', {}), indent=2)}

REPUTATION DATA (Google News):
{json.dumps(state.get('reputation_data', {}), indent=2)}

CYBER SECURITY DATA (HIBP/CVE):
{json.dumps(state.get('cyber_data', {}), indent=2)}

---

Create a comprehensive 20-page investigation report in the following format:

# EXECUTIVE SUMMARY
- Overall risk rating (Low/Medium/High/Critical)
- Key findings (3-5 bullet points)
- Underwriting recommendation (GO/NO-GO/REFER)

# FINANCIAL ANALYSIS
- SEC filing history and compliance
- Industry classification (SIC code analysis)
- Financial health indicators
- Red flags or concerns

# REGULATORY COMPLIANCE
- OSHA violation history
- EPA environmental compliance
- Regulatory risk assessment
- Industry-specific compliance issues

# REPUTATION & NEWS ANALYSIS
- Recent news sentiment
- Public perception analysis
- Crisis or controversy indicators
- Brand risk assessment

# CYBER SECURITY POSTURE
- Data breach history
- Known vulnerabilities (CVEs)
- Cyber risk exposure
- Security maturity estimate

# RISK SCORING MATRIX
Provide scores (0-100) for:
- Financial Risk
- Regulatory Risk
- Reputation Risk
- Cyber Risk
- Overall Composite Risk

# UNDERWRITING RECOMMENDATIONS
- Specific coverage considerations
- Premium loading factors
- Policy exclusions to consider
- Required additional due diligence

# APPENDICES
- Data sources and methodology
- Limitations and disclaimers
- Suggested follow-up investigations

Format the report in clear, professional markdown. Be thorough but concise. Highlight critical risks prominently."""

        # Call Bedrock Claude for synthesis
        bedrock = get_bedrock_client()

        messages = [
            {"role": "user", "content": prompt}
        ]

        report_text = await bedrock.chat(
            messages=messages,
            temperature=0.3,
            max_tokens=16000  # Allow for comprehensive report
        )

        # Parse risk scores from report (simple regex extraction)
        risk_score_match = re.search(r'Overall Composite Risk[:\s]+(\d+)', report_text)
        overall_risk_score = int(risk_score_match.group(1)) if risk_score_match else 50

        # Extract recommendation
        recommendation = "REFER"  # Default
        if "GO" in report_text and "NO-GO" not in report_text:
            recommendation = "GO"
        elif "NO-GO" in report_text or "DECLINE" in report_text:
            recommendation = "NO_GO"

        state['final_report'] = {
            "report_text": report_text,
            "overall_risk_score": overall_risk_score,
            "recommendation": recommendation,
            "executive_summary": report_text.split("# FINANCIAL ANALYSIS")[0] if "# FINANCIAL ANALYSIS" in report_text else report_text[:1000],
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "investigation_summary": investigation_summary
        }

        state['status'] = 'completed'
        state['completed_at'] = datetime.now(timezone.utc).isoformat()

    except Exception as e:
        logger.error(f"Synthesis agent error: {e}")
        state['errors'].append(f"Synthesis agent: {str(e)}")
        state['final_report'] = {
            "error": str(e),
            "report_text": "Report generation failed"
        }
        state['status'] = 'failed'

    return state


# =============================================================================
# LangGraph Workflow
# =============================================================================

def create_investigation_workflow() -> StateGraph:
    """
    Create the LangGraph workflow for autonomous investigation.

    Flow: Financial -> Regulatory -> Reputation -> Cyber -> Synthesis
    """
    workflow = StateGraph(InvestigationState)

    # Add agent nodes
    workflow.add_node("financial", financial_agent)
    workflow.add_node("regulatory", regulatory_agent)
    workflow.add_node("reputation", reputation_agent)
    workflow.add_node("cyber", cyber_agent)
    workflow.add_node("synthesis", synthesis_agent)

    # Define edges (sequential execution)
    workflow.set_entry_point("financial")
    workflow.add_edge("financial", "regulatory")
    workflow.add_edge("regulatory", "reputation")
    workflow.add_edge("reputation", "cyber")
    workflow.add_edge("cyber", "synthesis")
    workflow.add_edge("synthesis", END)

    return workflow.compile()


# =============================================================================
# Main Investigation Function
# =============================================================================

async def run_autonomous_investigation(
    company_name: str,
    assessment_id: str,
    companies_house_number: Optional[str] = None
) -> Dict[str, Any]:
    """
    Run autonomous investigation on a company.

    Args:
        company_name: Name of the company to investigate
        assessment_id: Associated assessment ID
        companies_house_number: Optional UK Companies House registration number

    Returns:
        Complete investigation report dictionary
    """
    logger.info(f"Starting autonomous investigation for: {company_name}")

    # Initialize state
    initial_state: InvestigationState = {
        "company_name": company_name,
        "assessment_id": assessment_id,
        "companies_house_number": companies_house_number,
        "financial_data": {},
        "regulatory_data": {},
        "reputation_data": {},
        "cyber_data": {},
        "final_report": {},
        "status": "started",
        "errors": [],
        "started_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None
    }

    # Create and run workflow
    workflow = create_investigation_workflow()

    try:
        # Execute the workflow
        final_state = await workflow.ainvoke(initial_state)

        logger.info(f"Investigation completed for {company_name}: {final_state['status']}")

        return final_state

    except Exception as e:
        logger.error(f"Investigation workflow failed: {e}")
        return {
            **initial_state,
            "status": "failed",
            "errors": [str(e)],
            "final_report": {"error": str(e)}
        }
