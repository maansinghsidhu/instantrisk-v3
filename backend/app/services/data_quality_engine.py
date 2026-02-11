"""
InstantRisk V3 - Data Quality Engine

Validates and scores data quality for insurance submissions.
Addresses Gap 3: Data Quality Crisis in Lloyd's market.

Quality Dimensions:
- Completeness (25%): All required fields present
- Accuracy (25%): Values within expected ranges
- Consistency (20%): No conflicting information
- Timeliness (15%): Data freshness
- Validity (15%): Format compliance
"""

import re
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Any, NamedTuple
from dataclasses import dataclass
from enum import Enum
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lloyds import DataQualityReport


class IssueSeverity(Enum):
    """Severity levels for quality issues."""
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


@dataclass
class QualityIssue:
    """Represents a single quality issue."""
    field: str
    message: str
    severity: IssueSeverity
    suggestion: Optional[str] = None


@dataclass
class Correction:
    """Represents an auto-correction."""
    field: str
    old_value: Any
    new_value: Any
    confidence: float
    reason: str


@dataclass
class QualityReport:
    """Complete quality assessment report."""
    overall_score: float
    completeness_score: float
    accuracy_score: float
    consistency_score: float
    timeliness_score: float
    validity_score: float
    issues: List[QualityIssue]
    corrections: List[Correction]
    suggestions: List[str]
    passed: bool


class DataQualityEngine:
    """
    Engine for assessing and improving data quality.
    """

    # Quality dimension weights
    QUALITY_DIMENSIONS = {
        'completeness': 0.25,
        'accuracy': 0.25,
        'consistency': 0.20,
        'timeliness': 0.15,
        'validity': 0.15,
    }

    # Required fields for Lloyd's submissions
    REQUIRED_FIELDS = {
        'core': [
            'insured_name',
            'broker_name',
            'risk_type',
            'class_of_business',
            'limit_of_liability',
            'premium',
            'inception_date',
            'expiry_date',
        ],
        'lloyds': [
            'umr',
            'unique_market_reference',
            'placing_broker_reference',
            'lead_underwriter',
            'signed_line',
        ],
        'cyber': [
            'data_types',
            'security_controls',
            'revenue',
            'industry_sector',
        ],
        'property': [
            'property_values',
            'location_addresses',
            'construction_type',
        ],
        'marine': [
            'vessel_name',
            'voyage_details',
            'cargo_description',
        ],
    }

    # Field validation rules
    VALIDATION_RULES = {
        'email': r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
        'phone': r'^\+?[\d\s\-\(\)]{8,20}$',
        'umr': r'^B\d{4}[A-Z0-9]{6,10}$',
        'percentage': (0, 100),
        'positive_number': (0, float('inf')),
        'currency_code': r'^[A-Z]{3}$',
        'country_code': r'^[A-Z]{2,3}$',
        'date_format': r'^\d{4}-\d{2}-\d{2}',
    }

    # Common auto-corrections
    AUTO_CORRECTIONS = {
        'currency': {
            'gbp': 'GBP', 'usd': 'USD', 'eur': 'EUR',
            'pounds': 'GBP', 'dollars': 'USD', 'euros': 'EUR',
            '£': 'GBP', '$': 'USD', '€': 'EUR',
        },
        'country': {
            'uk': 'GB', 'united kingdom': 'GB', 'great britain': 'GB',
            'usa': 'US', 'united states': 'US', 'america': 'US',
        },
    }

    def __init__(self, db: Optional[AsyncSession] = None):
        self.db = db

    async def score_submission(
        self,
        data: Dict[str, Any],
        risk_type: Optional[str] = None,
        assessment_id: Optional[str] = None,
    ) -> QualityReport:
        """
        Score a submission's data quality.

        Args:
            data: Submission data dictionary.
            risk_type: Type of risk (cyber, property, marine, etc.).
            assessment_id: Optional assessment ID for persistence.

        Returns:
            QualityReport with scores and issues.
        """
        issues: List[QualityIssue] = []
        corrections: List[Correction] = []
        suggestions: List[str] = []

        # Calculate dimension scores
        completeness_score = self._score_completeness(data, risk_type, issues, suggestions)
        accuracy_score = self._score_accuracy(data, issues, suggestions)
        consistency_score = self._score_consistency(data, issues, suggestions)
        timeliness_score = self._score_timeliness(data, issues, suggestions)
        validity_score = self._score_validity(data, issues, suggestions)

        # Calculate weighted overall score
        overall_score = (
            completeness_score * self.QUALITY_DIMENSIONS['completeness'] +
            accuracy_score * self.QUALITY_DIMENSIONS['accuracy'] +
            consistency_score * self.QUALITY_DIMENSIONS['consistency'] +
            timeliness_score * self.QUALITY_DIMENSIONS['timeliness'] +
            validity_score * self.QUALITY_DIMENSIONS['validity']
        )

        # Determine if passed (threshold: 70%)
        passed = overall_score >= 70 and not any(
            i.severity == IssueSeverity.CRITICAL for i in issues
        )

        report = QualityReport(
            overall_score=round(overall_score, 2),
            completeness_score=round(completeness_score, 2),
            accuracy_score=round(accuracy_score, 2),
            consistency_score=round(consistency_score, 2),
            timeliness_score=round(timeliness_score, 2),
            validity_score=round(validity_score, 2),
            issues=issues,
            corrections=corrections,
            suggestions=suggestions,
            passed=passed,
        )

        # Persist if database session and assessment_id provided
        if self.db and assessment_id:
            await self._save_report(assessment_id, report)

        return report

    def _score_completeness(
        self,
        data: Dict[str, Any],
        risk_type: Optional[str],
        issues: List[QualityIssue],
        suggestions: List[str],
    ) -> float:
        """Score completeness of required fields."""
        # Get required fields based on risk type
        required = set(self.REQUIRED_FIELDS['core'])
        if risk_type and risk_type in self.REQUIRED_FIELDS:
            required.update(self.REQUIRED_FIELDS[risk_type])

        # Check for Lloyd's specific fields
        if data.get('is_lloyds') or data.get('market') == 'lloyds':
            required.update(self.REQUIRED_FIELDS['lloyds'])

        # Count present fields
        present = 0
        for field in required:
            value = self._get_nested_value(data, field)
            if value is not None and value != '' and value != []:
                present += 1
            else:
                issues.append(QualityIssue(
                    field=field,
                    message=f"Required field '{field}' is missing or empty",
                    severity=IssueSeverity.CRITICAL,
                    suggestion=f"Please provide {field.replace('_', ' ')}"
                ))

        if not required:
            return 100.0

        score = (present / len(required)) * 100

        if score < 80:
            suggestions.append(
                f"Submission is missing {len(required) - present} required fields. "
                "Complete all required fields for a valid submission."
            )

        return score

    def _score_accuracy(
        self,
        data: Dict[str, Any],
        issues: List[QualityIssue],
        suggestions: List[str],
    ) -> float:
        """Score accuracy of values (ranges, reasonableness)."""
        checks = []

        # Check premium is reasonable
        premium = self._get_nested_value(data, 'premium') or \
                  self._get_nested_value(data, 'premium_amount')
        if premium is not None:
            try:
                premium_val = float(premium)
                if premium_val < 0:
                    issues.append(QualityIssue(
                        field='premium',
                        message='Premium cannot be negative',
                        severity=IssueSeverity.CRITICAL
                    ))
                    checks.append(False)
                elif premium_val == 0:
                    issues.append(QualityIssue(
                        field='premium',
                        message='Premium is zero - please verify',
                        severity=IssueSeverity.WARNING
                    ))
                    checks.append(True)  # Warning, not failure
                else:
                    checks.append(True)
            except (ValueError, TypeError):
                issues.append(QualityIssue(
                    field='premium',
                    message='Premium is not a valid number',
                    severity=IssueSeverity.CRITICAL
                ))
                checks.append(False)

        # Check limit is reasonable
        limit = self._get_nested_value(data, 'limit_of_liability') or \
                self._get_nested_value(data, 'limit')
        if limit is not None:
            try:
                limit_val = float(limit)
                if limit_val <= 0:
                    issues.append(QualityIssue(
                        field='limit_of_liability',
                        message='Limit of liability must be positive',
                        severity=IssueSeverity.CRITICAL
                    ))
                    checks.append(False)
                else:
                    checks.append(True)
            except (ValueError, TypeError):
                issues.append(QualityIssue(
                    field='limit_of_liability',
                    message='Limit is not a valid number',
                    severity=IssueSeverity.CRITICAL
                ))
                checks.append(False)

        # Check percentage fields
        for field in ['signed_line', 'order_percentage', 'deductible_percentage']:
            value = self._get_nested_value(data, field)
            if value is not None:
                try:
                    pct = float(value)
                    if not (0 <= pct <= 100):
                        issues.append(QualityIssue(
                            field=field,
                            message=f'{field} must be between 0 and 100',
                            severity=IssueSeverity.WARNING
                        ))
                        checks.append(False)
                    else:
                        checks.append(True)
                except (ValueError, TypeError):
                    pass

        # Rate-on-line check (premium / limit)
        if premium and limit:
            try:
                rol = (float(premium) / float(limit)) * 100
                if rol > 50:
                    issues.append(QualityIssue(
                        field='premium',
                        message=f'Rate on line ({rol:.2f}%) seems unusually high',
                        severity=IssueSeverity.WARNING
                    ))
                elif rol < 0.01:
                    issues.append(QualityIssue(
                        field='premium',
                        message=f'Rate on line ({rol:.4f}%) seems unusually low',
                        severity=IssueSeverity.WARNING
                    ))
                checks.append(True)
            except (ValueError, TypeError, ZeroDivisionError):
                pass

        if not checks:
            return 100.0  # No checks applicable

        return (sum(1 for c in checks if c) / len(checks)) * 100

    def _score_consistency(
        self,
        data: Dict[str, Any],
        issues: List[QualityIssue],
        suggestions: List[str],
    ) -> float:
        """Score internal consistency of data."""
        checks = []

        # Check inception < expiry
        inception = self._parse_date(self._get_nested_value(data, 'inception_date'))
        expiry = self._parse_date(self._get_nested_value(data, 'expiry_date'))

        if inception and expiry:
            if inception >= expiry:
                issues.append(QualityIssue(
                    field='inception_date',
                    message='Inception date must be before expiry date',
                    severity=IssueSeverity.CRITICAL
                ))
                checks.append(False)
            else:
                checks.append(True)

            # Check policy period is reasonable (typically 1-3 years)
            days = (expiry - inception).days
            if days > 1095:  # > 3 years
                issues.append(QualityIssue(
                    field='expiry_date',
                    message=f'Policy period of {days} days (>{days//365} years) is unusually long',
                    severity=IssueSeverity.WARNING
                ))
            elif days < 30:
                issues.append(QualityIssue(
                    field='expiry_date',
                    message=f'Policy period of {days} days is unusually short',
                    severity=IssueSeverity.WARNING
                ))

        # Check aggregate > limit
        aggregate = self._get_nested_value(data, 'aggregate_limit')
        limit = self._get_nested_value(data, 'limit_of_liability')
        if aggregate and limit:
            try:
                if float(aggregate) < float(limit):
                    issues.append(QualityIssue(
                        field='aggregate_limit',
                        message='Aggregate limit should be >= per occurrence limit',
                        severity=IssueSeverity.WARNING
                    ))
                    checks.append(False)
                else:
                    checks.append(True)
            except (ValueError, TypeError):
                pass

        # Check currency consistency
        currencies = set()
        for field in ['premium_currency', 'limit_currency', 'currency']:
            val = self._get_nested_value(data, field)
            if val:
                currencies.add(str(val).upper())

        if len(currencies) > 1:
            issues.append(QualityIssue(
                field='currency',
                message=f'Multiple currencies detected: {currencies}. Verify consistency.',
                severity=IssueSeverity.WARNING
            ))
            checks.append(False)
        elif currencies:
            checks.append(True)

        if not checks:
            return 100.0

        return (sum(1 for c in checks if c) / len(checks)) * 100

    def _score_timeliness(
        self,
        data: Dict[str, Any],
        issues: List[QualityIssue],
        suggestions: List[str],
    ) -> float:
        """Score data timeliness/freshness."""
        checks = []
        now = datetime.now(timezone.utc)

        # Check inception date isn't too old
        inception = self._parse_date(self._get_nested_value(data, 'inception_date'))
        if inception:
            if inception < now - timedelta(days=365):
                issues.append(QualityIssue(
                    field='inception_date',
                    message='Inception date is more than 1 year in the past',
                    severity=IssueSeverity.WARNING
                ))
                checks.append(False)
            elif inception < now - timedelta(days=90):
                issues.append(QualityIssue(
                    field='inception_date',
                    message='Inception date is more than 90 days in the past',
                    severity=IssueSeverity.INFO
                ))
                checks.append(True)
            else:
                checks.append(True)

        # Check expiry isn't already passed
        expiry = self._parse_date(self._get_nested_value(data, 'expiry_date'))
        if expiry:
            if expiry < now:
                issues.append(QualityIssue(
                    field='expiry_date',
                    message='Policy has already expired',
                    severity=IssueSeverity.CRITICAL
                ))
                checks.append(False)
            else:
                checks.append(True)

        # Check data timestamp if available
        data_date = self._parse_date(
            self._get_nested_value(data, 'data_date') or
            self._get_nested_value(data, 'submission_date')
        )
        if data_date:
            if data_date < now - timedelta(days=30):
                issues.append(QualityIssue(
                    field='data_date',
                    message='Data is more than 30 days old - please verify current accuracy',
                    severity=IssueSeverity.WARNING
                ))
                checks.append(False)
            else:
                checks.append(True)

        if not checks:
            return 100.0

        return (sum(1 for c in checks if c) / len(checks)) * 100

    def _score_validity(
        self,
        data: Dict[str, Any],
        issues: List[QualityIssue],
        suggestions: List[str],
    ) -> float:
        """Score format validity of fields."""
        checks = []

        # Validate email fields
        for field in ['contact_email', 'broker_email', 'underwriter_email']:
            value = self._get_nested_value(data, field)
            if value:
                if not re.match(self.VALIDATION_RULES['email'], str(value)):
                    issues.append(QualityIssue(
                        field=field,
                        message=f'Invalid email format: {value}',
                        severity=IssueSeverity.WARNING
                    ))
                    checks.append(False)
                else:
                    checks.append(True)

        # Validate UMR format
        umr = self._get_nested_value(data, 'umr') or \
              self._get_nested_value(data, 'unique_market_reference')
        if umr:
            if not re.match(self.VALIDATION_RULES['umr'], str(umr)):
                issues.append(QualityIssue(
                    field='umr',
                    message=f'Invalid UMR format: {umr}. Expected format: B0999XXXXXX',
                    severity=IssueSeverity.CRITICAL
                ))
                checks.append(False)
            else:
                checks.append(True)

        # Validate currency codes
        for field in ['currency', 'premium_currency', 'limit_currency']:
            value = self._get_nested_value(data, field)
            if value:
                if not re.match(self.VALIDATION_RULES['currency_code'], str(value).upper()):
                    issues.append(QualityIssue(
                        field=field,
                        message=f'Invalid currency code: {value}. Use ISO 4217 (e.g., GBP, USD)',
                        severity=IssueSeverity.WARNING
                    ))
                    checks.append(False)
                else:
                    checks.append(True)

        # Validate date formats
        for field in ['inception_date', 'expiry_date', 'quote_date']:
            value = self._get_nested_value(data, field)
            if value and isinstance(value, str):
                if not re.match(self.VALIDATION_RULES['date_format'], value):
                    issues.append(QualityIssue(
                        field=field,
                        message=f'Invalid date format: {value}. Use YYYY-MM-DD',
                        severity=IssueSeverity.WARNING
                    ))
                    checks.append(False)
                else:
                    checks.append(True)

        if not checks:
            return 100.0

        return (sum(1 for c in checks if c) / len(checks)) * 100

    async def auto_correct(
        self,
        data: Dict[str, Any],
        confidence_threshold: float = 0.9,
    ) -> tuple[Dict[str, Any], List[Correction]]:
        """
        Auto-correct low-confidence fields with high-confidence AI.

        Args:
            data: Original data dictionary.
            confidence_threshold: Minimum confidence for auto-correction.

        Returns:
            Tuple of (corrected_data, list of corrections made).
        """
        corrected = dict(data)
        corrections = []

        # Currency normalization
        for field in ['currency', 'premium_currency', 'limit_currency']:
            value = self._get_nested_value(corrected, field)
            if value and str(value).lower() in self.AUTO_CORRECTIONS['currency']:
                new_value = self.AUTO_CORRECTIONS['currency'][str(value).lower()]
                self._set_nested_value(corrected, field, new_value)
                corrections.append(Correction(
                    field=field,
                    old_value=value,
                    new_value=new_value,
                    confidence=0.99,
                    reason='Currency code normalization'
                ))

        # Country code normalization
        for field in ['country', 'territory', 'insured_country']:
            value = self._get_nested_value(corrected, field)
            if value and str(value).lower() in self.AUTO_CORRECTIONS['country']:
                new_value = self.AUTO_CORRECTIONS['country'][str(value).lower()]
                self._set_nested_value(corrected, field, new_value)
                corrections.append(Correction(
                    field=field,
                    old_value=value,
                    new_value=new_value,
                    confidence=0.95,
                    reason='Country code normalization'
                ))

        # Trim whitespace from string fields
        for key, value in corrected.items():
            if isinstance(value, str) and value != value.strip():
                corrected[key] = value.strip()
                corrections.append(Correction(
                    field=key,
                    old_value=value,
                    new_value=value.strip(),
                    confidence=1.0,
                    reason='Whitespace trimming'
                ))

        # Uppercase currency/country codes
        for field in ['currency', 'country']:
            value = self._get_nested_value(corrected, field)
            if value and isinstance(value, str) and value != value.upper():
                new_value = value.upper()
                self._set_nested_value(corrected, field, new_value)
                corrections.append(Correction(
                    field=field,
                    old_value=value,
                    new_value=new_value,
                    confidence=0.99,
                    reason='Case normalization'
                ))

        return corrected, corrections

    async def suggest_improvements(self, data: Dict[str, Any]) -> List[str]:
        """
        Return prioritized list of data improvements.

        Args:
            data: Submission data.

        Returns:
            List of improvement suggestions.
        """
        report = await self.score_submission(data)

        suggestions = []

        # Priority 1: Critical issues
        critical_issues = [i for i in report.issues if i.severity == IssueSeverity.CRITICAL]
        if critical_issues:
            suggestions.append(
                f"CRITICAL: {len(critical_issues)} critical issues must be resolved: " +
                ", ".join(i.field for i in critical_issues[:3])
            )

        # Priority 2: Low dimension scores
        if report.completeness_score < 80:
            suggestions.append(
                f"Completeness ({report.completeness_score:.0f}%): Add missing required fields"
            )
        if report.accuracy_score < 80:
            suggestions.append(
                f"Accuracy ({report.accuracy_score:.0f}%): Verify numerical values are correct"
            )
        if report.consistency_score < 80:
            suggestions.append(
                f"Consistency ({report.consistency_score:.0f}%): Check for conflicting data"
            )
        if report.validity_score < 80:
            suggestions.append(
                f"Validity ({report.validity_score:.0f}%): Fix format issues in fields"
            )

        # Priority 3: Warning issues
        warnings = [i for i in report.issues if i.severity == IssueSeverity.WARNING]
        if warnings:
            suggestions.append(
                f"WARNINGS: {len(warnings)} fields need review: " +
                ", ".join(i.field for i in warnings[:3])
            )

        return suggestions

    def _get_nested_value(self, data: Dict, path: str) -> Any:
        """Get value from nested dict using dot notation."""
        keys = path.split('.')
        value = data
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return None
        return value

    def _set_nested_value(self, data: Dict, path: str, value: Any):
        """Set value in nested dict using dot notation."""
        keys = path.split('.')
        obj = data
        for key in keys[:-1]:
            obj = obj.setdefault(key, {})
        obj[keys[-1]] = value

    def _parse_date(self, value: Any) -> Optional[datetime]:
        """Parse date from various formats."""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%Y-%m-%dT%H:%M:%S']:
                try:
                    return datetime.strptime(value[:19], fmt).replace(tzinfo=timezone.utc)
                except ValueError:
                    continue
        return None

    async def _save_report(self, assessment_id: str, report: QualityReport):
        """Save quality report to database."""
        db_report = DataQualityReport(
            assessment_id=assessment_id,
            overall_score=report.overall_score,
            completeness_score=report.completeness_score,
            accuracy_score=report.accuracy_score,
            consistency_score=report.consistency_score,
            timeliness_score=report.timeliness_score,
            validity_score=report.validity_score,
            issues={i.field: i.message for i in report.issues},
            issue_count=len(report.issues),
            critical_issues=sum(1 for i in report.issues if i.severity == IssueSeverity.CRITICAL),
            corrections={c.field: {'old': c.old_value, 'new': c.new_value, 'confidence': c.confidence}
                        for c in report.corrections},
            auto_corrected_count=len(report.corrections),
            suggestions=report.suggestions,
        )
        self.db.add(db_report)
        await self.db.flush()


# Convenience function
async def get_data_quality_engine(db: AsyncSession) -> DataQualityEngine:
    """Get data quality engine instance."""
    return DataQualityEngine(db)
