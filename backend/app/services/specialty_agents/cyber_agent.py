"""
InstantRisk V3 - Cyber Underwriting Agent

Specialized AI agent for cyber liability risk assessment.
Analyzes cyber security posture, data exposure, and business impact.
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional
from datetime import datetime


class CyberRiskLevel(Enum):
    """Cyber risk classification levels."""
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class IndustrySector(Enum):
    """Industry sectors with different cyber risk profiles."""
    HEALTHCARE = "healthcare"
    FINANCIAL = "financial"
    RETAIL = "retail"
    TECHNOLOGY = "technology"
    MANUFACTURING = "manufacturing"
    EDUCATION = "education"
    GOVERNMENT = "government"
    PROFESSIONAL_SERVICES = "professional_services"
    OTHER = "other"


@dataclass
class CyberAnalysis:
    """Results of cyber risk analysis."""
    risk_score: float  # 0-100
    risk_level: CyberRiskLevel
    recommended_limit: Decimal
    recommended_retention: Decimal
    premium_indication: Decimal
    key_concerns: List[str]
    mitigating_factors: List[str]
    coverage_recommendations: List[str]
    warranty_requirements: List[str]
    exclusion_recommendations: List[str]


@dataclass
class CyberWarranty:
    """A warranty requirement for cyber coverage."""
    code: str
    title: str
    description: str
    required: bool
    category: str  # access_control, backup, encryption, etc.


class CyberUnderwritingAgent:
    """
    AI agent specialized for cyber liability underwriting.

    Analyzes:
    - Security controls and posture
    - Data types and volume
    - Industry-specific risks
    - Incident history
    - Third-party exposure
    - Regulatory environment
    """

    # Cyber-specific risk factors
    RISK_FACTORS = {
        'data_types': {
            'pii': 0.3,      # Personal Identifiable Information
            'phi': 0.4,      # Protected Health Information
            'pci': 0.35,     # Payment Card Data
            'financial': 0.3,
            'intellectual_property': 0.25,
            'none_sensitive': 0.05,
        },
        'security_controls': {
            'mfa_enabled': -0.15,
            'encryption_at_rest': -0.10,
            'encryption_in_transit': -0.10,
            'endpoint_protection': -0.08,
            'siem_deployed': -0.10,
            'incident_response_plan': -0.08,
            'employee_training': -0.05,
            'backup_tested': -0.10,
            'patching_policy': -0.08,
        },
        'industry_base_risk': {
            IndustrySector.HEALTHCARE: 0.35,
            IndustrySector.FINANCIAL: 0.30,
            IndustrySector.RETAIL: 0.25,
            IndustrySector.TECHNOLOGY: 0.20,
            IndustrySector.MANUFACTURING: 0.18,
            IndustrySector.EDUCATION: 0.22,
            IndustrySector.GOVERNMENT: 0.28,
            IndustrySector.PROFESSIONAL_SERVICES: 0.18,
            IndustrySector.OTHER: 0.20,
        }
    }

    # Standard cyber warranties
    STANDARD_WARRANTIES = [
        CyberWarranty(
            code="CW001",
            title="Multi-Factor Authentication",
            description="MFA enabled for all remote access and privileged accounts",
            required=True,
            category="access_control",
        ),
        CyberWarranty(
            code="CW002",
            title="Backup Frequency",
            description="Critical data backed up at least daily with 30-day retention",
            required=True,
            category="backup",
        ),
        CyberWarranty(
            code="CW003",
            title="Backup Testing",
            description="Backup restoration tested at least quarterly",
            required=True,
            category="backup",
        ),
        CyberWarranty(
            code="CW004",
            title="Endpoint Protection",
            description="EDR/Antivirus deployed on all endpoints with auto-update",
            required=True,
            category="endpoint",
        ),
        CyberWarranty(
            code="CW005",
            title="Patch Management",
            description="Critical patches applied within 30 days of release",
            required=False,
            category="patching",
        ),
        CyberWarranty(
            code="CW006",
            title="Incident Response Plan",
            description="Documented and tested incident response plan",
            required=False,
            category="incident_response",
        ),
        CyberWarranty(
            code="CW007",
            title="Employee Training",
            description="Annual cybersecurity awareness training for all employees",
            required=False,
            category="training",
        ),
        CyberWarranty(
            code="CW008",
            title="Encryption",
            description="Data encrypted at rest and in transit",
            required=False,
            category="encryption",
        ),
    ]

    def __init__(self):
        pass

    async def analyze_cyber_submission(
        self,
        data: Dict[str, Any],
    ) -> CyberAnalysis:
        """
        Analyze a cyber insurance submission.

        Args:
            data: Submission data including:
                - revenue: Annual revenue
                - industry_sector: Industry classification
                - employee_count: Number of employees
                - data_types: Types of data held
                - security_controls: Security measures in place
                - incident_history: Past cyber incidents
                - vendor_exposure: Third-party risk

        Returns:
            CyberAnalysis with risk score and recommendations.
        """
        # Extract key inputs
        revenue = Decimal(str(data.get('revenue', 0)))
        industry = self._parse_industry(data.get('industry_sector', 'other'))
        employee_count = int(data.get('employee_count', 0))
        data_types = data.get('data_types', [])
        security_controls = data.get('security_controls', {})
        incident_history = data.get('incident_history', [])

        # Calculate base risk score
        base_score = self._calculate_base_score(industry, revenue, employee_count)

        # Adjust for data types
        data_score = self._score_data_types(data_types)

        # Adjust for security controls
        security_adjustment = self._score_security_controls(security_controls)

        # Adjust for incident history
        incident_adjustment = self._score_incident_history(incident_history)

        # Calculate final risk score (0-100)
        risk_score = min(100, max(0,
            base_score + (data_score * 30) + (security_adjustment * 30) + (incident_adjustment * 20)
        ))

        # Determine risk level
        risk_level = self._determine_risk_level(risk_score)

        # Calculate recommended limits and pricing
        recommended_limit = self._calculate_recommended_limit(revenue, risk_level)
        recommended_retention = self._calculate_retention(revenue, risk_level)
        premium_indication = self._calculate_premium(recommended_limit, risk_score, industry)

        # Generate concerns and recommendations
        key_concerns = self._identify_concerns(data, security_controls)
        mitigating_factors = self._identify_mitigating_factors(security_controls)
        coverage_recs = self._recommend_coverages(data)
        warranty_reqs = self._generate_warranty_requirements(security_controls, risk_level)
        exclusion_recs = self._recommend_exclusions(data, risk_level)

        return CyberAnalysis(
            risk_score=round(risk_score, 2),
            risk_level=risk_level,
            recommended_limit=recommended_limit,
            recommended_retention=recommended_retention,
            premium_indication=premium_indication,
            key_concerns=key_concerns,
            mitigating_factors=mitigating_factors,
            coverage_recommendations=coverage_recs,
            warranty_requirements=warranty_reqs,
            exclusion_recommendations=exclusion_recs,
        )

    async def generate_warranty_requirements(
        self,
        data: Dict[str, Any],
    ) -> List[CyberWarranty]:
        """
        Generate warranty requirements based on submission.

        Args:
            data: Submission data.

        Returns:
            List of required warranties.
        """
        security_controls = data.get('security_controls', {})
        analysis = await self.analyze_cyber_submission(data)

        warranties = []

        for warranty in self.STANDARD_WARRANTIES:
            # All required warranties are always included
            if warranty.required:
                warranties.append(warranty)
            # High risk submissions need all warranties
            elif analysis.risk_level in [CyberRiskLevel.HIGH, CyberRiskLevel.CRITICAL]:
                warranties.append(warranty)
            # Check if specific control is missing
            elif warranty.category == 'backup' and not security_controls.get('backup_tested'):
                warranties.append(warranty)
            elif warranty.category == 'patching' and not security_controls.get('patching_policy'):
                warranties.append(warranty)

        return warranties

    def _parse_industry(self, sector: str) -> IndustrySector:
        """Parse industry sector string to enum."""
        try:
            return IndustrySector(sector.lower())
        except ValueError:
            return IndustrySector.OTHER

    def _calculate_base_score(
        self,
        industry: IndustrySector,
        revenue: Decimal,
        employee_count: int,
    ) -> float:
        """Calculate base risk score from fundamentals."""
        # Industry base risk
        industry_risk = self.RISK_FACTORS['industry_base_risk'].get(industry, 0.20)

        # Size factor (larger = more exposure but often better security)
        if revenue > Decimal('1000000000'):  # >$1B
            size_factor = 0.15
        elif revenue > Decimal('100000000'):  # >$100M
            size_factor = 0.10
        elif revenue > Decimal('10000000'):  # >$10M
            size_factor = 0.05
        else:
            size_factor = 0.0

        # Employee count factor
        if employee_count > 5000:
            employee_factor = 0.10
        elif employee_count > 1000:
            employee_factor = 0.05
        else:
            employee_factor = 0.0

        return (industry_risk + size_factor + employee_factor) * 100

    def _score_data_types(self, data_types: List[str]) -> float:
        """Score based on types of data held."""
        if not data_types:
            return 0.1  # Unknown data = some risk

        score = 0.0
        for data_type in data_types:
            score += self.RISK_FACTORS['data_types'].get(
                data_type.lower(), 0.1
            )
        return min(1.0, score)

    def _score_security_controls(self, controls: Dict[str, bool]) -> float:
        """Score security controls (negative = risk reduction)."""
        adjustment = 0.0
        for control, enabled in controls.items():
            if enabled:
                adjustment += self.RISK_FACTORS['security_controls'].get(
                    control, 0.0
                )
        return adjustment  # Negative values reduce risk

    def _score_incident_history(self, incidents: List[Dict]) -> float:
        """Score based on incident history."""
        if not incidents:
            return -0.05  # No incidents = slight reduction

        # Recent incidents increase risk
        now = datetime.now()
        recent_incidents = 0
        severe_incidents = 0

        for incident in incidents:
            incident_date = incident.get('date')
            if incident_date:
                # Within last 3 years
                recent_incidents += 1
            if incident.get('severity', '').lower() in ['high', 'critical']:
                severe_incidents += 1

        return (recent_incidents * 0.10) + (severe_incidents * 0.15)

    def _determine_risk_level(self, score: float) -> CyberRiskLevel:
        """Determine risk level from score."""
        if score < 25:
            return CyberRiskLevel.LOW
        elif score < 50:
            return CyberRiskLevel.MODERATE
        elif score < 75:
            return CyberRiskLevel.HIGH
        else:
            return CyberRiskLevel.CRITICAL

    def _calculate_recommended_limit(
        self,
        revenue: Decimal,
        risk_level: CyberRiskLevel,
    ) -> Decimal:
        """Calculate recommended policy limit."""
        # Base limit as percentage of revenue
        base_percentages = {
            CyberRiskLevel.LOW: Decimal('0.05'),
            CyberRiskLevel.MODERATE: Decimal('0.10'),
            CyberRiskLevel.HIGH: Decimal('0.15'),
            CyberRiskLevel.CRITICAL: Decimal('0.20'),
        }

        base = revenue * base_percentages[risk_level]

        # Apply minimum and maximum limits
        min_limit = Decimal('1000000')  # $1M minimum
        max_limit = Decimal('100000000')  # $100M maximum

        return min(max_limit, max(min_limit, base))

    def _calculate_retention(
        self,
        revenue: Decimal,
        risk_level: CyberRiskLevel,
    ) -> Decimal:
        """Calculate recommended retention/deductible."""
        # Higher risk = higher retention
        retention_factors = {
            CyberRiskLevel.LOW: Decimal('0.001'),
            CyberRiskLevel.MODERATE: Decimal('0.002'),
            CyberRiskLevel.HIGH: Decimal('0.005'),
            CyberRiskLevel.CRITICAL: Decimal('0.01'),
        }

        base = revenue * retention_factors[risk_level]

        # Apply minimum and maximum
        min_retention = Decimal('10000')  # $10K minimum
        max_retention = Decimal('500000')  # $500K maximum

        return min(max_retention, max(min_retention, base))

    def _calculate_premium(
        self,
        limit: Decimal,
        risk_score: float,
        industry: IndustrySector,
    ) -> Decimal:
        """Calculate premium indication."""
        # Base rate varies by industry
        base_rates = {
            IndustrySector.HEALTHCARE: Decimal('0.025'),
            IndustrySector.FINANCIAL: Decimal('0.020'),
            IndustrySector.RETAIL: Decimal('0.018'),
            IndustrySector.TECHNOLOGY: Decimal('0.015'),
            IndustrySector.MANUFACTURING: Decimal('0.012'),
            IndustrySector.EDUCATION: Decimal('0.015'),
            IndustrySector.GOVERNMENT: Decimal('0.018'),
            IndustrySector.PROFESSIONAL_SERVICES: Decimal('0.012'),
            IndustrySector.OTHER: Decimal('0.015'),
        }

        base_rate = base_rates.get(industry, Decimal('0.015'))

        # Adjust for risk score
        risk_multiplier = Decimal('1') + (Decimal(str(risk_score)) / Decimal('100'))

        premium = limit * base_rate * risk_multiplier

        # Apply minimum premium
        return max(premium, Decimal('5000'))

    def _identify_concerns(
        self,
        data: Dict[str, Any],
        controls: Dict[str, bool],
    ) -> List[str]:
        """Identify key underwriting concerns."""
        concerns = []

        # Missing critical controls
        if not controls.get('mfa_enabled'):
            concerns.append("Multi-factor authentication not enabled")
        if not controls.get('backup_tested'):
            concerns.append("Backups not regularly tested")
        if not controls.get('endpoint_protection'):
            concerns.append("No endpoint detection/response solution")

        # High-risk data
        data_types = data.get('data_types', [])
        if 'phi' in data_types:
            concerns.append("Holds Protected Health Information (PHI) - HIPAA exposure")
        if 'pci' in data_types:
            concerns.append("Processes payment card data - PCI-DSS compliance required")

        # Incident history
        if data.get('incident_history'):
            concerns.append("Prior cyber incidents on record")

        return concerns

    def _identify_mitigating_factors(self, controls: Dict[str, bool]) -> List[str]:
        """Identify positive risk mitigating factors."""
        factors = []

        if controls.get('mfa_enabled'):
            factors.append("Multi-factor authentication deployed")
        if controls.get('siem_deployed'):
            factors.append("Security Information and Event Management (SIEM) in place")
        if controls.get('incident_response_plan'):
            factors.append("Documented incident response plan")
        if controls.get('employee_training'):
            factors.append("Regular security awareness training")
        if controls.get('encryption_at_rest') and controls.get('encryption_in_transit'):
            factors.append("Data encryption implemented")

        return factors

    def _recommend_coverages(self, data: Dict[str, Any]) -> List[str]:
        """Recommend appropriate coverages."""
        coverages = [
            "First-party breach response costs",
            "Business interruption",
            "Data restoration",
            "Cyber extortion/ransomware",
            "Third-party liability",
        ]

        # Add specific coverages based on data types
        if 'pci' in data.get('data_types', []):
            coverages.append("PCI-DSS fines and penalties")
        if 'phi' in data.get('data_types', []):
            coverages.append("HIPAA fines and penalties")

        return coverages

    def _generate_warranty_requirements(
        self,
        controls: Dict[str, bool],
        risk_level: CyberRiskLevel,
    ) -> List[str]:
        """Generate list of warranty requirements."""
        warranties = []

        # Always required
        if not controls.get('mfa_enabled'):
            warranties.append("Implement MFA for all remote access within 60 days")
        if not controls.get('backup_tested'):
            warranties.append("Test backup restoration quarterly")

        # Required for high risk
        if risk_level in [CyberRiskLevel.HIGH, CyberRiskLevel.CRITICAL]:
            if not controls.get('siem_deployed'):
                warranties.append("Deploy SIEM solution within 90 days")
            if not controls.get('incident_response_plan'):
                warranties.append("Implement incident response plan within 30 days")

        return warranties

    def _recommend_exclusions(
        self,
        data: Dict[str, Any],
        risk_level: CyberRiskLevel,
    ) -> List[str]:
        """Recommend policy exclusions."""
        exclusions = []

        # Standard exclusions
        exclusions.extend([
            "War and terrorism (cyber warfare)",
            "Prior known circumstances",
            "Intentional acts",
        ])

        # Risk-based exclusions
        if risk_level == CyberRiskLevel.CRITICAL:
            exclusions.append("Social engineering losses above sub-limit")
            exclusions.append("Cryptocurrency and digital asset losses")

        return exclusions
