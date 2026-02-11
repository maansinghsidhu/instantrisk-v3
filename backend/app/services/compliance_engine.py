"""
InstantRisk V3 - Compliance Automation Engine

Automates Lloyd's regulatory compliance submissions:
- PMDR (Premium and Claims Market Data Returns)
- RDS (Realistic Disaster Scenarios)
- Solvency II / QRT templates

Addresses Gap 6: Regulatory Compliance Burden
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from enum import Enum
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lloyds import (
    ComplianceSubmission,
    ComplianceRule,
    ExposureSnapshot,
    ExposureAggregate,
)


class SubmissionType(Enum):
    """Types of compliance submissions."""
    PMDR = "PMDR"  # Premium and Claims Market Data Returns
    RDS = "RDS"    # Realistic Disaster Scenarios
    QRT = "QRT"    # Quantitative Reporting Templates (Solvency II)
    SCR = "SCR"    # Solvency Capital Requirement


class ValidationSeverity(Enum):
    """Validation result severity."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationResult:
    """Result of a validation check."""
    rule_code: str
    field: str
    severity: ValidationSeverity
    message: str
    actual_value: Any = None
    expected_value: Any = None


@dataclass
class PMDRReport:
    """PMDR submission data structure."""
    period: str
    syndicate_id: int
    gross_written_premium: Decimal
    net_written_premium: Decimal
    gross_earned_premium: Decimal
    net_earned_premium: Decimal
    gross_claims_paid: Decimal
    net_claims_paid: Decimal
    gross_claims_outstanding: Decimal
    net_claims_outstanding: Decimal
    reinsurance_premium_ceded: Decimal
    reinsurance_recoveries: Decimal
    by_class: Dict[str, Dict[str, Decimal]]
    by_year_of_account: Dict[str, Dict[str, Decimal]]


@dataclass
class RDSReport:
    """RDS submission data structure."""
    period: str
    syndicate_id: int
    scenarios: List[Dict[str, Any]]
    total_gross_loss: Decimal
    total_net_loss: Decimal
    pml_100yr: Decimal
    pml_250yr: Decimal


class ComplianceAutomationEngine:
    """
    Engine for automating regulatory compliance submissions.

    Uses AI agents for:
    - Data aggregation and validation
    - Cross-checking against rules
    - Report generation
    """

    # Standard RDS scenarios required by Lloyd's
    RDS_SCENARIOS = [
        {"id": "RDS1", "name": "Florida Windstorm", "type": "nat_cat", "region": "US_FL"},
        {"id": "RDS2", "name": "Gulf of Mexico Windstorm", "type": "nat_cat", "region": "US_GOM"},
        {"id": "RDS3", "name": "California Earthquake", "type": "nat_cat", "region": "US_CA"},
        {"id": "RDS4", "name": "New Madrid Earthquake", "type": "nat_cat", "region": "US_NM"},
        {"id": "RDS5", "name": "Japanese Earthquake", "type": "nat_cat", "region": "JP"},
        {"id": "RDS6", "name": "European Windstorm", "type": "nat_cat", "region": "EU"},
        {"id": "RDS7", "name": "UK Flood", "type": "nat_cat", "region": "UK"},
        {"id": "RDS8", "name": "Terrorism", "type": "man_made", "region": "GLOBAL"},
        {"id": "RDS9", "name": "Marine Collision", "type": "man_made", "region": "GLOBAL"},
        {"id": "RDS10", "name": "Aviation Collision", "type": "man_made", "region": "GLOBAL"},
        {"id": "RDS11", "name": "Cyber Attack", "type": "man_made", "region": "GLOBAL"},
    ]

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================================================================
    # PMDR Generation
    # =========================================================================

    async def generate_pmdr_return(
        self,
        syndicate_id: int,
        period: str,
        save: bool = True,
    ) -> PMDRReport:
        """
        Generate PMDR (Premium and Claims Market Data Return).

        Args:
            syndicate_id: Syndicate identifier.
            period: Reporting period (e.g., "2026-Q1").
            save: Whether to save to database.

        Returns:
            PMDRReport with all required data.
        """
        # Calculate premium data
        premium_data = await self._calculate_premium_data(syndicate_id, period)

        # Calculate claims data
        claims_data = await self._calculate_claims_data(syndicate_id, period)

        # Calculate reinsurance data
        reinsurance_data = await self._calculate_reinsurance_data(syndicate_id, period)

        # Aggregate by class of business
        by_class = await self._aggregate_by_class(syndicate_id, period)

        # Aggregate by year of account
        by_yoa = await self._aggregate_by_year_of_account(syndicate_id, period)

        report = PMDRReport(
            period=period,
            syndicate_id=syndicate_id,
            gross_written_premium=premium_data.get("gross_written", Decimal("0")),
            net_written_premium=premium_data.get("net_written", Decimal("0")),
            gross_earned_premium=premium_data.get("gross_earned", Decimal("0")),
            net_earned_premium=premium_data.get("net_earned", Decimal("0")),
            gross_claims_paid=claims_data.get("gross_paid", Decimal("0")),
            net_claims_paid=claims_data.get("net_paid", Decimal("0")),
            gross_claims_outstanding=claims_data.get("gross_outstanding", Decimal("0")),
            net_claims_outstanding=claims_data.get("net_outstanding", Decimal("0")),
            reinsurance_premium_ceded=reinsurance_data.get("premium_ceded", Decimal("0")),
            reinsurance_recoveries=reinsurance_data.get("recoveries", Decimal("0")),
            by_class=by_class,
            by_year_of_account=by_yoa,
        )

        if save:
            await self._save_submission(
                syndicate_id=syndicate_id,
                submission_type=SubmissionType.PMDR.value,
                period=period,
                data=self._pmdr_to_dict(report),
            )

        return report

    async def _calculate_premium_data(
        self,
        syndicate_id: int,
        period: str,
    ) -> Dict[str, Decimal]:
        """Calculate premium figures for PMDR."""
        # In production, this would query actual premium tables
        # For now, return placeholder structure
        return {
            "gross_written": Decimal("0"),
            "net_written": Decimal("0"),
            "gross_earned": Decimal("0"),
            "net_earned": Decimal("0"),
        }

    async def _calculate_claims_data(
        self,
        syndicate_id: int,
        period: str,
    ) -> Dict[str, Decimal]:
        """Calculate claims figures for PMDR."""
        return {
            "gross_paid": Decimal("0"),
            "net_paid": Decimal("0"),
            "gross_outstanding": Decimal("0"),
            "net_outstanding": Decimal("0"),
        }

    async def _calculate_reinsurance_data(
        self,
        syndicate_id: int,
        period: str,
    ) -> Dict[str, Decimal]:
        """Calculate reinsurance figures for PMDR."""
        return {
            "premium_ceded": Decimal("0"),
            "recoveries": Decimal("0"),
        }

    async def _aggregate_by_class(
        self,
        syndicate_id: int,
        period: str,
    ) -> Dict[str, Dict[str, Decimal]]:
        """Aggregate data by class of business."""
        # Query exposure aggregates by class
        result = await self.db.execute(
            select(ExposureAggregate)
            .where(ExposureAggregate.syndicate_id == syndicate_id)
            .where(ExposureAggregate.aggregation_type == "class")
        )
        aggregates = result.scalars().all()

        by_class = {}
        for agg in aggregates:
            by_class[agg.aggregation_key] = {
                "exposure": agg.current_exposure,
                "premium": Decimal("0"),  # Would come from premium tables
            }

        return by_class

    async def _aggregate_by_year_of_account(
        self,
        syndicate_id: int,
        period: str,
    ) -> Dict[str, Dict[str, Decimal]]:
        """Aggregate data by year of account."""
        return {}  # Would query actual YOA data

    def _pmdr_to_dict(self, report: PMDRReport) -> Dict[str, Any]:
        """Convert PMDRReport to dictionary for storage."""
        return {
            "period": report.period,
            "syndicate_id": report.syndicate_id,
            "gross_written_premium": str(report.gross_written_premium),
            "net_written_premium": str(report.net_written_premium),
            "gross_earned_premium": str(report.gross_earned_premium),
            "net_earned_premium": str(report.net_earned_premium),
            "gross_claims_paid": str(report.gross_claims_paid),
            "net_claims_paid": str(report.net_claims_paid),
            "gross_claims_outstanding": str(report.gross_claims_outstanding),
            "net_claims_outstanding": str(report.net_claims_outstanding),
            "reinsurance_premium_ceded": str(report.reinsurance_premium_ceded),
            "reinsurance_recoveries": str(report.reinsurance_recoveries),
            "by_class": report.by_class,
            "by_year_of_account": report.by_year_of_account,
        }

    # =========================================================================
    # RDS Calculation
    # =========================================================================

    async def calculate_rds(
        self,
        syndicate_id: int,
        period: Optional[str] = None,
        save: bool = True,
    ) -> RDSReport:
        """
        Calculate Realistic Disaster Scenarios.

        Args:
            syndicate_id: Syndicate identifier.
            period: Reporting period (defaults to current year).
            save: Whether to save to database.

        Returns:
            RDSReport with all scenario results.
        """
        if not period:
            period = datetime.now().strftime("%Y")

        scenarios = []
        total_gross = Decimal("0")
        total_net = Decimal("0")

        for scenario_def in self.RDS_SCENARIOS:
            scenario_result = await self._calculate_scenario(
                syndicate_id, scenario_def
            )
            scenarios.append(scenario_result)
            total_gross += Decimal(str(scenario_result.get("gross_loss", 0)))
            total_net += Decimal(str(scenario_result.get("net_loss", 0)))

        # Calculate PML estimates
        pml_100yr = await self._calculate_pml(syndicate_id, 100)
        pml_250yr = await self._calculate_pml(syndicate_id, 250)

        report = RDSReport(
            period=period,
            syndicate_id=syndicate_id,
            scenarios=scenarios,
            total_gross_loss=total_gross,
            total_net_loss=total_net,
            pml_100yr=pml_100yr,
            pml_250yr=pml_250yr,
        )

        if save:
            await self._save_submission(
                syndicate_id=syndicate_id,
                submission_type=SubmissionType.RDS.value,
                period=period,
                data=self._rds_to_dict(report),
            )

        return report

    async def _calculate_scenario(
        self,
        syndicate_id: int,
        scenario_def: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        Calculate exposure for a single RDS scenario.

        In production, this would:
        - Query policies with exposure in the region
        - Apply damage factors based on scenario type
        - Calculate gross and net losses
        """
        # Query exposures by region/peril
        region = scenario_def.get("region", "")
        scenario_type = scenario_def.get("type", "")

        # Get relevant exposure data
        result = await self.db.execute(
            select(ExposureSnapshot)
            .where(ExposureSnapshot.syndicate_id == syndicate_id)
            .where(ExposureSnapshot.geographic_zone == region)
            .order_by(ExposureSnapshot.timestamp.desc())
            .limit(1)
        )
        exposure = result.scalar_one_or_none()

        gross_loss = Decimal("0")
        net_loss = Decimal("0")

        if exposure:
            # Apply scenario-specific damage factor (simplified)
            damage_factor = self._get_damage_factor(scenario_type)
            gross_loss = exposure.gross_exposure * Decimal(str(damage_factor))
            net_loss = exposure.net_exposure * Decimal(str(damage_factor))

        return {
            "scenario_id": scenario_def["id"],
            "scenario_name": scenario_def["name"],
            "scenario_type": scenario_type,
            "region": region,
            "gross_loss": float(gross_loss),
            "net_loss": float(net_loss),
            "policies_affected": 0,  # Would count actual policies
        }

    def _get_damage_factor(self, scenario_type: str) -> float:
        """Get damage factor for scenario type."""
        # Simplified damage factors
        factors = {
            "nat_cat": 0.15,  # 15% of exposed values
            "man_made": 0.10,  # 10% of exposed values
        }
        return factors.get(scenario_type, 0.10)

    async def _calculate_pml(
        self,
        syndicate_id: int,
        return_period: int,
    ) -> Decimal:
        """Calculate Probable Maximum Loss for return period."""
        # Query PML data from exposure snapshots
        result = await self.db.execute(
            select(ExposureSnapshot)
            .where(ExposureSnapshot.syndicate_id == syndicate_id)
            .order_by(ExposureSnapshot.timestamp.desc())
            .limit(1)
        )
        snapshot = result.scalar_one_or_none()

        if snapshot:
            if return_period == 100:
                return snapshot.pml_100yr or Decimal("0")
            elif return_period == 250:
                return snapshot.pml_250yr or Decimal("0")

        return Decimal("0")

    def _rds_to_dict(self, report: RDSReport) -> Dict[str, Any]:
        """Convert RDSReport to dictionary for storage."""
        return {
            "period": report.period,
            "syndicate_id": report.syndicate_id,
            "scenarios": report.scenarios,
            "total_gross_loss": str(report.total_gross_loss),
            "total_net_loss": str(report.total_net_loss),
            "pml_100yr": str(report.pml_100yr),
            "pml_250yr": str(report.pml_250yr),
        }

    # =========================================================================
    # Solvency II / QRT
    # =========================================================================

    async def generate_solvency_qrt(
        self,
        syndicate_id: int,
        period: str,
        templates: Optional[List[str]] = None,
        save: bool = True,
    ) -> Dict[str, Any]:
        """
        Generate Solvency II Quantitative Reporting Templates.

        Args:
            syndicate_id: Syndicate identifier.
            period: Reporting period.
            templates: Specific QRT templates to generate (or all).
            save: Whether to save to database.

        Returns:
            Dictionary of QRT template data.
        """
        # Common QRT templates for Lloyd's syndicates
        default_templates = [
            "S.02.01",  # Balance Sheet
            "S.05.01",  # Premiums, claims and expenses by line of business
            "S.17.01",  # Non-Life Technical Provisions
            "S.19.01",  # Non-life insurance claims
            "S.23.01",  # Own funds
            "S.25.01",  # Solvency Capital Requirement
            "S.28.01",  # Minimum Capital Requirement
        ]

        templates_to_generate = templates or default_templates
        qrt_data = {}

        for template_id in templates_to_generate:
            qrt_data[template_id] = await self._generate_qrt_template(
                syndicate_id, period, template_id
            )

        if save:
            await self._save_submission(
                syndicate_id=syndicate_id,
                submission_type=SubmissionType.QRT.value,
                period=period,
                data=qrt_data,
            )

        return qrt_data

    async def _generate_qrt_template(
        self,
        syndicate_id: int,
        period: str,
        template_id: str,
    ) -> Dict[str, Any]:
        """Generate a single QRT template."""
        # Each template has specific structure
        # This is a simplified implementation
        return {
            "template_id": template_id,
            "period": period,
            "syndicate_id": syndicate_id,
            "status": "generated",
            "data": {},  # Would contain template-specific data
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # =========================================================================
    # Validation
    # =========================================================================

    async def validate_submission(
        self,
        submission_type: str,
        data: Dict[str, Any],
    ) -> List[ValidationResult]:
        """
        Validate a compliance submission against rules.

        Args:
            submission_type: Type of submission (PMDR, RDS, QRT).
            data: Submission data to validate.

        Returns:
            List of validation results.
        """
        results = []

        # Load active rules for this submission type
        rules = await self._load_rules(submission_type)

        for rule in rules:
            result = await self._apply_rule(rule, data)
            if result:
                results.append(result)

        # Add standard validations
        results.extend(self._standard_validations(submission_type, data))

        return results

    async def _load_rules(self, submission_type: str) -> List[ComplianceRule]:
        """Load active compliance rules for submission type."""
        result = await self.db.execute(
            select(ComplianceRule)
            .where(ComplianceRule.regulation == submission_type)
            .where(ComplianceRule.is_active == True)
        )
        return list(result.scalars().all())

    async def _apply_rule(
        self,
        rule: ComplianceRule,
        data: Dict[str, Any],
    ) -> Optional[ValidationResult]:
        """Apply a single validation rule."""
        # Get the field value
        field_path = rule.field_path
        if not field_path:
            return None

        value = self._get_nested_value(data, field_path)

        # Apply validation logic (simplified)
        if rule.validation_logic:
            try:
                # Safe evaluation of simple rules
                if "required" in rule.validation_logic.lower():
                    if value is None or value == "":
                        return ValidationResult(
                            rule_code=rule.rule_code,
                            field=field_path,
                            severity=ValidationSeverity(rule.severity),
                            message=rule.description or f"Field {field_path} is required",
                        )
            except Exception:
                pass

        return None

    def _standard_validations(
        self,
        submission_type: str,
        data: Dict[str, Any],
    ) -> List[ValidationResult]:
        """Apply standard validations for submission type."""
        results = []

        # Check required fields
        required_fields = self._get_required_fields(submission_type)
        for field in required_fields:
            value = self._get_nested_value(data, field)
            if value is None or value == "":
                results.append(ValidationResult(
                    rule_code=f"REQ_{field.upper()}",
                    field=field,
                    severity=ValidationSeverity.ERROR,
                    message=f"Required field '{field}' is missing",
                ))

        # Check numeric fields are non-negative
        numeric_fields = self._get_numeric_fields(submission_type)
        for field in numeric_fields:
            value = self._get_nested_value(data, field)
            if value is not None:
                try:
                    if float(value) < 0:
                        results.append(ValidationResult(
                            rule_code=f"NEG_{field.upper()}",
                            field=field,
                            severity=ValidationSeverity.ERROR,
                            message=f"Field '{field}' cannot be negative",
                            actual_value=value,
                        ))
                except (ValueError, TypeError):
                    results.append(ValidationResult(
                        rule_code=f"NUM_{field.upper()}",
                        field=field,
                        severity=ValidationSeverity.ERROR,
                        message=f"Field '{field}' must be numeric",
                        actual_value=value,
                    ))

        return results

    def _get_required_fields(self, submission_type: str) -> List[str]:
        """Get required fields for submission type."""
        required = {
            "PMDR": ["period", "syndicate_id", "gross_written_premium", "net_written_premium"],
            "RDS": ["period", "syndicate_id", "scenarios"],
            "QRT": ["period", "syndicate_id"],
        }
        return required.get(submission_type, [])

    def _get_numeric_fields(self, submission_type: str) -> List[str]:
        """Get numeric fields for submission type."""
        numeric = {
            "PMDR": [
                "gross_written_premium", "net_written_premium",
                "gross_claims_paid", "net_claims_paid",
            ],
            "RDS": ["total_gross_loss", "total_net_loss", "pml_100yr", "pml_250yr"],
        }
        return numeric.get(submission_type, [])

    def _get_nested_value(self, data: Dict, path: str) -> Any:
        """Get value from nested dictionary using dot notation."""
        keys = path.split(".")
        value = data
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return None
        return value

    # =========================================================================
    # Persistence
    # =========================================================================

    async def _save_submission(
        self,
        syndicate_id: int,
        submission_type: str,
        period: str,
        data: Dict[str, Any],
    ) -> ComplianceSubmission:
        """Save compliance submission to database."""
        # Validate before saving
        validations = await self.validate_submission(submission_type, data)
        errors = [v for v in validations if v.severity == ValidationSeverity.ERROR]
        warnings = [v for v in validations if v.severity == ValidationSeverity.WARNING]

        submission = ComplianceSubmission(
            syndicate_id=syndicate_id,
            submission_type=submission_type,
            period=period,
            data=data,
            validation_errors=[{"code": e.rule_code, "field": e.field, "message": e.message} for e in errors],
            validation_warnings=[{"code": w.rule_code, "field": w.field, "message": w.message} for w in warnings],
            is_valid=len(errors) == 0,
            status="validated" if len(errors) == 0 else "draft",
            validated_at=datetime.now(timezone.utc) if len(errors) == 0 else None,
        )

        self.db.add(submission)
        await self.db.flush()
        return submission

    async def get_submission(
        self,
        submission_id: int,
    ) -> Optional[ComplianceSubmission]:
        """Get a compliance submission by ID."""
        result = await self.db.execute(
            select(ComplianceSubmission)
            .where(ComplianceSubmission.id == submission_id)
        )
        return result.scalar_one_or_none()

    async def list_submissions(
        self,
        syndicate_id: int,
        submission_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[ComplianceSubmission]:
        """List compliance submissions for a syndicate."""
        query = select(ComplianceSubmission).where(
            ComplianceSubmission.syndicate_id == syndicate_id
        )

        if submission_type:
            query = query.where(ComplianceSubmission.submission_type == submission_type)
        if status:
            query = query.where(ComplianceSubmission.status == status)

        query = query.order_by(ComplianceSubmission.created_at.desc()).limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def submit_to_regulator(
        self,
        submission_id: int,
    ) -> Dict[str, Any]:
        """
        Submit a validated submission to Lloyd's/regulator.

        In production, this would integrate with Lloyd's reporting systems.
        """
        submission = await self.get_submission(submission_id)
        if not submission:
            raise ValueError(f"Submission {submission_id} not found")

        if not submission.is_valid:
            raise ValueError("Cannot submit invalid submission")

        # Mark as submitted
        submission.status = "submitted"
        submission.submitted_at = datetime.now(timezone.utc)
        submission.submission_reference = f"IR-{submission.submission_type}-{submission.id}"

        await self.db.flush()

        return {
            "submitted": True,
            "submission_reference": submission.submission_reference,
            "submitted_at": submission.submitted_at.isoformat(),
        }


# Convenience function
async def get_compliance_engine(db: AsyncSession) -> ComplianceAutomationEngine:
    """Get compliance engine instance."""
    return ComplianceAutomationEngine(db)
