"""
InstantRisk V2 - OCR Service

This module provides fast, high-quality OCR processing using RapidOCR
for document text extraction.
"""

import asyncio
from typing import Dict, Any, List, Optional
from pathlib import Path
import logging

from app.config import settings

logger = logging.getLogger(__name__)


class OCRService:
    """
    Fast, high-quality OCR service using RapidOCR.

    Provides both text extraction and structured data parsing.
    Much faster than EasyOCR on CPU with comparable quality.
    """

    def __init__(self, languages: Optional[List[str]] = None):
        """
        Initialize the OCR service.

        Args:
            languages: List of language codes to support.
                      Defaults to settings.OCR_LANGUAGES.
        """
        self.languages = languages or settings.OCR_LANGUAGES
        self._engine = None

    def _get_engine(self):
        """
        Lazily initialize the RapidOCR engine.

        Returns:
            RapidOCR: The initialized OCR engine instance.
        """
        if self._engine is None:
            try:
                from rapidocr_onnxruntime import RapidOCR
                self._engine = RapidOCR()
                logger.info("RapidOCR engine initialized successfully")
            except ImportError:
                logger.error("RapidOCR not installed. Run: pip install rapidocr-onnxruntime")
                raise ImportError("RapidOCR is required for OCR processing")
        return self._engine

    async def process_document(self, file_path: str) -> Dict[str, Any]:
        """
        Process a document and extract text using OCR.

        Args:
            file_path: Path to the document file.

        Returns:
            dict: OCR results including:
                - text: Extracted text content
                - confidence: Average confidence score (0-100)
                - language: Detected primary language
                - extracted_data: Structured data (if applicable)
                - boxes: List of text boxes with coordinates

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If the file type is not supported.
        """
        # Run OCR in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            self._process_sync,
            file_path
        )
        return result

    def _process_sync(self, file_path: str) -> Dict[str, Any]:
        """
        Synchronous OCR processing.

        Args:
            file_path: Path to the document file.

        Returns:
            dict: OCR results.
        """
        try:
            engine = self._get_engine()

            # Process the image/document
            result, elapse = engine(file_path)

            # Extract text and calculate confidence
            texts = []
            confidences = []
            boxes = []

            if result:
                for item in result:
                    bbox, text, confidence = item
                    texts.append(text)
                    confidences.append(confidence)
                    boxes.append({
                        "text": text,
                        "confidence": round(confidence * 100, 2),
                        "bbox": bbox
                    })

            # Combine text
            full_text = "\n".join(texts)

            # Calculate average confidence
            avg_confidence = (
                sum(confidences) / len(confidences) * 100
                if confidences else 0
            )

            # Try to extract structured data
            extracted_data = self._extract_structured_data(full_text)

            # Detect primary language
            detected_language = self._detect_language(full_text)

            return {
                "text": full_text,
                "confidence": round(avg_confidence),
                "language": detected_language,
                "extracted_data": extracted_data,
                "boxes": boxes,
                "word_count": len(full_text.split()),
                "processing_time_ms": round(elapse * 1000) if elapse else None
            }

        except FileNotFoundError:
            logger.error(f"File not found: {file_path}")
            raise
        except Exception as e:
            logger.error(f"OCR processing error: {str(e)}")
            raise

    def _extract_structured_data(self, text: str) -> Dict[str, Any]:
        """
        Extract structured data from OCR text.

        Attempts to identify and extract common insurance document fields.

        Args:
            text: The extracted OCR text.

        Returns:
            dict: Structured data extracted from the text.
        """
        import re

        extracted = {}

        # Try to extract common fields
        patterns = {
            "policy_number": r"(?:Policy\s*(?:No|Number|#)?[:\s]*)?([A-Z]{2,4}[-/]?\d{6,12})",
            "premium": r"(?:Premium|Total Premium)[:\s]*[\$\u00A3\u20AC]?\s*([\d,]+(?:\.\d{2})?)",
            "sum_insured": r"(?:Sum Insured|Total Sum Insured|TSI)[:\s]*[\$\u00A3\u20AC]?\s*([\d,]+(?:\.\d{2})?)",
            "inception_date": r"(?:Inception|Start|Effective)[:\s]*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})",
            "expiry_date": r"(?:Expiry|End|Termination)[:\s]*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})",
            "insured_name": r"(?:Insured|Named Insured|Policy Holder)[:\s]*([A-Za-z\s&.,]+?)(?:\n|$)",
            "broker": r"(?:Broker|Producing Broker)[:\s]*([A-Za-z\s&.,]+?)(?:\n|$)",
        }

        for field, pattern in patterns.items():
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                extracted[field] = match.group(1).strip()

        return extracted

    def _detect_language(self, text: str) -> str:
        """
        Detect the primary language of the text.

        Args:
            text: The text to analyze.

        Returns:
            str: Detected language code.
        """
        # Simple heuristic based on character sets
        arabic_chars = sum(1 for c in text if '\u0600' <= c <= '\u06FF')
        total_chars = len(text.replace(" ", ""))

        if total_chars == 0:
            return "en"

        arabic_ratio = arabic_chars / total_chars

        if arabic_ratio > 0.3:
            return "ar"

        # Check for French-specific characters
        french_indicators = ["é", "è", "ê", "ë", "à", "â", "ù", "û", "ô", "î", "ç"]
        french_count = sum(text.lower().count(c) for c in french_indicators)

        if french_count > 5:
            return "fr"

        return "en"

    async def process_pdf(self, pdf_path: str) -> Dict[str, Any]:
        """
        Process a PDF document page by page.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            dict: Combined OCR results from all pages.
        """
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            self._process_pdf_sync,
            pdf_path
        )
        return result

    def _process_pdf_sync(self, pdf_path: str) -> Dict[str, Any]:
        """
        Synchronous PDF processing.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            dict: Combined OCR results.
        """
        try:
            import pdf2image
        except ImportError:
            logger.error("pdf2image not installed. Run: pip install pdf2image")
            raise ImportError("pdf2image is required for PDF processing")

        try:
            # Convert PDF to images
            images = pdf2image.convert_from_path(pdf_path)

            all_texts = []
            all_confidences = []
            page_results = []

            engine = self._get_engine()

            for i, image in enumerate(images):
                # Convert PIL image to numpy array
                import numpy as np
                image_np = np.array(image)

                # Process page with RapidOCR
                result, _ = engine(image_np)

                page_text = []
                page_confidence = []

                if result:
                    for item in result:
                        bbox, text, confidence = item
                        page_text.append(text)
                        page_confidence.append(confidence)

                page_results.append({
                    "page": i + 1,
                    "text": "\n".join(page_text),
                    "confidence": (
                        sum(page_confidence) / len(page_confidence) * 100
                        if page_confidence else 0
                    )
                })

                all_texts.extend(page_text)
                all_confidences.extend(page_confidence)

            full_text = "\n\n".join([p["text"] for p in page_results])
            avg_confidence = (
                sum(all_confidences) / len(all_confidences) * 100
                if all_confidences else 0
            )

            return {
                "text": full_text,
                "confidence": round(avg_confidence),
                "language": self._detect_language(full_text),
                "extracted_data": self._extract_structured_data(full_text),
                "pages": page_results,
                "page_count": len(images)
            }

        except Exception as e:
            logger.error(f"PDF processing error: {str(e)}")
            raise

# Singleton instance
ocr_service = OCRService()
