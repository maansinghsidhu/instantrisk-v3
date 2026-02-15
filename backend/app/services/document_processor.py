"""
Document Processor Service - Analyzes uploaded documents using OCR + AI

Extracts insurance-relevant information from images and documents.
Uses OCR to extract text from images, then AWS Bedrock Claude to analyze.
"""

import os
import base64
import json
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Configure logging to ensure output is visible
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

from app.services.bedrock_client import BedrockClient as _BedrockClient

# Try to import OCR dependencies
try:
    import pytesseract
    from PIL import Image
    OCR_AVAILABLE = True
    logger.info("OCR (pytesseract) available")
except ImportError:
    OCR_AVAILABLE = False
    logger.warning("OCR not available - pytesseract or PIL not installed")

# Try to import RapidOCR for fast, high-quality OCR
try:
    from rapidocr_onnxruntime import RapidOCR
    RAPIDOCR_AVAILABLE = True
    RAPIDOCR_ENGINE = None  # Lazy init to avoid startup delay
    logger.info("RapidOCR available for fast, high-quality document OCR")
except ImportError:
    RAPIDOCR_AVAILABLE = False
    RAPIDOCR_ENGINE = None
    logger.warning("RapidOCR not available - install with: pip install rapidocr-onnxruntime")

# Try to import PDF dependencies
try:
    import fitz  # PyMuPDF
    PDF_AVAILABLE = True
    logger.info("PDF processing (PyMuPDF) available")
except ImportError:
    PDF_AVAILABLE = False
    logger.warning("PDF processing not available - PyMuPDF not installed")

class DocumentProcessor:
    """Process and analyze insurance documents using OCR + Bedrock Claude."""

    def __init__(self):
        self._bedrock = _BedrockClient()

    def _extract_text_ocr(self, file_path: str, use_rapidocr: bool = True) -> str:
        """
        Extract text from image or PDF using best available OCR.
        Priority: RapidOCR > Tesseract > PyMuPDF (for PDFs)

        Args:
            file_path: Path to the document
            use_rapidocr: If True, prefer RapidOCR for higher quality (fast and accurate)
        """
        global RAPIDOCR_ENGINE

        file_lower = file_path.lower()

        # Handle PDFs
        if file_lower.endswith('.pdf'):
            return self._extract_text_from_pdf(file_path)

        # Try RapidOCR first for best quality on images
        if use_rapidocr and RAPIDOCR_AVAILABLE:
            try:
                # Lazy initialize RapidOCR engine
                if RAPIDOCR_ENGINE is None:
                    logger.info("Initializing RapidOCR engine...")
                    RAPIDOCR_ENGINE = RapidOCR()

                logger.info(f"Using RapidOCR for fast, high-quality extraction: {file_path}")
                result, _ = RAPIDOCR_ENGINE(file_path)

                if result:
                    # RapidOCR returns list of [box, text, confidence]
                    texts = [item[1] for item in result]
                    text = "\n".join(texts)
                    logger.info(f"RapidOCR extracted {len(text)} characters from {file_path}")
                    return text.strip()
                else:
                    logger.warning(f"RapidOCR returned no results for {file_path}")
            except Exception as e:
                logger.warning(f"RapidOCR failed, falling back to Tesseract: {e}")

        # Fallback to Tesseract
        if OCR_AVAILABLE:
            try:
                image = Image.open(file_path)
                text = pytesseract.image_to_string(image)
                logger.info(f"Tesseract OCR extracted {len(text)} characters from {file_path}")
                return text.strip()
            except Exception as e:
                logger.error(f"Tesseract OCR extraction failed: {e}")

        return ""

    def _extract_text_from_pdf(self, pdf_path: str) -> str:
        """Extract text from PDF using PyMuPDF with RapidOCR fallback for scanned pages."""
        global RAPIDOCR_ENGINE

        if not PDF_AVAILABLE:
            logger.warning("PDF extraction not available")
            return ""

        try:
            doc = fitz.open(pdf_path)
            text_parts = []

            for page_num, page in enumerate(doc):
                page_text = page.get_text()

                if page_text.strip() and len(page_text.strip()) > 50:
                    # Good text extraction
                    text_parts.append(page_text)
                else:
                    # Scanned page - use OCR
                    logger.info(f"Page {page_num + 1} appears scanned, using OCR")
                    # Higher resolution (2x) for good OCR quality
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

                    # Save temp image for OCR
                    import tempfile
                    temp_path = os.path.join(tempfile.gettempdir(), f"pdf_page_{page_num}.png")
                    img.save(temp_path, quality=95)

                    # Try RapidOCR first (fast and high quality)
                    if RAPIDOCR_AVAILABLE:
                        try:
                            if RAPIDOCR_ENGINE is None:
                                RAPIDOCR_ENGINE = RapidOCR()
                            result, _ = RAPIDOCR_ENGINE(temp_path)
                            if result:
                                texts = [item[1] for item in result]
                                ocr_text = "\n".join(texts)
                                if ocr_text.strip():
                                    text_parts.append(ocr_text)
                                    continue
                        except Exception as e:
                            logger.warning(f"RapidOCR failed on PDF page: {e}")

                    # Fallback to Tesseract
                    if OCR_AVAILABLE:
                        ocr_text = pytesseract.image_to_string(img)
                        if ocr_text.strip():
                            text_parts.append(ocr_text)

            doc.close()
            full_text = "\n".join(text_parts)
            logger.info(f"PDF extracted {len(full_text)} characters from {pdf_path}")
            return full_text.strip()

        except Exception as e:
            logger.error(f"PDF extraction failed: {e}")
            return ""

    def _get_image_description(self, image_path: str) -> str:
        """Get basic image metadata."""
        try:
            if OCR_AVAILABLE:
                image = Image.open(image_path)
                return f"Image: {image.format}, {image.size[0]}x{image.size[1]} pixels, {image.mode} mode"
            return ""
        except Exception:
            return ""

    async def analyze_document(self, file_path: str, use_autogen: bool = True, mode: str = "deep", progress_callback=None) -> Dict[str, Any]:
        """
        Analyze a document/image and extract insurance-relevant information.
        Uses OCR to extract text, then AutoGen multi-agent system for quality analysis.

        Args:
            file_path: Path to the document file
            use_autogen: If True, use AutoGen multi-agent processing (recommended for quality)
            mode: Analysis mode - 'quick', 'go_no_go', or 'deep'
            progress_callback: Optional async callback for progress updates
        """
        try:
            # Step 1: Extract text from image using OCR
            extracted_text = self._extract_text_ocr(file_path)
            image_desc = self._get_image_description(file_path)

            if not extracted_text:
                logger.info("No text extracted from image, returning basic analysis")
                return self._generate_fallback_analysis(file_path, "No text found in document")

            logger.info(f"Extracted text preview: {extracted_text[:200]}...")

            # Step 2: Use AutoGen multi-agent processing (uses Bedrock, not MiniMax)
            if use_autogen:
                try:
                    from app.services.autogen_processor import autogen_processor, AnalysisMode
                    # Map string mode to AnalysisMode enum
                    mode_map = {"quick": AnalysisMode.QUICK, "go_no_go": AnalysisMode.GO_NO_GO, "deep": AnalysisMode.DEEP}
                    analysis_mode = mode_map.get(mode.lower(), AnalysisMode.DEEP)
                    logger.info(f"Using AutoGen multi-agent processor with mode: {analysis_mode.value}")
                    return await autogen_processor.process_document(extracted_text, image_desc, mode=analysis_mode, progress_callback=progress_callback)
                except ImportError as e:
                    logger.warning(f"AutoGen not available: {e}, falling back to standard processing")
                except Exception as e:
                    logger.error(f"AutoGen processing failed: {e}, falling back to standard processing")

            # Fallback: Standard single-pass analysis via Bedrock
            initial_analysis = await self._analyze_with_bedrock(extracted_text, image_desc, file_path)

            # Handle None response from analysis
            if initial_analysis is None:
                logger.error("Analysis returned None, using fallback")
                return self._generate_fallback_analysis(file_path, "Analysis returned no result")

            # Quality validation pass
            if initial_analysis.get("is_valid_insurance_doc", True):
                validated_analysis = await self._validate_and_enhance(initial_analysis, extracted_text)
                return validated_analysis

            return initial_analysis

        except Exception as e:
            logger.error(f"Document analysis error: {str(e)}")
            return self._generate_fallback_analysis(file_path, str(e))

    async def _validate_and_enhance(self, analysis: Dict[str, Any], original_text: str) -> Dict[str, Any]:
        """Second pass validation to improve analysis quality (autogen-style)."""
        try:
            validation_prompt = f"""You are a senior Lloyd's insurance underwriter validating an AI-extracted analysis.
Review the extraction below and IMPROVE it if needed. Focus on:
1. Accurate company names (not app/UI names)
2. Correct risk type classification
3. Realistic premium/sum insured values
4. Professional risk factor identification

Current extraction:
{json.dumps(analysis, indent=2, default=str)}

Original document text (first 2000 chars):
{original_text[:2000]}

If the extraction looks correct, return it unchanged.
If improvements are needed, return the corrected JSON.
RESPOND ONLY WITH VALID JSON."""

            messages = [
                {"role": "system", "content": "You are a Lloyd's underwriter validating insurance document extractions. Return only JSON."},
                {"role": "user", "content": validation_prompt}
            ]

            content = await self._bedrock.chat(
                messages=messages,
                temperature=0.05,
                max_tokens=2000,
            )

            if content:
                try:
                    if "```json" in content:
                        content = content.split("```json")[1].split("```")[0]
                    elif "```" in content:
                        for part in content.split("```"):
                            if "{" in part:
                                content = part
                                break

                    validated = json.loads(content.strip())
                    validated["quality_validated"] = True
                    return validated
                except:
                    analysis["quality_validated"] = False
                    return analysis

            return analysis

        except Exception as e:
            logger.error(f"Validation error: {e}")
            analysis["quality_validated"] = False
            return analysis

    async def _analyze_with_bedrock(self, text: str, image_desc: str, file_path: str) -> Dict[str, Any]:
        """Analyze extracted text with AWS Bedrock Claude."""

        system_prompt = """You are an expert insurance underwriter and document analyst.
Analyze the text extracted from a document (via OCR) and extract ALL relevant insurance information.

IMPORTANT: First determine if this is a valid insurance document. Insurance documents include:
- Policy documents, slips, certificates
- Quotes, proposals, submissions
- Loss runs, claims reports
- Financial statements for underwriting
- Risk surveys, inspection reports
- Business contracts with indemnity clauses

If the document appears to be:
- A screenshot of an app/website
- Random text unrelated to insurance
- Marketing material
- User interface elements
Then set confidence_score to 0.1 and document_type to "Not Insurance Document".

You MUST respond with ONLY a valid JSON object (no markdown, no extra text, just JSON):
{
    "company_name": "Name of the insured company/person or null",
    "risk_type": "Type of insurance (Property, Liability, Marine, Cyber, etc.) or null",
    "industry": "Industry sector or null",
    "location": "Address or location or null",
    "territory": "Country/region or null",
    "sum_insured": null,
    "premium": null,
    "deductible": null,
    "inception_date": null,
    "expiry_date": null,
    "coverage_details": "Summary of coverage or what the document is about",
    "risk_factors": ["List of identified risk factors from the text"],
    "document_type": "Type of document (Slip, Policy, Certificate, Quote, Invoice, Letter, Not Insurance Document, etc.)",
    "confidence_score": 0.0 to 1.0,
    "is_valid_insurance_doc": true or false
}

Extract real data from the text. For non-insurance documents, set is_valid_insurance_doc to false and confidence_score below 0.2."""

        user_message = f"""Analyze this document text (extracted via OCR from an image):

--- DOCUMENT TEXT START ---
{text[:4000]}
--- DOCUMENT TEXT END ---

{image_desc}

Extract all insurance-relevant information and return ONLY valid JSON."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]

        try:
            logger.info("Calling Bedrock Claude for text analysis")
            content = await self._bedrock.chat(
                messages=messages,
                temperature=0.1,
                max_tokens=2000,
            )

            if content:
                return self._parse_response(content, text)
            else:
                return self._generate_fallback_analysis(file_path, "Empty AI response")

        except Exception as e:
            logger.error(f"Bedrock API call failed: {e}")
            return self._generate_fallback_analysis(file_path, str(e))

    def _parse_response(self, content: str, original_text: str) -> Dict[str, Any]:
        """Parse AI response into structured data."""
        try:
            content = content.strip()

            # Extract JSON from markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                parts = content.split("```")
                for part in parts:
                    if "{" in part and "}" in part:
                        content = part
                        break

            content = content.strip()
            extracted_data = json.loads(content)
            extracted_data["extraction_successful"] = True
            extracted_data["ocr_text_preview"] = original_text[:500] if original_text else ""
            return extracted_data

        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}, content: {content[:200]}")
            return {
                "extraction_successful": True,
                "company_name": "See Document",
                "risk_type": "Manual Review Required",
                "coverage_details": content[:500] if content else "AI analysis completed",
                "risk_factors": [],
                "document_type": "Document",
                "confidence_score": 0.3,
                "ocr_text_preview": original_text[:500] if original_text else "",
                "raw_analysis": content[:1000]
            }

    async def analyze_multiple_documents(self, file_paths: List[str], mode: str = "deep", progress_callback=None) -> Dict[str, Any]:
        """
        Analyze multiple documents - extract OCR from ALL first, then run agents on combined data.

        Flow:
        1. Extract OCR text from ALL documents first
        2. Run DocumentClassifier on combined text
        3. Run DataExtractor on combined text
        4. Run RiskAnalyst on combined text
        5. etc. through all agents

        This ensures each agent has the complete picture across all documents.
        """
        all_ocr_texts = []
        all_entities = []
        total_documents = len(file_paths)

        # =========================================================
        # PHASE 1: Extract OCR text from ALL documents first
        # =========================================================
        for i, file_path in enumerate(file_paths):
            current_doc = i + 1
            doc_name = Path(file_path).name
            docs_remaining = total_documents - current_doc

            # Send progress for OCR extraction phase
            if progress_callback:
                ocr_progress = (i / total_documents) * 10  # OCR phase is 0-10%
                await progress_callback({
                    "steps": [{
                        "agent": "DocumentLoader",
                        "description": f"Extracting text from document {current_doc} of {total_documents}",
                        "status": "running"
                    }],
                    "current_document": current_doc,
                    "total_documents": total_documents,
                    "documents_remaining": docs_remaining,
                    "document_name": doc_name,
                    "current_agent": "DocumentLoader",
                    "overall_progress": ocr_progress,
                    "live_findings": [
                        {"label": "Phase", "value": "Document Loading", "type": "info", "agent": "DocumentLoader"},
                        {"label": "Document", "value": f"{current_doc} of {total_documents}: {doc_name}", "type": "info", "agent": "DocumentLoader"},
                        {"label": "Action", "value": "Running OCR text extraction...", "type": "info", "agent": "DocumentLoader"}
                    ]
                })

            # Extract OCR text (no agent processing yet)
            ocr_text = self._extract_text_ocr(file_path)

            if ocr_text:
                all_ocr_texts.append(f"--- Document {current_doc}: {doc_name} ---\n{ocr_text}")

                # Add finding for extracted text
                if progress_callback:
                    char_count = len(ocr_text)
                    await progress_callback({
                        "steps": [{
                            "agent": "DocumentLoader",
                            "description": f"Extracted {char_count:,} characters from {doc_name}",
                            "status": "running"
                        }],
                        "current_document": current_doc,
                        "total_documents": total_documents,
                        "documents_remaining": docs_remaining,
                        "document_name": doc_name,
                        "current_agent": "DocumentLoader",
                        "overall_progress": ((i + 1) / total_documents) * 10,
                        "live_findings": [
                            {"label": "Document", "value": doc_name, "type": "success", "agent": "DocumentLoader"},
                            {"label": "Characters", "value": f"{char_count:,}", "type": "info", "agent": "DocumentLoader"},
                            {"label": "Preview", "value": ocr_text[:100] + "...", "type": "info", "agent": "DocumentLoader"}
                        ]
                    })
            else:
                logger.warning(f"No text extracted from {doc_name}")

        # Combine all OCR texts
        combined_text = "\n\n".join(all_ocr_texts)

        if not combined_text:
            logger.warning("No text extracted from any documents")
            return self._generate_fallback_analysis(file_paths[0] if file_paths else "", "No text extracted from documents")

        logger.info(f"Combined OCR text from {total_documents} documents: {len(combined_text):,} characters")

        # =========================================================
        # PHASE 2: Run agents on combined document data
        # Progress callback wrapper that shows agent progress (10-100%)
        # =========================================================
        async def agent_progress_callback(progress_state):
            if not progress_callback:
                return

            if isinstance(progress_state, dict):
                steps = progress_state.get("steps", [])
                current_step = steps[-1] if steps else {}
                agent_name = current_step.get("agent", "Processing")
                agent_desc = current_step.get("description", "")
                live_findings = progress_state.get("live_findings", [])

                # Agent phase is 10-100%, so scale agent_progress accordingly
                agent_progress = progress_state.get("agent_progress", 0)
                overall_progress = 10 + (agent_progress * 0.9)  # 10% + 90% of agent progress
            else:
                agent_name = "Processing"
                agent_desc = ""
                overall_progress = 50
                live_findings = []

            # Send progress with all documents context
            await progress_callback({
                "steps": [{
                    "agent": agent_name,
                    "description": agent_desc,
                    "status": "running"
                }],
                "current_document": total_documents,  # All docs loaded
                "total_documents": total_documents,
                "documents_remaining": 0,  # All loaded
                "document_name": f"All {total_documents} documents",
                "current_agent": agent_name,
                "overall_progress": min(99, overall_progress),
                "live_findings": live_findings
            })

        # Send progress: starting agent processing
        if progress_callback:
            await progress_callback({
                "steps": [{
                    "agent": "AgentPipeline",
                    "description": f"Starting analysis on {total_documents} documents ({len(combined_text):,} characters)",
                    "status": "running"
                }],
                "current_document": total_documents,
                "total_documents": total_documents,
                "documents_remaining": 0,
                "document_name": f"All {total_documents} documents",
                "current_agent": "AgentPipeline",
                "overall_progress": 10,
                "live_findings": [
                    {"label": "Documents Loaded", "value": str(total_documents), "type": "success", "agent": "Pipeline"},
                    {"label": "Total Characters", "value": f"{len(combined_text):,}", "type": "info", "agent": "Pipeline"},
                    {"label": "Status", "value": "Starting agent analysis...", "type": "info", "agent": "Pipeline"}
                ]
            })

        # Run AutoGen multi-agent processing on combined text
        try:
            from app.services.autogen_processor import autogen_processor, AnalysisMode
            mode_map = {"quick": AnalysisMode.QUICK, "go_no_go": AnalysisMode.GO_NO_GO, "deep": AnalysisMode.DEEP}
            analysis_mode = mode_map.get(mode.lower(), AnalysisMode.DEEP)

            image_desc = f"Combined analysis of {total_documents} documents"
            result = await autogen_processor.process_document(
                combined_text,
                image_desc,
                mode=analysis_mode,
                progress_callback=agent_progress_callback
            )
        except Exception as e:
            logger.error(f"AutoGen processing failed: {e}")
            result = self._generate_fallback_analysis(file_paths[0] if file_paths else "", str(e))

        # Store combined OCR text and document count
        result["ocr_extracted_text"] = combined_text
        result["ocr_text_preview"] = combined_text[:500] if combined_text else ""
        result["documents_analyzed"] = total_documents

        # Extract entities from the result for sanctions screening
        agent_results = result.get("agent_results", {})
        extractor = agent_results.get("extractor", {})
        if extractor.get("insured", {}).get("name"):
            all_entities.append({"name": extractor["insured"]["name"], "type": "LegalEntity", "role": "insured"})
        if extractor.get("broker", {}).get("name"):
            all_entities.append({"name": extractor["broker"]["name"], "type": "Organization", "role": "broker"})
        if result.get("company_name") and result["company_name"] not in [e["name"] for e in all_entities]:
            all_entities.append({"name": result["company_name"], "type": "LegalEntity", "role": "insured"})

        result["extracted_entities"] = all_entities

        return result

    def _generate_fallback_analysis(self, file_path: str, error_msg: str = None) -> Dict[str, Any]:
        """Generate fallback result when analysis fails."""
        filename = Path(file_path).name
        try:
            file_size = os.path.getsize(file_path) / 1024  # KB
        except:
            file_size = 0

        return {
            "company_name": "Document Received",
            "risk_type": "Pending Review",
            "industry": None,
            "location": None,
            "territory": None,
            "sum_insured": None,
            "premium": None,
            "deductible": None,
            "inception_date": None,
            "expiry_date": None,
            "coverage_details": f"Document '{filename}' ({file_size:.1f} KB) uploaded. {error_msg or 'Ready for review.'}",
            "risk_factors": [],
            "document_type": "Uploaded Document",
            "confidence_score": 0.1,
            "extraction_successful": True,
            "note": "Manual review recommended"
        }


# Singleton instance
document_processor = DocumentProcessor()
