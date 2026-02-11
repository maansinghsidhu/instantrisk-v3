"""
InstantRisk V3 - Services Module

This module exports all service classes for the application.
"""

from app.services.ocr_service import OCRService
from app.services.ai_service import AIService

# Document Processing Pipeline (V3)
from app.services.document_chunker import (
    IntelligentDocumentChunker,
    ChunkResultAggregator,
    DocumentChunk,
    ChunkingResult,
    AggregatedResult,
    document_chunker,
    result_aggregator,
)
from app.services.enhanced_autogen_processor import (
    EnhancedAutoGenProcessor,
    enhanced_processor,
)
from app.services.intelligent_document_generator import (
    IntelligentDocumentGenerator,
    intelligent_generator,
    ClauseSelection,
    TemplateSelection,
    GeneratedDocument,
    DocumentPurpose,
)

from app.services.algorithmic_underwriting import (
    AlgorithmicUnderwritingEngine,
    get_underwriting_engine,
    quick_price,
    quick_quote,
    # Dataclasses
    RiskFactors,
    PricingBreakdown,
    MarketComparison,
    CapacityRecommendation,
    ExplainableAIReport,
    PricingResultData,
    QuoteData,
    # Enums
    RiskCategory,
    ClassOfBusiness,
    DecisionType,
)
from app.services.intelligent_extractor import (
    IntelligentDocumentExtractor,
    ExtractionFeedbackManager,
    TrainingDataCollector,
    # Singleton instances
    intelligent_extractor,
    feedback_manager,
    training_collector,
    # Convenience functions
    extract_document,
    detect_type,
    get_confidence_level,
    # Dataclasses
    ExtractedField,
    ExtractionResult,
    DocumentTypeResult,
    MRCSlipData,
    PolicyScheduleData,
    ValidationResult,
    # Enums
    DocumentType,
    ConfidenceLevel,
    ExtractionStatus,
)

__all__ = [
    # Existing services
    "OCRService",
    "AIService",
    # Document Processing Pipeline (V3)
    "IntelligentDocumentChunker",
    "ChunkResultAggregator",
    "DocumentChunk",
    "ChunkingResult",
    "AggregatedResult",
    "document_chunker",
    "result_aggregator",
    "EnhancedAutoGenProcessor",
    "enhanced_processor",
    "IntelligentDocumentGenerator",
    "intelligent_generator",
    "ClauseSelection",
    "TemplateSelection",
    "GeneratedDocument",
    "DocumentPurpose",
    # Algorithmic underwriting
    "AlgorithmicUnderwritingEngine",
    "get_underwriting_engine",
    "quick_price",
    "quick_quote",
    # Dataclasses
    "RiskFactors",
    "PricingBreakdown",
    "MarketComparison",
    "CapacityRecommendation",
    "ExplainableAIReport",
    "PricingResultData",
    "QuoteData",
    # Enums
    "RiskCategory",
    "ClassOfBusiness",
    "DecisionType",
    # Intelligent Extractor
    "IntelligentDocumentExtractor",
    "ExtractionFeedbackManager",
    "TrainingDataCollector",
    "intelligent_extractor",
    "feedback_manager",
    "training_collector",
    "extract_document",
    "detect_type",
    "get_confidence_level",
    # Extractor Dataclasses
    "ExtractedField",
    "ExtractionResult",
    "DocumentTypeResult",
    "MRCSlipData",
    "PolicyScheduleData",
    "ValidationResult",
    # Extractor Enums
    "DocumentType",
    "ConfidenceLevel",
    "ExtractionStatus",
]
