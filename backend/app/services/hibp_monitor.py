"""
Have I Been Pwned (HIBP) Breach Monitoring Service

Monitors data breaches for insured companies using HIBP API.
No API key required for basic breach checking.
"""

import logging
import asyncio
from typing import List, Dict, Optional, Any
from datetime import datetime, timezone

import aiohttp
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment import Assessment

logger = logging.getLogger(__name__)


class HIBPMonitor:
    """
    Have I Been Pwned breach monitoring.

    Free API (no key required): https://haveibeenpwned.com/API/v3
    Rate limit: 1 request every 1.5 seconds per domain
    """

    HIBP_API = "https://haveibeenpwned.com/api/v3"

    def __init__(self):
        self.headers = {
            "User-Agent": "InstantRisk-Platform",
            "hibp-api-version": "3"
        }

    async def check_breach(self, email_domain: str) -> List[Dict]:
        """
        Check if domain has been involved in data breaches.

        Args:
            email_domain: Email domain to check (e.g., "acme.com")

        Returns:
            List of breaches with details
        """

        url = f"{self.HIBP_API}/breaches"

        try:
            async with aiohttp.ClientSession() as session:
                # Note: Domain-specific search requires API key
                # For now, get all breaches and filter client-side
                async with session.get(url, headers=self.headers) as response:
                    if response.status == 200:
                        all_breaches = await response.json()

                        # Filter for domain
                        domain_breaches = [
                            breach for breach in all_breaches
                            if email_domain.lower() in breach.get('Domain', '').lower()
                        ]

                        return domain_breaches

                    elif response.status == 429:
                        logger.warning("HIBP rate limit exceeded")
                        return []

                    else:
                        logger.error(f"HIBP API error: {response.status}")
                        return []

        except Exception as e:
            logger.error(f"HIBP check failed for {email_domain}: {e}")
            return []

    async def check_email(self, email: str) -> List[Dict]:
        """
        Check if specific email address has been pwned.

        Note: Requires API key for email search. Using domain search instead.
        """

        domain = email.split('@')[1] if '@' in email else email
        return await self.check_breach(domain)

    async def monitor_assessment(
        self,
        db: AsyncSession,
        assessment: Assessment
    ) -> Dict[str, Any]:
        """
        Monitor assessment for data breaches.

        Checks insured company email domain against HIBP.
        """

        if not assessment.insured_name:
            return {"status": "skipped", "reason": "No insured name"}

        # Extract or infer domain
        # For now, we'll need broker_email or insured_email field
        # Fallback: check if description mentions email/domain

        # Placeholder: In production, extract domain from:
        # - broker_reference email
        # - insured company website
        # - OCR extracted email addresses from documents

        domain = self._extract_domain_from_assessment(assessment)
        if not domain:
            return {"status": "skipped", "reason": "No domain found"}

        # Check breaches
        breaches = await self.check_breach(domain)

        # Respect rate limit (1 request per 1.5 seconds)
        await asyncio.sleep(1.5)

        if breaches:
            severity = "critical" if len(breaches) > 5 else "medium" if len(breaches) > 1 else "low"

            return {
                "status": "breaches_found",
                "domain": domain,
                "breach_count": len(breaches),
                "severity": severity,
                "breaches": [
                    {
                        "name": b.get('Name'),
                        "date": b.get('BreachDate'),
                        "pwn_count": b.get('PwnCount'),
                        "description": b.get('Description', '')[:200]
                    }
                    for b in breaches[:5]  # Top 5 breaches
                ]
            }
        else:
            return {
                "status": "clean",
                "domain": domain,
                "breach_count": 0
            }

    def _extract_domain_from_assessment(self, assessment: Assessment) -> Optional[str]:
        """
        Extract email domain from assessment data.

        Looks for:
        - broker_reference field (if contains email)
        - insured_name (convert to domain guess)
        - description text
        """

        # Check broker reference
        if assessment.broker_reference and '@' in assessment.broker_reference:
            return assessment.broker_reference.split('@')[1]

        # Infer from company name (simple heuristic)
        if assessment.insured_name:
            # "Acme Corporation" → "acme.com"
            name = assessment.insured_name.lower()
            name = name.replace(' corporation', '').replace(' corp', '').replace(' inc', '')
            name = name.replace(' ltd', '').replace(' limited', '').replace(',', '')
            name = name.strip().replace(' ', '')
            return f"{name}.com"  # Naive but works for demos

        return None

    async def batch_monitor_active_assessments(
        self,
        db: AsyncSession,
        max_checks: int = 100
    ) -> List[Dict]:
        """
        Batch check active assessments for breaches.

        Run this as scheduled job (daily).
        """

        # Get active assessments
        query = select(Assessment).where(
            Assessment.status.in_(['active', 'pending', 'draft'])
        ).limit(max_checks)

        result = await db.execute(query)
        assessments = result.scalars().all()

        logger.info(f"Monitoring {len(assessments)} active assessments for breaches...")

        alerts = []
        for assessment in assessments:
            result = await self.monitor_assessment(db, assessment)

            if result['status'] == 'breaches_found':
                alerts.append({
                    "assessment_id": str(assessment.id),
                    "reference": assessment.reference_number,
                    "insured": assessment.insured_name,
                    **result
                })

        logger.info(f"Found {len(alerts)} assessments with breach alerts")
        return alerts


# Singleton instance
hibp_monitor = HIBPMonitor()
