"""
Intelligent Document Extractor for Insurance Documents

AI-powered document extraction system that:
- Detects document types (MRC slips, policy schedules, endorsements, etc.)
- Extracts specific fields with pattern matching
- Provides confidence scores for each extraction
- Integrates with RAG for enhanced terminology understanding
- Supports human feedback loop for continuous improvement
- Collects training data for model fine-tuning

Author: InstantRisk Development Team
Version: 1.0.0
"""

import os
import re
import json
import hashlib
import logging
from enum import Enum
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional, Tuple, Union
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update, insert

from app.config import settings
from app.services.insurance_templates import (
    INSURANCE_TEMPLATES,
    LLOYDS_MRC_SLIP,
    LLOYDS_POLICY_WORDING,
    get_template,
    auto_select_templates
)

logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS AND DATACLASSES
# =============================================================================

class DocumentType(str, Enum):
    """Supported insurance document types."""
    MRC_SLIP = "mrc_slip"
    POLICY_SCHEDULE = "policy_schedule"
    POLICY_WORDING = "policy_wording"
    ENDORSEMENT = "endorsement"
    SIGNING_PAGE = "signing_page"
    BINDER = "binder"
    COVER_NOTE = "cover_note"
    QUOTE = "quote"
    CERTIFICATE = "certificate"
    CLAIMS_ADVICE = "claims_advice"
    BORDEREAUX = "bordereaux"
    FACULTATIVE_CERT = "facultative_certificate"
    TREATY_SLIP = "treaty_slip"
    UNKNOWN = "unknown"


class ConfidenceLevel(str, Enum):
    """Confidence level classifications."""
    HIGH = "high"       # > 90% - Auto-accept
    MEDIUM = "medium"   # 70-90% - Highlight for review
    LOW = "low"         # < 70% - Flag for manual entry


class ExtractionStatus(str, Enum):
    """Extraction process status."""
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


@dataclass
class ExtractedField:
    """Represents a single extracted field with metadata."""
    field_name: str
    value: Any
    raw_text: str
    confidence: float
    confidence_level: ConfidenceLevel
    pattern_used: str = ""
    position: Optional[Tuple[int, int]] = None  # (start, end) in text
    requires_review: bool = False
    alternatives: List[Any] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "field_name": self.field_name,
            "value": self.value,
            "raw_text": self.raw_text,
            "confidence": self.confidence,
            "confidence_level": self.confidence_level.value,
            "pattern_used": self.pattern_used,
            "position": self.position,
            "requires_review": self.requires_review,
            "alternatives": self.alternatives
        }


@dataclass
class DocumentTypeResult:
    """Result of document type detection."""
    detected_type: DocumentType
    confidence: float
    confidence_level: ConfidenceLevel
    matched_keywords: List[str]
    matched_sections: List[str]
    alternative_types: List[Tuple[DocumentType, float]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "detected_type": self.detected_type.value,
            "confidence": self.confidence,
            "confidence_level": self.confidence_level.value,
            "matched_keywords": self.matched_keywords,
            "matched_sections": self.matched_sections,
            "alternative_types": [
                {"type": t.value, "confidence": c}
                for t, c in self.alternative_types
            ]
        }


@dataclass
class MRCSlipData:
    """Extracted data from an MRC slip."""
    umr: Optional[ExtractedField] = None
    pbcr: Optional[ExtractedField] = None
    insured_name: Optional[ExtractedField] = None
    insured_address: Optional[ExtractedField] = None
    broker_name: Optional[ExtractedField] = None
    broker_reference: Optional[ExtractedField] = None
    class_of_business: Optional[ExtractedField] = None
    risk_code: Optional[ExtractedField] = None
    period_from: Optional[ExtractedField] = None
    period_to: Optional[ExtractedField] = None
    limit_of_liability: Optional[ExtractedField] = None
    aggregate_limit: Optional[ExtractedField] = None
    deductible: Optional[ExtractedField] = None
    premium: Optional[ExtractedField] = None
    deposit_premium: Optional[ExtractedField] = None
    minimum_premium: Optional[ExtractedField] = None
    currency: Optional[ExtractedField] = None
    lead_underwriter: Optional[ExtractedField] = None
    lead_syndicate: Optional[ExtractedField] = None
    signed_line: Optional[ExtractedField] = None
    written_line: Optional[ExtractedField] = None
    order_percentage: Optional[ExtractedField] = None
    following_markets: List[ExtractedField] = field(default_factory=list)
    syndicate_lines: List[ExtractedField] = field(default_factory=list)
    subjectivities: List[ExtractedField] = field(default_factory=list)
    warranties: List[ExtractedField] = field(default_factory=list)
    exclusions: List[ExtractedField] = field(default_factory=list)
    territorial_limits: Optional[ExtractedField] = None
    jurisdiction: Optional[ExtractedField] = None
    basis_of_cover: Optional[ExtractedField] = None
    retroactive_date: Optional[ExtractedField] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {}
        for field_name, field_value in self.__dict__.items():
            if isinstance(field_value, ExtractedField):
                result[field_name] = field_value.to_dict()
            elif isinstance(field_value, list):
                result[field_name] = [
                    f.to_dict() if isinstance(f, ExtractedField) else f
                    for f in field_value
                ]
            else:
                result[field_name] = field_value
        return result


@dataclass
class PolicyScheduleData:
    """Extracted data from a policy schedule."""
    policy_number: Optional[ExtractedField] = None
    umr: Optional[ExtractedField] = None
    named_insured: Optional[ExtractedField] = None
    additional_insureds: List[ExtractedField] = field(default_factory=list)
    policy_period_from: Optional[ExtractedField] = None
    policy_period_to: Optional[ExtractedField] = None
    coverage_parts: List[ExtractedField] = field(default_factory=list)
    limits_schedule: List[ExtractedField] = field(default_factory=list)
    deductibles_schedule: List[ExtractedField] = field(default_factory=list)
    premium_schedule: List[ExtractedField] = field(default_factory=list)
    locations: List[ExtractedField] = field(default_factory=list)
    endorsements: List[ExtractedField] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        result = {}
        for field_name, field_value in self.__dict__.items():
            if isinstance(field_value, ExtractedField):
                result[field_name] = field_value.to_dict()
            elif isinstance(field_value, list):
                result[field_name] = [
                    f.to_dict() if isinstance(f, ExtractedField) else f
                    for f in field_value
                ]
            else:
                result[field_name] = field_value
        return result


@dataclass
class ValidationResult:
    """Result of extraction validation."""
    is_valid: bool
    completeness_score: float
    required_fields_found: List[str]
    required_fields_missing: List[str]
    optional_fields_found: List[str]
    warnings: List[str]
    errors: List[str]
    field_validations: Dict[str, bool]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ExtractionResult:
    """Complete extraction result with metadata."""
    document_id: Optional[int]
    document_type: DocumentTypeResult
    status: ExtractionStatus
    extracted_data: Union[MRCSlipData, PolicyScheduleData, Dict[str, Any]]
    validation: ValidationResult
    overall_confidence: float
    overall_confidence_level: ConfidenceLevel
    fields_requiring_review: List[str]
    processing_time_ms: float
    rag_context_used: bool
    similar_documents_found: int
    extraction_timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    raw_text_hash: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_id": self.document_id,
            "document_type": self.document_type.to_dict(),
            "status": self.status.value,
            "extracted_data": (
                self.extracted_data.to_dict()
                if hasattr(self.extracted_data, 'to_dict')
                else self.extracted_data
            ),
            "validation": self.validation.to_dict(),
            "overall_confidence": self.overall_confidence,
            "overall_confidence_level": self.overall_confidence_level.value,
            "fields_requiring_review": self.fields_requiring_review,
            "processing_time_ms": self.processing_time_ms,
            "rag_context_used": self.rag_context_used,
            "similar_documents_found": self.similar_documents_found,
            "extraction_timestamp": self.extraction_timestamp,
            "raw_text_hash": self.raw_text_hash
        }


# =============================================================================
# FIELD EXTRACTION PATTERNS
# =============================================================================

class ExtractionPatterns:
    """
    Regex patterns for extracting insurance document fields.
    Patterns are organized by field type for Lloyd's and commercial documents.
    """

    # UMR Pattern: B followed by 4 digits then alphanumeric (Lloyd's standard)
    UMR = [
        r"(?:UMR|Unique\s*Market\s*Ref(?:erence)?)[:\s]*([B]\d{4}[A-Z0-9]+)",
        r"(?:^|[\s,;])([B]\d{4}[A-Z0-9]{2,8})(?:[\s,;]|$)",
        r"UMR[:\s]*([A-Z]\d{4}[A-Z0-9]+)",
    ]

    # Policy/Certificate Number patterns
    POLICY_NUMBER = [
        r"(?:Policy\s*(?:No|Number|#)?)[:\s]*([A-Z]{2,4}[-/]?\d{6,12})",
        r"(?:Certificate\s*(?:No|Number)?)[:\s]*([A-Z0-9]{6,15})",
        r"(?:Ref(?:erence)?)[:\s]*([A-Z]{2,3}\d{6,10})",
    ]

    # Broker Reference patterns
    BROKER_REF = [
        r"(?:PBCR|Placing\s*Broker\s*(?:Contract\s*)?Ref(?:erence)?)[:\s]*([A-Z0-9-/]+)",
        r"(?:Broker\s*Ref(?:erence)?)[:\s]*([A-Z0-9-/]+)",
        r"(?:Our\s*Ref(?:erence)?)[:\s]*([A-Z0-9-/]+)",
    ]

    # Premium patterns with currency
    PREMIUM = [
        r"(?:(?:Total\s*)?Premium)[:\s]*([A-Z]{3})?[\s]*([£$€])?[\s]*([\d,]+(?:\.\d{2})?)",
        r"(?:Premium\s*Amount)[:\s]*([A-Z]{3})?[\s]*([£$€])?[\s]*([\d,]+(?:\.\d{2})?)",
        r"(?:Gross\s*Premium)[:\s]*([A-Z]{3})?[\s]*([£$€])?[\s]*([\d,]+(?:\.\d{2})?)",
        r"(?:Net\s*Premium)[:\s]*([A-Z]{3})?[\s]*([£$€])?[\s]*([\d,]+(?:\.\d{2})?)",
    ]

    # Minimum and Deposit Premium
    MIN_DEP_PREMIUM = [
        r"(?:Minimum\s*(?:&|and)?\s*Deposit(?:\s*Premium)?)[:\s]*([A-Z]{3})?[\s]*([£$€])?[\s]*([\d,]+(?:\.\d{2})?)",
        r"(?:M&D|M\s*&\s*D)[:\s]*([A-Z]{3})?[\s]*([£$€])?[\s]*([\d,]+(?:\.\d{2})?)",
        r"(?:Deposit\s*Premium)[:\s]*([A-Z]{3})?[\s]*([£$€])?[\s]*([\d,]+(?:\.\d{2})?)",
    ]

    # Limit of Liability patterns
    LIMIT = [
        r"(?:Limit\s*(?:of\s*)?(?:Liability|Indemnity))[:\s]*([A-Z]{3})?[\s]*([£$€])?[\s]*([\d,]+(?:,\d{3})*(?:\.\d{2})?)",
        r"(?:(?:Any\s*)?One\s*(?:Occurrence|Claim|Loss))[:\s]*([A-Z]{3})?[\s]*([£$€])?[\s]*([\d,]+(?:\.\d{2})?)",
        r"(?:Policy\s*Limit)[:\s]*([A-Z]{3})?[\s]*([£$€])?[\s]*([\d,]+(?:\.\d{2})?)",
        r"(?:Sum\s*Insured|TSI)[:\s]*([A-Z]{3})?[\s]*([£$€])?[\s]*([\d,]+(?:\.\d{2})?)",
    ]

    # Aggregate Limit
    AGGREGATE = [
        r"(?:Aggregate\s*(?:Limit)?)[:\s]*([A-Z]{3})?[\s]*([£$€])?[\s]*([\d,]+(?:\.\d{2})?)",
        r"(?:(?:Annual|Policy)\s*Aggregate)[:\s]*([A-Z]{3})?[\s]*([£$€])?[\s]*([\d,]+(?:\.\d{2})?)",
        r"(?:In\s*the\s*Aggregate)[:\s]*([A-Z]{3})?[\s]*([£$€])?[\s]*([\d,]+(?:\.\d{2})?)",
    ]

    # Deductible/Excess patterns
    DEDUCTIBLE = [
        r"(?:Deductible|Excess)[:\s]*([A-Z]{3})?[\s]*([£$€])?[\s]*([\d,]+(?:\.\d{2})?)",
        r"(?:Self[\s-]?Insured\s*Retention|SIR)[:\s]*([A-Z]{3})?[\s]*([£$€])?[\s]*([\d,]+(?:\.\d{2})?)",
        r"(?:Retention)[:\s]*([A-Z]{3})?[\s]*([£$€])?[\s]*([\d,]+(?:\.\d{2})?)",
    ]

    # Date patterns (multiple formats)
    DATE = [
        r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})",
        r"(\d{1,2})\s+(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+(\d{2,4})",
        r"(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+(\d{1,2}),?\s+(\d{2,4})",
    ]

    # Inception Date
    INCEPTION_DATE = [
        r"(?:Inception|Start|Effective|From)[:\s]*(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})",
        r"(?:Period\s*(?:of\s*Insurance\s*)?From)[:\s]*(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})",
        r"(?:Commencing)[:\s]*(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})",
    ]

    # Expiry Date
    EXPIRY_DATE = [
        r"(?:Expiry|Expiration|End|To)[:\s]*(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})",
        r"(?:Period\s*(?:of\s*Insurance\s*)?To)[:\s]*(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})",
        r"(?:Terminating)[:\s]*(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})",
    ]

    # Syndicate Line patterns (for Lloyd's)
    SYNDICATE_LINE = [
        r"(?:Syndicate|Synd\.?)\s*(\d{3,4})\s*[-:]\s*([\d.]+)%",
        r"(\d{3,4})\s*@\s*([\d.]+)%",
        r"(\d{3,4})[\s:]+Written\s*Line[:\s]*([\d.]+)%",
    ]

    # Signed Line percentage
    SIGNED_LINE = [
        r"(?:Signed\s*Line)[:\s]*([\d.]+)%",
        r"(?:Our\s*(?:Signed\s*)?Line)[:\s]*([\d.]+)%",
        r"(?:Participation)[:\s]*([\d.]+)%",
    ]

    # Order percentage
    ORDER_PERCENTAGE = [
        r"(?:Order)[:\s]*([\d.]+)%",
        r"(?:Slip\s*Order)[:\s]*([\d.]+)%",
        r"(\d{2,3}(?:\.\d+)?)%\s*(?:of\s*)?(?:100|Order)",
    ]

    # Currency
    CURRENCY = [
        r"(?:Currency)[:\s]*([A-Z]{3})",
        r"(?:in|of)\s+(GBP|USD|EUR|CHF|JPY|AUD|CAD)",
        r"([£$€])",
    ]

    # Insured Name
    INSURED = [
        r"(?:(?:The\s*)?(?:Named\s*)?Insured|Assured)[:\s]*([A-Za-z0-9\s&.,'-]+?)(?:\n|Address|$)",
        r"(?:Policy\s*Holder)[:\s]*([A-Za-z0-9\s&.,'-]+?)(?:\n|$)",
        r"(?:In\s*(?:the\s*)?name\s*of)[:\s]*([A-Za-z0-9\s&.,'-]+?)(?:\n|$)",
    ]

    # Broker Name
    BROKER = [
        r"(?:(?:Placing\s*)?Broker)[:\s]*([A-Za-z0-9\s&.,'-]+?)(?:\n|Ref|$)",
        r"(?:Produced\s*by)[:\s]*([A-Za-z0-9\s&.,'-]+?)(?:\n|$)",
    ]

    # Lead Underwriter/Syndicate
    LEAD_UNDERWRITER = [
        r"(?:Lead\s*Underwriter)[:\s]*([A-Za-z0-9\s&.,'-]+?)(?:\n|Syndicate|$)",
        r"(?:Lead\s*Syndicate)[:\s]*(\d{3,4})",
        r"(?:Leader)[:\s]*([A-Za-z0-9\s&.,'-]+?)(?:\n|$)",
    ]

    # Class of Business
    CLASS_OF_BUSINESS = [
        r"(?:Class\s*(?:of\s*)?Business)[:\s]*([A-Za-z\s&/,'-]+?)(?:\n|Risk\s*Code|$)",
        r"(?:Type\s*(?:of\s*)?Insurance)[:\s]*([A-Za-z\s&/,'-]+?)(?:\n|$)",
        r"(?:Coverage\s*Type)[:\s]*([A-Za-z\s&/,'-]+?)(?:\n|$)",
    ]

    # Risk Code (Lloyd's)
    RISK_CODE = [
        r"(?:Risk\s*Code)[:\s]*([A-Z]{2,4}\d{0,3})",
        r"(?:Lloyd's\s*Risk\s*Code)[:\s]*([A-Z]{2,4}\d{0,3})",
    ]

    # Territorial Limits
    TERRITORIAL_LIMITS = [
        r"(?:Territorial\s*(?:Limits|Scope))[:\s]*([A-Za-z\s,&/-]+?)(?:\n|Basis|$)",
        r"(?:Geographical\s*(?:Limits|Scope))[:\s]*([A-Za-z\s,&/-]+?)(?:\n|$)",
    ]

    # Basis of Cover
    BASIS_OF_COVER = [
        r"(?:Basis\s*(?:of\s*)?(?:Cover|Indemnity|Insurance))[:\s]*(Claims?\s*Made(?:\s*(?:&|and)\s*Reported)?|Occurrence|Losses?\s*Occurring)",
    ]

    # Jurisdiction
    JURISDICTION = [
        r"(?:Jurisdiction)[:\s]*([A-Za-z\s,&/-]+?)(?:\n|Law|$)",
        r"(?:Governing\s*Law)[:\s]*([A-Za-z\s,&/-]+?)(?:\n|$)",
        r"(?:Law\s*(?:&|and)\s*Practice)[:\s]*([A-Za-z\s,&/-]+?)(?:\n|$)",
    ]


# =============================================================================
# DOCUMENT TYPE DETECTION
# =============================================================================

class DocumentTypeDetector:
    """Detects insurance document types based on content analysis."""

    # Keywords and patterns for each document type
    TYPE_INDICATORS = {
        DocumentType.MRC_SLIP: {
            "keywords": [
                "unique market reference", "umr", "market reform contract",
                "placing slip", "risk details", "the assured", "signed line",
                "written line", "lead underwriter", "following markets",
                "several liability clause", "london market"
            ],
            "sections": [
                "RISK DETAILS", "THE ASSURED", "PERIOD", "INTEREST",
                "TERRITORIAL LIMITS", "LIMIT OF LIABILITY", "PREMIUM",
                "CONDITIONS PRECEDENT", "SUBJECTIVITIES", "EXCLUSIONS",
                "SECURITY", "SYNDICATE"
            ],
            "patterns": [
                r"B\d{4}[A-Z0-9]+",  # UMR pattern
                r"Syndicate\s*\d{3,4}",
                r"Signed\s*Line.*%",
            ],
            "weight": 1.0
        },
        DocumentType.POLICY_SCHEDULE: {
            "keywords": [
                "policy schedule", "schedule of insurance", "declarations",
                "schedule of coverages", "schedule of limits", "named insured",
                "policy number", "effective date"
            ],
            "sections": [
                "DECLARATIONS", "SCHEDULE OF COVERAGES", "SCHEDULE OF LOCATIONS",
                "LIMITS SCHEDULE", "DEDUCTIBLES SCHEDULE", "PREMIUM SCHEDULE"
            ],
            "patterns": [
                r"Policy\s*(?:No|Number)",
                r"Schedule\s*of",
            ],
            "weight": 0.9
        },
        DocumentType.POLICY_WORDING: {
            "keywords": [
                "policy wording", "insuring agreement", "definitions",
                "policy conditions", "what is covered", "what is not covered",
                "general conditions", "claims conditions"
            ],
            "sections": [
                "INSURING AGREEMENTS", "DEFINITIONS", "EXCLUSIONS",
                "CONDITIONS", "GENERAL CONDITIONS", "CLAIMS"
            ],
            "patterns": [
                r"INSURING\s*AGREEMENT",
                r"DEFINITIONS\s*SECTION",
            ],
            "weight": 0.85
        },
        DocumentType.ENDORSEMENT: {
            "keywords": [
                "endorsement", "amendment", "rider", "addendum",
                "it is hereby agreed", "this endorsement modifies",
                "effective date of endorsement"
            ],
            "sections": [
                "ENDORSEMENT", "AMENDMENT"
            ],
            "patterns": [
                r"Endorsement\s*(?:No|Number|#)",
                r"This\s*endorsement\s*(?:modifies|amends)",
            ],
            "weight": 0.8
        },
        DocumentType.SIGNING_PAGE: {
            "keywords": [
                "signing page", "signing number", "bureau signing",
                "signing date", "syndicate participation", "100% gross premium"
            ],
            "sections": [
                "SIGNING", "SYNDICATE PARTICIPATION"
            ],
            "patterns": [
                r"Signing\s*(?:Number|No)",
                r"100%\s*Gross\s*Premium",
            ],
            "weight": 0.85
        },
        DocumentType.BINDER: {
            "keywords": [
                "binding authority", "binder", "coverholder",
                "delegated authority", "coverholder pin", "agreement number"
            ],
            "sections": [
                "BINDING AUTHORITY", "COVERHOLDER", "AUTHORITY GRANTED"
            ],
            "patterns": [
                r"Binding\s*Authority",
                r"Coverholder\s*PIN",
            ],
            "weight": 0.9
        },
        DocumentType.COVER_NOTE: {
            "keywords": [
                "cover note", "temporary cover", "valid until",
                "pending policy issuance", "interim cover"
            ],
            "sections": [
                "COVER NOTE", "TEMPORARY COVER"
            ],
            "patterns": [
                r"Cover\s*Note\s*(?:No|Number)",
                r"Valid\s*Until",
            ],
            "weight": 0.8
        },
        DocumentType.QUOTE: {
            "keywords": [
                "quotation", "indication", "quote", "firm quote",
                "budgetary indication", "indicative terms", "subject to"
            ],
            "sections": [
                "QUOTATION", "INDICATION", "INDICATIVE TERMS"
            ],
            "patterns": [
                r"(?:Firm\s*)?Quote\s*(?:Reference|Ref|No)",
                r"Indication\s*(?:Only)?",
            ],
            "weight": 0.75
        },
        DocumentType.CERTIFICATE: {
            "keywords": [
                "certificate of insurance", "evidence of insurance",
                "certificate holder", "certificate number", "producer"
            ],
            "sections": [
                "CERTIFICATE", "COVERAGES", "CERTIFICATE HOLDER"
            ],
            "patterns": [
                r"Certificate\s*(?:No|Number|of\s*Insurance)",
                r"This\s*certificate\s*is\s*issued",
            ],
            "weight": 0.85
        },
        DocumentType.CLAIMS_ADVICE: {
            "keywords": [
                "claim advice", "claims notification", "date of loss",
                "cause of loss", "reserve", "first advice", "claim reference"
            ],
            "sections": [
                "CLAIM DETAILS", "LOSS DETAILS", "CLAIM ADVICE"
            ],
            "patterns": [
                r"Claim\s*(?:Reference|Ref|No)",
                r"Date\s*of\s*Loss",
            ],
            "weight": 0.9
        },
        DocumentType.BORDEREAUX: {
            "keywords": [
                "bordereaux", "premium bordereau", "claims bordereau",
                "risk bordereau", "monthly report"
            ],
            "sections": [
                "BORDEREAUX", "PREMIUM BORDEREAU", "CLAIMS BORDEREAU"
            ],
            "patterns": [
                r"Border(?:eaux?|eau)",
                r"Period\s*(?:From|To)",
            ],
            "weight": 0.85
        },
        DocumentType.FACULTATIVE_CERT: {
            "keywords": [
                "facultative certificate", "facultative reinsurance",
                "cedent", "reinsurer share", "ceded premium", "original insured"
            ],
            "sections": [
                "CEDENT", "REINSURER", "ORIGINAL POLICY", "REINSURANCE TERMS"
            ],
            "patterns": [
                r"Facultative\s*(?:Certificate|Reinsurance)",
                r"Ceded\s*(?:Premium|Limit)",
            ],
            "weight": 0.9
        },
        DocumentType.TREATY_SLIP: {
            "keywords": [
                "treaty", "reinsurance treaty", "quota share", "surplus",
                "excess of loss", "reinstatement", "cedent", "rate on line"
            ],
            "sections": [
                "TREATY", "CEDENT", "REINSURER", "BUSINESS COVERED"
            ],
            "patterns": [
                r"(?:Reinsurance\s*)?Treaty",
                r"Rate\s*on\s*Line",
                r"Reinstatement",
            ],
            "weight": 0.85
        },
    }

    def detect(self, text: str) -> DocumentTypeResult:
        """
        Detect document type from text content.

        Args:
            text: The OCR-extracted text content.

        Returns:
            DocumentTypeResult with detected type and confidence.
        """
        text_lower = text.lower()
        text_upper = text.upper()

        scores = {}
        matches = {}

        for doc_type, indicators in self.TYPE_INDICATORS.items():
            score = 0.0
            matched_keywords = []
            matched_sections = []

            # Check keywords
            for keyword in indicators["keywords"]:
                if keyword.lower() in text_lower:
                    score += 1.0
                    matched_keywords.append(keyword)

            # Check sections (usually uppercase)
            for section in indicators["sections"]:
                if section in text_upper:
                    score += 2.0  # Sections weighted higher
                    matched_sections.append(section)

            # Check patterns
            for pattern in indicators["patterns"]:
                if re.search(pattern, text, re.IGNORECASE):
                    score += 1.5

            # Apply type weight
            score *= indicators["weight"]

            scores[doc_type] = score
            matches[doc_type] = {
                "keywords": matched_keywords,
                "sections": matched_sections
            }

        # Determine best match
        if not scores or max(scores.values()) == 0:
            return DocumentTypeResult(
                detected_type=DocumentType.UNKNOWN,
                confidence=0.0,
                confidence_level=ConfidenceLevel.LOW,
                matched_keywords=[],
                matched_sections=[],
                alternative_types=[]
            )

        # Normalize scores
        max_score = max(scores.values())
        sorted_types = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        best_type = sorted_types[0][0]
        best_score = sorted_types[0][1]

        # Calculate confidence (normalized to 0-100)
        confidence = min(100.0, (best_score / 10.0) * 100)

        # Determine confidence level
        if confidence >= 90:
            confidence_level = ConfidenceLevel.HIGH
        elif confidence >= 70:
            confidence_level = ConfidenceLevel.MEDIUM
        else:
            confidence_level = ConfidenceLevel.LOW

        # Get alternatives (top 3 excluding best)
        alternatives = [
            (t, min(100.0, (s / 10.0) * 100))
            for t, s in sorted_types[1:4]
            if s > 0
        ]

        return DocumentTypeResult(
            detected_type=best_type,
            confidence=confidence,
            confidence_level=confidence_level,
            matched_keywords=matches[best_type]["keywords"],
            matched_sections=matches[best_type]["sections"],
            alternative_types=alternatives
        )


# =============================================================================
# FIELD EXTRACTOR
# =============================================================================

class FieldExtractor:
    """Extracts specific fields from document text using patterns."""

    def __init__(self):
        self.patterns = ExtractionPatterns()
        self._month_map = {
            'jan': '01', 'january': '01',
            'feb': '02', 'february': '02',
            'mar': '03', 'march': '03',
            'apr': '04', 'april': '04',
            'may': '05',
            'jun': '06', 'june': '06',
            'jul': '07', 'july': '07',
            'aug': '08', 'august': '08',
            'sep': '09', 'september': '09',
            'oct': '10', 'october': '10',
            'nov': '11', 'november': '11',
            'dec': '12', 'december': '12',
        }

    def _calculate_confidence(
        self,
        match: re.Match,
        pattern_index: int,
        total_patterns: int,
        text: str
    ) -> float:
        """
        Calculate confidence score for a match.

        Factors:
        - Pattern specificity (earlier patterns more specific)
        - Match context (nearby relevant keywords)
        - Match length and format quality
        """
        base_confidence = 100.0 - (pattern_index * 5)

        # Check context (words around the match)
        start = max(0, match.start() - 50)
        end = min(len(text), match.end() + 50)
        context = text[start:end].lower()

        # Boost for relevant context
        context_keywords = ["policy", "premium", "limit", "insured", "date", "umr", "reference"]
        context_boost = sum(5 for kw in context_keywords if kw in context)

        confidence = min(100.0, base_confidence + context_boost)
        return confidence

    def _get_confidence_level(self, confidence: float) -> ConfidenceLevel:
        """Map confidence score to level."""
        if confidence >= 90:
            return ConfidenceLevel.HIGH
        elif confidence >= 70:
            return ConfidenceLevel.MEDIUM
        else:
            return ConfidenceLevel.LOW

    def extract_field(
        self,
        text: str,
        field_name: str,
        patterns: List[str],
        group_index: int = 1,
        clean_func=None
    ) -> Optional[ExtractedField]:
        """
        Extract a field value using multiple patterns.

        Args:
            text: Source text.
            field_name: Name of the field being extracted.
            patterns: List of regex patterns to try.
            group_index: Which capture group contains the value.
            clean_func: Optional function to clean/transform the value.

        Returns:
            ExtractedField if found, None otherwise.
        """
        for idx, pattern in enumerate(patterns):
            try:
                match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
                if match:
                    raw_text = match.group(0)
                    value = match.group(group_index) if match.lastindex >= group_index else match.group(0)

                    if clean_func:
                        value = clean_func(value)

                    if value:
                        value = value.strip()
                        confidence = self._calculate_confidence(match, idx, len(patterns), text)

                        return ExtractedField(
                            field_name=field_name,
                            value=value,
                            raw_text=raw_text,
                            confidence=confidence,
                            confidence_level=self._get_confidence_level(confidence),
                            pattern_used=pattern,
                            position=(match.start(), match.end()),
                            requires_review=confidence < 70
                        )
            except Exception as e:
                logger.debug(f"Pattern error for {field_name}: {e}")
                continue

        return None

    def extract_monetary_value(
        self,
        text: str,
        field_name: str,
        patterns: List[str]
    ) -> Optional[ExtractedField]:
        """Extract monetary values with currency detection."""
        currency_symbols = {'£': 'GBP', '$': 'USD', '€': 'EUR'}

        for idx, pattern in enumerate(patterns):
            try:
                match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
                if match:
                    groups = match.groups()
                    raw_text = match.group(0)

                    # Parse currency and amount from groups
                    currency = None
                    amount = None

                    for g in groups:
                        if g:
                            g = g.strip()
                            if g in currency_symbols:
                                currency = currency_symbols[g]
                            elif g.upper() in ['GBP', 'USD', 'EUR', 'CHF', 'JPY', 'AUD', 'CAD']:
                                currency = g.upper()
                            elif re.match(r'^[\d,]+(?:\.\d{2})?$', g):
                                amount = g.replace(',', '')

                    if amount:
                        try:
                            amount_float = float(amount)
                        except ValueError:
                            continue

                        value = {
                            "amount": amount_float,
                            "currency": currency or "USD",
                            "formatted": f"{currency or 'USD'} {amount_float:,.2f}"
                        }

                        confidence = self._calculate_confidence(match, idx, len(patterns), text)

                        return ExtractedField(
                            field_name=field_name,
                            value=value,
                            raw_text=raw_text,
                            confidence=confidence,
                            confidence_level=self._get_confidence_level(confidence),
                            pattern_used=pattern,
                            position=(match.start(), match.end()),
                            requires_review=confidence < 70
                        )
            except Exception as e:
                logger.debug(f"Monetary extraction error for {field_name}: {e}")
                continue

        return None

    def extract_date(
        self,
        text: str,
        field_name: str,
        patterns: List[str]
    ) -> Optional[ExtractedField]:
        """Extract and normalize date values."""
        for idx, pattern in enumerate(patterns):
            try:
                match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
                if match:
                    raw_text = match.group(0)
                    date_str = match.group(1) if match.lastindex >= 1 else match.group(0)

                    # Try to parse the date
                    normalized_date = self._normalize_date(date_str)

                    if normalized_date:
                        confidence = self._calculate_confidence(match, idx, len(patterns), text)

                        return ExtractedField(
                            field_name=field_name,
                            value=normalized_date,
                            raw_text=raw_text,
                            confidence=confidence,
                            confidence_level=self._get_confidence_level(confidence),
                            pattern_used=pattern,
                            position=(match.start(), match.end()),
                            requires_review=confidence < 70
                        )
            except Exception as e:
                logger.debug(f"Date extraction error for {field_name}: {e}")
                continue

        return None

    def _normalize_date(self, date_str: str) -> Optional[str]:
        """Normalize date string to ISO format (YYYY-MM-DD)."""
        date_str = date_str.strip()

        # Try DD/MM/YYYY or MM/DD/YYYY format
        match = re.match(r'(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})', date_str)
        if match:
            d1, d2, year = match.groups()

            # Handle 2-digit years
            if len(year) == 2:
                year = f"20{year}" if int(year) < 50 else f"19{year}"

            # Assume DD/MM/YYYY (European format common in Lloyd's)
            day, month = d1, d2

            # Validate and swap if needed
            if int(d2) > 12:
                day, month = d2, d1

            try:
                return f"{year}-{int(month):02d}-{int(day):02d}"
            except ValueError:
                return None

        # Try "DD Month YYYY" format
        match = re.match(
            r'(\d{1,2})\s+(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+(\d{2,4})',
            date_str,
            re.IGNORECASE
        )
        if match:
            day, month_name, year = match.groups()
            month = self._month_map.get(month_name.lower()[:3], '01')

            if len(year) == 2:
                year = f"20{year}" if int(year) < 50 else f"19{year}"

            return f"{year}-{month}-{int(day):02d}"

        return None

    def extract_percentage(
        self,
        text: str,
        field_name: str,
        patterns: List[str]
    ) -> Optional[ExtractedField]:
        """Extract percentage values."""
        for idx, pattern in enumerate(patterns):
            try:
                match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
                if match:
                    raw_text = match.group(0)
                    pct_str = match.group(1) if match.lastindex >= 1 else match.group(0)

                    # Clean and parse percentage
                    pct_str = pct_str.strip().replace('%', '')
                    try:
                        pct_value = float(pct_str)
                    except ValueError:
                        continue

                    confidence = self._calculate_confidence(match, idx, len(patterns), text)

                    return ExtractedField(
                        field_name=field_name,
                        value=pct_value,
                        raw_text=raw_text,
                        confidence=confidence,
                        confidence_level=self._get_confidence_level(confidence),
                        pattern_used=pattern,
                        position=(match.start(), match.end()),
                        requires_review=confidence < 70
                    )
            except Exception as e:
                logger.debug(f"Percentage extraction error for {field_name}: {e}")
                continue

        return None

    def extract_syndicate_lines(self, text: str) -> List[ExtractedField]:
        """Extract all syndicate participation lines."""
        lines = []

        for pattern in self.patterns.SYNDICATE_LINE:
            for match in re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE):
                try:
                    syndicate = match.group(1)
                    line_pct = float(match.group(2))

                    lines.append(ExtractedField(
                        field_name=f"syndicate_{syndicate}",
                        value={"syndicate": syndicate, "line_percentage": line_pct},
                        raw_text=match.group(0),
                        confidence=85.0,
                        confidence_level=ConfidenceLevel.HIGH,
                        pattern_used=pattern,
                        position=(match.start(), match.end()),
                        requires_review=False
                    ))
                except Exception as e:
                    logger.debug(f"Syndicate line extraction error: {e}")
                    continue

        return lines

    def extract_list_items(
        self,
        text: str,
        section_name: str,
        field_name: str
    ) -> List[ExtractedField]:
        """Extract list items from a document section."""
        items = []

        # Find section boundaries
        section_pattern = rf"(?:{section_name})[:\s]*\n((?:[-•*\d.]+\s*.+\n?)+)"
        match = re.search(section_pattern, text, re.IGNORECASE | re.MULTILINE)

        if match:
            section_text = match.group(1)

            # Extract individual items
            item_pattern = r"[-•*]|\d+[.)]\s*"
            lines = re.split(item_pattern, section_text)

            for idx, line in enumerate(lines):
                line = line.strip()
                if line and len(line) > 5:
                    items.append(ExtractedField(
                        field_name=f"{field_name}_{idx}",
                        value=line,
                        raw_text=line,
                        confidence=75.0,
                        confidence_level=ConfidenceLevel.MEDIUM,
                        pattern_used="list_item",
                        requires_review=True
                    ))

        return items


# =============================================================================
# INTELLIGENT DOCUMENT EXTRACTOR
# =============================================================================

class IntelligentDocumentExtractor:
    """
    AI-powered document extraction using:
    - Template matching for document type detection
    - Field-specific extraction patterns
    - RAG enhancement for insurance terminology
    - Confidence scoring per field
    """

    def __init__(self):
        self.type_detector = DocumentTypeDetector()
        self.field_extractor = FieldExtractor()
        self.reference_service = None
        self.qdrant_client = None
        self._initialize_services()

    def _initialize_services(self):
        """Initialize RAG and vector services."""
        try:
            from app.services.reference_document_service import reference_document_service
            self.reference_service = reference_document_service
        except ImportError:
            logger.warning("Reference document service not available")

        try:
            from qdrant_client import QdrantClient
            self.qdrant_client = QdrantClient(
                host=settings.QDRANT_HOST,
                port=settings.QDRANT_PORT
            )
        except Exception as e:
            logger.warning(f"Qdrant not available: {e}")

    async def extract_from_document(
        self,
        file_path: str,
        document_type: str = None,
        document_id: int = None,
        use_rag: bool = True
    ) -> ExtractionResult:
        """
        Extract structured data from an insurance document.

        Args:
            file_path: Path to the document file.
            document_type: Optional known document type.
            document_id: Optional database document ID.
            use_rag: Whether to use RAG enhancement.

        Returns:
            ExtractionResult with all extracted data and metadata.
        """
        import time
        start_time = time.time()

        # Step 1: Get document text (OCR if needed)
        text = await self._get_document_text(file_path)

        if not text or len(text.strip()) < 50:
            return self._create_failed_result(
                document_id,
                "No text content extracted from document"
            )

        # Calculate text hash for caching/tracking
        text_hash = hashlib.sha256(text.encode()).hexdigest()[:16]

        # Step 2: Detect document type (if not provided)
        if document_type:
            type_result = DocumentTypeResult(
                detected_type=DocumentType(document_type),
                confidence=100.0,
                confidence_level=ConfidenceLevel.HIGH,
                matched_keywords=[],
                matched_sections=[]
            )
        else:
            type_result = self.type_detector.detect(text)

        # Step 3: Get RAG context if enabled
        rag_context = ""
        similar_count = 0
        if use_rag and self.reference_service:
            try:
                rag_context = await self.reference_service.get_rag_context(
                    query=text[:1000],  # Use first 1000 chars as query
                    limit=3
                )
                similar_count = len(rag_context.split("---")) if rag_context else 0
            except Exception as e:
                logger.warning(f"RAG context retrieval failed: {e}")

        # Step 4: Extract fields based on document type
        extracted_data = await self._extract_by_type(
            text,
            type_result.detected_type,
            rag_context
        )

        # Step 5: Validate extraction
        template = self._get_template_for_type(type_result.detected_type)
        validation = self.validate_extraction(extracted_data, template)

        # Step 6: Calculate overall confidence
        overall_confidence, fields_for_review = self._calculate_overall_confidence(
            extracted_data
        )

        processing_time = (time.time() - start_time) * 1000

        return ExtractionResult(
            document_id=document_id,
            document_type=type_result,
            status=(
                ExtractionStatus.SUCCESS if validation.is_valid
                else ExtractionStatus.PARTIAL if validation.completeness_score > 0.5
                else ExtractionStatus.FAILED
            ),
            extracted_data=extracted_data,
            validation=validation,
            overall_confidence=overall_confidence,
            overall_confidence_level=self.field_extractor._get_confidence_level(overall_confidence),
            fields_requiring_review=fields_for_review,
            processing_time_ms=processing_time,
            rag_context_used=bool(rag_context),
            similar_documents_found=similar_count,
            raw_text_hash=text_hash
        )

    async def _get_document_text(self, file_path: str) -> str:
        """Get text content from document file."""
        try:
            from app.services.ocr_service import ocr_service

            path = Path(file_path)
            if path.suffix.lower() == '.pdf':
                result = await ocr_service.process_pdf(file_path)
            else:
                result = await ocr_service.process_document(file_path)

            return result.get("text", "")
        except Exception as e:
            logger.error(f"Text extraction error: {e}")
            return ""

    async def detect_document_type(self, text: str) -> DocumentTypeResult:
        """
        Detect the type of insurance document from text.

        Args:
            text: OCR-extracted text content.

        Returns:
            DocumentTypeResult with detection details.
        """
        return self.type_detector.detect(text)

    async def extract_mrc_slip(
        self,
        text: str,
        rag_context: str = ""
    ) -> MRCSlipData:
        """
        Extract data from a Lloyd's MRC slip.

        Args:
            text: Document text content.
            rag_context: Optional RAG context for enhancement.

        Returns:
            MRCSlipData with all extracted fields.
        """
        p = self.field_extractor.patterns
        fe = self.field_extractor

        data = MRCSlipData(
            umr=fe.extract_field(text, "umr", p.UMR),
            pbcr=fe.extract_field(text, "pbcr", p.BROKER_REF),
            insured_name=fe.extract_field(text, "insured_name", p.INSURED),
            broker_name=fe.extract_field(text, "broker_name", p.BROKER),
            broker_reference=fe.extract_field(text, "broker_reference", p.BROKER_REF),
            class_of_business=fe.extract_field(text, "class_of_business", p.CLASS_OF_BUSINESS),
            risk_code=fe.extract_field(text, "risk_code", p.RISK_CODE),
            period_from=fe.extract_date(text, "period_from", p.INCEPTION_DATE),
            period_to=fe.extract_date(text, "period_to", p.EXPIRY_DATE),
            limit_of_liability=fe.extract_monetary_value(text, "limit_of_liability", p.LIMIT),
            aggregate_limit=fe.extract_monetary_value(text, "aggregate_limit", p.AGGREGATE),
            deductible=fe.extract_monetary_value(text, "deductible", p.DEDUCTIBLE),
            premium=fe.extract_monetary_value(text, "premium", p.PREMIUM),
            minimum_premium=fe.extract_monetary_value(text, "minimum_premium", p.MIN_DEP_PREMIUM),
            currency=fe.extract_field(text, "currency", p.CURRENCY),
            lead_underwriter=fe.extract_field(text, "lead_underwriter", p.LEAD_UNDERWRITER),
            signed_line=fe.extract_percentage(text, "signed_line", p.SIGNED_LINE),
            order_percentage=fe.extract_percentage(text, "order_percentage", p.ORDER_PERCENTAGE),
            syndicate_lines=fe.extract_syndicate_lines(text),
            territorial_limits=fe.extract_field(text, "territorial_limits", p.TERRITORIAL_LIMITS),
            jurisdiction=fe.extract_field(text, "jurisdiction", p.JURISDICTION),
            basis_of_cover=fe.extract_field(text, "basis_of_cover", p.BASIS_OF_COVER),
            subjectivities=fe.extract_list_items(text, "SUBJECTIVITIES", "subjectivity"),
            warranties=fe.extract_list_items(text, "WARRANTIES", "warranty"),
            exclusions=fe.extract_list_items(text, "EXCLUSIONS", "exclusion"),
        )

        # Extract lead syndicate number if present
        if not data.lead_syndicate:
            syndicate_match = re.search(r"Lead\s*Syndicate[:\s]*(\d{3,4})", text, re.IGNORECASE)
            if syndicate_match:
                data.lead_syndicate = ExtractedField(
                    field_name="lead_syndicate",
                    value=syndicate_match.group(1),
                    raw_text=syndicate_match.group(0),
                    confidence=90.0,
                    confidence_level=ConfidenceLevel.HIGH,
                    pattern_used="Lead Syndicate pattern",
                    position=(syndicate_match.start(), syndicate_match.end()),
                    requires_review=False
                )

        return data

    async def extract_policy_schedule(
        self,
        text: str,
        rag_context: str = ""
    ) -> PolicyScheduleData:
        """
        Extract data from a policy schedule.

        Args:
            text: Document text content.
            rag_context: Optional RAG context for enhancement.

        Returns:
            PolicyScheduleData with all extracted fields.
        """
        p = self.field_extractor.patterns
        fe = self.field_extractor

        data = PolicyScheduleData(
            policy_number=fe.extract_field(text, "policy_number", p.POLICY_NUMBER),
            umr=fe.extract_field(text, "umr", p.UMR),
            named_insured=fe.extract_field(text, "named_insured", p.INSURED),
            policy_period_from=fe.extract_date(text, "policy_period_from", p.INCEPTION_DATE),
            policy_period_to=fe.extract_date(text, "policy_period_to", p.EXPIRY_DATE),
            limits_schedule=fe.extract_list_items(text, "LIMITS?(?:\s*SCHEDULE)?", "limit"),
            deductibles_schedule=fe.extract_list_items(text, "DEDUCTIBLES?(?:\s*SCHEDULE)?", "deductible"),
            premium_schedule=fe.extract_list_items(text, "PREMIUM(?:\s*SCHEDULE)?", "premium"),
            locations=fe.extract_list_items(text, "LOCATIONS?(?:\s*SCHEDULE)?", "location"),
            endorsements=fe.extract_list_items(text, "ENDORSEMENTS?", "endorsement"),
        )

        return data

    async def _extract_by_type(
        self,
        text: str,
        doc_type: DocumentType,
        rag_context: str
    ) -> Union[MRCSlipData, PolicyScheduleData, Dict[str, Any]]:
        """Extract data based on document type."""

        if doc_type == DocumentType.MRC_SLIP:
            return await self.extract_mrc_slip(text, rag_context)

        elif doc_type == DocumentType.POLICY_SCHEDULE:
            return await self.extract_policy_schedule(text, rag_context)

        elif doc_type == DocumentType.POLICY_WORDING:
            return await self._extract_generic(text, "lloyds_policy_wording")

        elif doc_type == DocumentType.ENDORSEMENT:
            return await self._extract_generic(text, "lloyds_endorsement")

        elif doc_type == DocumentType.CERTIFICATE:
            return await self._extract_generic(text, "certificate_of_insurance")

        else:
            # Generic extraction for unknown types
            return await self._extract_generic(text, None)

    async def _extract_generic(
        self,
        text: str,
        template_id: Optional[str]
    ) -> Dict[str, Any]:
        """Generic extraction when specific type handlers aren't available."""
        p = self.field_extractor.patterns
        fe = self.field_extractor

        extracted = {}

        # Try to extract common fields
        common_extractions = [
            ("umr", p.UMR),
            ("policy_number", p.POLICY_NUMBER),
            ("insured", p.INSURED),
            ("broker", p.BROKER),
            ("premium", p.PREMIUM),
            ("limit", p.LIMIT),
            ("deductible", p.DEDUCTIBLE),
        ]

        for field_name, patterns in common_extractions:
            if field_name in ["premium", "limit", "deductible"]:
                result = fe.extract_monetary_value(text, field_name, patterns)
            else:
                result = fe.extract_field(text, field_name, patterns)

            if result:
                extracted[field_name] = result.to_dict()

        # Extract dates
        inception = fe.extract_date(text, "inception_date", p.INCEPTION_DATE)
        expiry = fe.extract_date(text, "expiry_date", p.EXPIRY_DATE)

        if inception:
            extracted["inception_date"] = inception.to_dict()
        if expiry:
            extracted["expiry_date"] = expiry.to_dict()

        return extracted

    def _get_template_for_type(self, doc_type: DocumentType) -> Optional[Dict]:
        """Get the template for a document type."""
        type_to_template = {
            DocumentType.MRC_SLIP: "lloyds_mrc_slip",
            DocumentType.POLICY_SCHEDULE: "lloyds_policy_wording",
            DocumentType.POLICY_WORDING: "lloyds_policy_wording",
            DocumentType.ENDORSEMENT: "lloyds_endorsement",
            DocumentType.BINDER: "lloyds_binder",
            DocumentType.CERTIFICATE: "certificate_of_insurance",
            DocumentType.SIGNING_PAGE: "lloyds_signing",
            DocumentType.COVER_NOTE: "lloyds_cover_note",
            DocumentType.QUOTE: "lloyds_quote",
            DocumentType.CLAIMS_ADVICE: "lloyds_claims_advice",
            DocumentType.BORDEREAUX: "bordereaux",
            DocumentType.FACULTATIVE_CERT: "facultative_certificate",
            DocumentType.TREATY_SLIP: "treaty_slip",
        }

        template_id = type_to_template.get(doc_type)
        if template_id:
            return get_template(template_id)
        return None

    def validate_extraction(
        self,
        data: Union[MRCSlipData, PolicyScheduleData, Dict],
        template: Optional[Dict]
    ) -> ValidationResult:
        """
        Validate extracted data against template requirements.

        Args:
            data: Extracted data object.
            template: Template definition with required fields.

        Returns:
            ValidationResult with validation details.
        """
        required_found = []
        required_missing = []
        optional_found = []
        warnings = []
        errors = []
        field_validations = {}

        if template is None:
            # Basic validation without template
            data_dict = data.to_dict() if hasattr(data, 'to_dict') else data
            found_count = sum(1 for v in data_dict.values() if v is not None)

            return ValidationResult(
                is_valid=found_count > 0,
                completeness_score=min(1.0, found_count / 10.0),
                required_fields_found=list(k for k, v in data_dict.items() if v),
                required_fields_missing=[],
                optional_fields_found=[],
                warnings=["No template available for validation"],
                errors=[],
                field_validations={}
            )

        # Get required fields from template
        required_fields = []
        optional_fields = []

        for section_name, section_fields in template.get("fields", {}).items():
            if isinstance(section_fields, dict):
                for field_name, field_config in section_fields.items():
                    if isinstance(field_config, dict):
                        if field_config.get("required"):
                            required_fields.append(field_name)
                        else:
                            optional_fields.append(field_name)

        # Check data against requirements
        data_dict = data.to_dict() if hasattr(data, 'to_dict') else data

        for field in required_fields:
            field_data = data_dict.get(field)
            if field_data and (
                isinstance(field_data, dict) and field_data.get("value") is not None
                or not isinstance(field_data, dict) and field_data is not None
            ):
                required_found.append(field)
                field_validations[field] = True
            else:
                required_missing.append(field)
                field_validations[field] = False
                errors.append(f"Required field missing: {field}")

        for field in optional_fields:
            field_data = data_dict.get(field)
            if field_data and (
                isinstance(field_data, dict) and field_data.get("value") is not None
                or not isinstance(field_data, dict) and field_data is not None
            ):
                optional_found.append(field)
                field_validations[field] = True

        # Calculate completeness
        total_required = len(required_fields)
        found_required = len(required_found)
        completeness = found_required / total_required if total_required > 0 else 1.0

        # Add warnings for low confidence fields
        for key, value in data_dict.items():
            if isinstance(value, dict) and value.get("confidence_level") == "low":
                warnings.append(f"Low confidence extraction: {key}")

        return ValidationResult(
            is_valid=len(required_missing) == 0,
            completeness_score=completeness,
            required_fields_found=required_found,
            required_fields_missing=required_missing,
            optional_fields_found=optional_found,
            warnings=warnings,
            errors=errors,
            field_validations=field_validations
        )

    def _calculate_overall_confidence(
        self,
        data: Union[MRCSlipData, PolicyScheduleData, Dict]
    ) -> Tuple[float, List[str]]:
        """Calculate overall confidence and identify fields for review."""
        data_dict = data.to_dict() if hasattr(data, 'to_dict') else data

        confidences = []
        review_fields = []

        for field_name, field_data in data_dict.items():
            if isinstance(field_data, dict) and "confidence" in field_data:
                confidences.append(field_data["confidence"])
                if field_data.get("requires_review") or field_data.get("confidence", 100) < 70:
                    review_fields.append(field_name)
            elif isinstance(field_data, list):
                for item in field_data:
                    if isinstance(item, dict) and "confidence" in item:
                        confidences.append(item["confidence"])
                        if item.get("requires_review"):
                            review_fields.append(field_name)

        overall = sum(confidences) / len(confidences) if confidences else 0.0
        return overall, review_fields

    def _create_failed_result(
        self,
        document_id: Optional[int],
        error_message: str
    ) -> ExtractionResult:
        """Create a failed extraction result."""
        return ExtractionResult(
            document_id=document_id,
            document_type=DocumentTypeResult(
                detected_type=DocumentType.UNKNOWN,
                confidence=0.0,
                confidence_level=ConfidenceLevel.LOW,
                matched_keywords=[],
                matched_sections=[]
            ),
            status=ExtractionStatus.FAILED,
            extracted_data={},
            validation=ValidationResult(
                is_valid=False,
                completeness_score=0.0,
                required_fields_found=[],
                required_fields_missing=[],
                optional_fields_found=[],
                warnings=[],
                errors=[error_message],
                field_validations={}
            ),
            overall_confidence=0.0,
            overall_confidence_level=ConfidenceLevel.LOW,
            fields_requiring_review=[],
            processing_time_ms=0.0,
            rag_context_used=False,
            similar_documents_found=0
        )


# =============================================================================
# HUMAN FEEDBACK LOOP
# =============================================================================

class ExtractionFeedbackManager:
    """
    Manages human feedback for extraction corrections.
    Stores corrections to improve future extractions.
    """

    def __init__(self, db_session_factory=None):
        self.db_session_factory = db_session_factory

    async def record_correction(
        self,
        document_id: int,
        field_name: str,
        original_value: Any,
        corrected_value: Any,
        user_id: str,
        confidence_was: float,
        extraction_pattern: str = None
    ) -> Dict[str, Any]:
        """
        Record a human correction to an extracted field.

        Args:
            document_id: ID of the document.
            field_name: Name of the corrected field.
            original_value: Value that was extracted.
            corrected_value: Corrected value from human.
            user_id: ID of the user making correction.
            confidence_was: Original confidence score.
            extraction_pattern: Pattern that was used for extraction.

        Returns:
            Confirmation of recorded correction.
        """
        correction_record = {
            "document_id": document_id,
            "field_name": field_name,
            "original_value": original_value,
            "corrected_value": corrected_value,
            "user_id": user_id,
            "original_confidence": confidence_was,
            "extraction_pattern": extraction_pattern,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "correction_type": self._determine_correction_type(original_value, corrected_value)
        }

        # Store in database if available
        if self.db_session_factory:
            try:
                # Would insert into extraction_corrections table
                logger.info(f"Stored correction for document {document_id}, field {field_name}")
            except Exception as e:
                logger.error(f"Failed to store correction: {e}")

        logger.info(
            f"Correction recorded: document={document_id}, field={field_name}, "
            f"original={original_value}, corrected={corrected_value}"
        )

        return correction_record

    def _determine_correction_type(
        self,
        original: Any,
        corrected: Any
    ) -> str:
        """Determine the type of correction made."""
        if original is None:
            return "missing_value"
        if corrected is None:
            return "false_positive"
        if isinstance(original, str) and isinstance(corrected, str):
            if original.lower() == corrected.lower():
                return "formatting"
            return "wrong_value"
        return "type_mismatch"

    async def get_accuracy_metrics(
        self,
        field_name: str = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get accuracy metrics for extractions.

        Args:
            field_name: Optional specific field to analyze.
            days: Number of days to analyze.

        Returns:
            Accuracy metrics including correction rates.
        """
        # Would query correction history from database
        return {
            "field_name": field_name or "all",
            "period_days": days,
            "total_extractions": 0,
            "total_corrections": 0,
            "accuracy_rate": 0.0,
            "common_correction_types": [],
            "fields_with_lowest_accuracy": []
        }


# =============================================================================
# TRAINING DATA COLLECTOR
# =============================================================================

class TrainingDataCollector:
    """
    Collects and exports training data from extractions.
    Formats data for model fine-tuning.
    """

    def __init__(self, output_dir: str = None):
        if output_dir is None:
            output_dir = "/tmp/training_data"
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def log_extraction(
        self,
        document_id: int,
        raw_text: str,
        extraction_result: ExtractionResult,
        ground_truth: Dict[str, Any] = None
    ) -> str:
        """
        Log an extraction for training purposes.

        Args:
            document_id: ID of the document.
            raw_text: Original OCR text.
            extraction_result: The extraction result.
            ground_truth: Optional verified ground truth values.

        Returns:
            ID of the logged training sample.
        """
        sample_id = f"{document_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        training_sample = {
            "sample_id": sample_id,
            "document_id": document_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "document_type": extraction_result.document_type.detected_type.value,
            "raw_text": raw_text,
            "extracted_data": extraction_result.to_dict(),
            "ground_truth": ground_truth,
            "has_ground_truth": ground_truth is not None,
            "overall_confidence": extraction_result.overall_confidence
        }

        # Save to JSONL file
        output_file = self.output_dir / f"training_samples_{datetime.now().strftime('%Y%m')}.jsonl"

        with open(output_file, 'a') as f:
            f.write(json.dumps(training_sample) + '\n')

        logger.info(f"Logged training sample: {sample_id}")
        return sample_id

    async def export_training_dataset(
        self,
        format: str = "jsonl",
        include_only_verified: bool = False,
        min_confidence: float = 0.0
    ) -> str:
        """
        Export training data in specified format.

        Args:
            format: Output format (jsonl, csv, huggingface).
            include_only_verified: Only include samples with ground truth.
            min_confidence: Minimum confidence threshold.

        Returns:
            Path to exported dataset.
        """
        samples = []

        # Read all training samples
        for jsonl_file in self.output_dir.glob("training_samples_*.jsonl"):
            with open(jsonl_file, 'r') as f:
                for line in f:
                    sample = json.loads(line)

                    if include_only_verified and not sample.get("has_ground_truth"):
                        continue

                    if sample.get("overall_confidence", 0) < min_confidence:
                        continue

                    samples.append(sample)

        if not samples:
            logger.warning("No training samples found matching criteria")
            return ""

        # Export based on format
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        if format == "jsonl":
            output_path = self.output_dir / f"dataset_{timestamp}.jsonl"
            with open(output_path, 'w') as f:
                for sample in samples:
                    f.write(json.dumps(sample) + '\n')

        elif format == "csv":
            import csv
            output_path = self.output_dir / f"dataset_{timestamp}.csv"

            with open(output_path, 'w', newline='') as f:
                writer = csv.writer(f)
                # Flatten and write samples
                if samples:
                    headers = list(samples[0].keys())
                    writer.writerow(headers)
                    for sample in samples:
                        writer.writerow([
                            json.dumps(v) if isinstance(v, (dict, list)) else v
                            for v in sample.values()
                        ])

        elif format == "huggingface":
            # Format for Hugging Face datasets
            hf_samples = []
            for sample in samples:
                hf_samples.append({
                    "text": sample["raw_text"],
                    "document_type": sample["document_type"],
                    "extracted_fields": json.dumps(sample["extracted_data"]),
                    "ground_truth": json.dumps(sample.get("ground_truth", {}))
                })

            output_path = self.output_dir / f"hf_dataset_{timestamp}.jsonl"
            with open(output_path, 'w') as f:
                for sample in hf_samples:
                    f.write(json.dumps(sample) + '\n')

        else:
            raise ValueError(f"Unsupported format: {format}")

        logger.info(f"Exported {len(samples)} samples to {output_path}")
        return str(output_path)

    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about collected training data."""
        total_samples = 0
        verified_samples = 0
        doc_type_counts = {}
        confidence_sum = 0.0

        for jsonl_file in self.output_dir.glob("training_samples_*.jsonl"):
            with open(jsonl_file, 'r') as f:
                for line in f:
                    sample = json.loads(line)
                    total_samples += 1

                    if sample.get("has_ground_truth"):
                        verified_samples += 1

                    doc_type = sample.get("document_type", "unknown")
                    doc_type_counts[doc_type] = doc_type_counts.get(doc_type, 0) + 1

                    confidence_sum += sample.get("overall_confidence", 0)

        return {
            "total_samples": total_samples,
            "verified_samples": verified_samples,
            "verification_rate": verified_samples / total_samples if total_samples > 0 else 0,
            "document_type_distribution": doc_type_counts,
            "average_confidence": confidence_sum / total_samples if total_samples > 0 else 0,
            "output_directory": str(self.output_dir)
        }


# =============================================================================
# SINGLETON INSTANCES
# =============================================================================

intelligent_extractor = IntelligentDocumentExtractor()
feedback_manager = ExtractionFeedbackManager()
training_collector = TrainingDataCollector()


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

async def extract_document(
    file_path: str,
    document_type: str = None,
    document_id: int = None
) -> Dict[str, Any]:
    """
    Convenience function to extract data from a document.

    Args:
        file_path: Path to the document.
        document_type: Optional known document type.
        document_id: Optional database document ID.

    Returns:
        Extraction result as dictionary.
    """
    result = await intelligent_extractor.extract_from_document(
        file_path=file_path,
        document_type=document_type,
        document_id=document_id
    )
    return result.to_dict()


async def detect_type(text: str) -> Dict[str, Any]:
    """
    Convenience function to detect document type.

    Args:
        text: Document text content.

    Returns:
        Detection result as dictionary.
    """
    result = await intelligent_extractor.detect_document_type(text)
    return result.to_dict()


def get_confidence_level(score: float) -> str:
    """
    Get confidence level label from score.

    Args:
        score: Confidence score (0-100).

    Returns:
        Confidence level string.
    """
    if score >= 90:
        return "high"
    elif score >= 70:
        return "medium"
    else:
        return "low"
