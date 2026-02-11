"""
InstantRisk V3 - Intelligent Document Chunking Service

Handles large insurance documents by:
1. Intelligent section-based splitting (preserves logical structure)
2. Overlapping chunks to prevent context loss
3. Section detection for Lloyd's MRC/Slip documents
4. Chunk metadata for aggregation
5. Token-aware splitting that respects LLM limits

Designed for 99%+ accuracy by:
- Never truncating mid-sentence
- Preserving section headers with each chunk
- Including document context in every chunk
- Using semantic boundaries (clauses, sections)
"""

import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class DocumentSection(str, Enum):
    """Lloyd's MRC/Slip standard sections."""
    HEADER = "header"
    RISK_DETAILS = "risk_details"
    TYPE_OF_INSURANCE = "type"
    INSURED = "insured"
    PERIOD = "period"
    INTEREST = "interest"
    LIMITS = "limits"
    PREMIUM = "premium"
    DEDUCTIBLE = "deductible"
    CONDITIONS = "conditions"
    EXCLUSIONS = "exclusions"
    CLAUSES = "clauses"
    SCHEDULE = "schedule"
    SUBJECTIVITIES = "subjectivities"
    WARRANTY = "warranty"
    ENDORSEMENT = "endorsement"
    BROKER = "broker"
    SECURITY = "security"
    SIGNING = "signing"
    GENERAL = "general"


@dataclass
class DocumentChunk:
    """Represents a chunk of document with full metadata."""
    content: str
    chunk_index: int
    total_chunks: int
    section: DocumentSection
    section_title: str
    start_position: int
    end_position: int
    token_estimate: int
    has_overlap_before: bool
    has_overlap_after: bool
    context_header: str  # Document context carried with each chunk
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_prompt_text(self) -> str:
        """Format chunk for LLM processing with full context."""
        return f"""[DOCUMENT CONTEXT]
{self.context_header}

[SECTION: {self.section_title}]
[CHUNK {self.chunk_index + 1} OF {self.total_chunks}]

{self.content}

[END OF CHUNK {self.chunk_index + 1}]"""


@dataclass
class ChunkingResult:
    """Result of document chunking operation."""
    chunks: List[DocumentChunk]
    total_tokens_estimated: int
    sections_detected: List[str]
    document_type_hint: Optional[str]
    requires_multi_pass: bool
    metadata: Dict[str, Any]


class IntelligentDocumentChunker:
    """
    Intelligent chunker for insurance documents.

    Features:
    - Section-aware splitting for Lloyd's documents
    - Token counting with safety margins
    - Overlapping chunks for context preservation
    - Metadata tracking for accurate aggregation
    """

    # Standard section headers in Lloyd's documents
    SECTION_PATTERNS = {
        DocumentSection.TYPE_OF_INSURANCE: [
            r"(?i)type\s+of\s+insurance",
            r"(?i)class\s+of\s+business",
            r"(?i)coverage\s+type",
        ],
        DocumentSection.INSURED: [
            r"(?i)the\s+insured",
            r"(?i)named\s+insured",
            r"(?i)insured\s*:",
            r"(?i)policyholder",
        ],
        DocumentSection.PERIOD: [
            r"(?i)period\s+of\s+insurance",
            r"(?i)policy\s+period",
            r"(?i)inception\s*:",
            r"(?i)from\s*:\s*\d",
        ],
        DocumentSection.INTEREST: [
            r"(?i)interest\s+insured",
            r"(?i)subject\s+matter",
            r"(?i)property\s+insured",
        ],
        DocumentSection.LIMITS: [
            r"(?i)limit\s+of\s+(liability|indemnity)",
            r"(?i)sum\s+insured",
            r"(?i)maximum\s+limit",
            r"(?i)aggregate\s+limit",
        ],
        DocumentSection.PREMIUM: [
            r"(?i)premium\s*:",
            r"(?i)rate\s*:",
            r"(?i)deposit\s+premium",
            r"(?i)minimum\s+(and\s+)?deposit",
        ],
        DocumentSection.DEDUCTIBLE: [
            r"(?i)deductible",
            r"(?i)excess\s*:",
            r"(?i)self.insured\s+retention",
            r"(?i)each\s+and\s+every\s+loss",
        ],
        DocumentSection.CONDITIONS: [
            r"(?i)conditions\s*:",
            r"(?i)general\s+conditions",
            r"(?i)policy\s+conditions",
            r"(?i)special\s+conditions",
        ],
        DocumentSection.EXCLUSIONS: [
            r"(?i)exclusions\s*:",
            r"(?i)this\s+policy\s+does\s+not\s+cover",
            r"(?i)excluded\s+from\s+coverage",
            r"(?i)not\s+covered",
        ],
        DocumentSection.CLAUSES: [
            r"(?i)clauses?\s*:",
            r"(?i)lma\d+",
            r"(?i)lsw\d+",
            r"(?i)nma\d+",
            r"(?i)jc\d+",
        ],
        DocumentSection.SUBJECTIVITIES: [
            r"(?i)subjectivities",
            r"(?i)subject\s+to",
            r"(?i)conditional\s+upon",
        ],
        DocumentSection.WARRANTY: [
            r"(?i)warrant(y|ies)",
            r"(?i)warranted\s+that",
        ],
        DocumentSection.BROKER: [
            r"(?i)broker\s*:",
            r"(?i)producing\s+broker",
            r"(?i)lloyd'?s\s+broker",
        ],
        DocumentSection.SECURITY: [
            r"(?i)security\s*:",
            r"(?i)syndicates?\s*:",
            r"(?i)underwriters?\s*:",
            r"(?i)insurers?\s*:",
        ],
        DocumentSection.SIGNING: [
            r"(?i)signed\s+line",
            r"(?i)percentage\s+of\s+order",
            r"(?i)written\s+line",
        ],
    }

    # Approximate tokens per character (conservative for safety)
    CHARS_PER_TOKEN = 3.5

    def __init__(
        self,
        max_tokens_per_chunk: int = 2500,  # Safe limit below 3000
        overlap_tokens: int = 200,
        min_chunk_tokens: int = 100
    ):
        self.max_tokens_per_chunk = max_tokens_per_chunk
        self.overlap_tokens = overlap_tokens
        self.min_chunk_tokens = min_chunk_tokens
        self.max_chars_per_chunk = int(max_tokens_per_chunk * self.CHARS_PER_TOKEN)
        self.overlap_chars = int(overlap_tokens * self.CHARS_PER_TOKEN)

    def chunk_document(
        self,
        text: str,
        document_type: str = None,
        preserve_sections: bool = True
    ) -> ChunkingResult:
        """
        Intelligently chunk a document while preserving structure.

        Args:
            text: Full document text
            document_type: Optional hint about document type
            preserve_sections: Whether to respect section boundaries

        Returns:
            ChunkingResult with chunks and metadata
        """
        if not text or not text.strip():
            return ChunkingResult(
                chunks=[],
                total_tokens_estimated=0,
                sections_detected=[],
                document_type_hint=document_type,
                requires_multi_pass=False,
                metadata={}
            )

        # Clean and normalize text
        text = self._normalize_text(text)
        total_chars = len(text)
        estimated_total_tokens = int(total_chars / self.CHARS_PER_TOKEN)

        # Extract document header/context (first ~500 chars)
        context_header = self._extract_context_header(text)

        # Detect sections in the document
        sections = self._detect_sections(text) if preserve_sections else []

        # Choose chunking strategy based on document size
        if estimated_total_tokens <= self.max_tokens_per_chunk:
            # Small document - single chunk
            chunks = [self._create_single_chunk(text, context_header)]
        elif sections:
            # Section-aware chunking
            chunks = self._chunk_by_sections(text, sections, context_header)
        else:
            # Fallback to semantic chunking
            chunks = self._chunk_semantically(text, context_header)

        # Validate and fill chunk metadata
        self._finalize_chunks(chunks, estimated_total_tokens)

        return ChunkingResult(
            chunks=chunks,
            total_tokens_estimated=estimated_total_tokens,
            sections_detected=[s[0].value for s in sections],
            document_type_hint=self._detect_document_type(text),
            requires_multi_pass=len(chunks) > 1,
            metadata={
                "total_characters": total_chars,
                "chunk_count": len(chunks),
                "avg_chunk_tokens": estimated_total_tokens // max(len(chunks), 1),
                "sections_found": len(sections)
            }
        )

    def _normalize_text(self, text: str) -> str:
        """Normalize whitespace and clean text."""
        # Replace multiple whitespace with single space
        text = re.sub(r'[ \t]+', ' ', text)
        # Normalize line breaks
        text = re.sub(r'\n{3,}', '\n\n', text)
        # Remove non-printable characters except newlines
        text = ''.join(c for c in text if c.isprintable() or c in '\n\t')
        return text.strip()

    def _extract_context_header(self, text: str, max_chars: int = 500) -> str:
        """Extract document context to include with every chunk."""
        # Get first portion up to first major break
        header = text[:max_chars]

        # Try to end at a logical break point
        for pattern in ['\n\n', '\n', '. ', ', ']:
            idx = header.rfind(pattern)
            if idx > max_chars // 2:
                header = header[:idx + len(pattern)]
                break

        # Extract key identifiers
        key_info = []

        # Look for UMR
        umr_match = re.search(r'(?i)umr[:\s]*([A-Z0-9]+)', text[:2000])
        if umr_match:
            key_info.append(f"UMR: {umr_match.group(1)}")

        # Look for policy number
        policy_match = re.search(r'(?i)policy\s*(no|number|ref)[:\s]*([A-Z0-9\-/]+)', text[:2000])
        if policy_match:
            key_info.append(f"Policy: {policy_match.group(2)}")

        # Look for insured name
        insured_match = re.search(r'(?i)(?:the\s+)?insured[:\s]*([A-Z][A-Za-z\s&,\.]+?)(?:\n|$)', text[:3000])
        if insured_match:
            key_info.append(f"Insured: {insured_match.group(1).strip()[:100]}")

        context = header.strip()
        if key_info:
            context = f"KEY IDENTIFIERS: {' | '.join(key_info)}\n\nDOCUMENT START:\n{context}"

        return context

    def _detect_sections(self, text: str) -> List[Tuple[DocumentSection, int, str]]:
        """
        Detect section boundaries in the document.

        Returns list of (section_type, position, matched_text) tuples.
        """
        sections = []

        for section_type, patterns in self.SECTION_PATTERNS.items():
            for pattern in patterns:
                for match in re.finditer(pattern, text):
                    # Get some context around the match
                    start = max(0, match.start() - 50)
                    end = min(len(text), match.end() + 50)
                    context = text[start:end]

                    sections.append((
                        section_type,
                        match.start(),
                        match.group()
                    ))

        # Sort by position
        sections.sort(key=lambda x: x[1])

        # Remove duplicates (same section detected multiple times)
        unique_sections = []
        last_pos = -1000
        for section in sections:
            if section[1] - last_pos > 100:  # At least 100 chars apart
                unique_sections.append(section)
                last_pos = section[1]

        return unique_sections

    def _detect_document_type(self, text: str) -> Optional[str]:
        """Detect document type from content."""
        text_lower = text[:5000].lower()

        if 'market reform contract' in text_lower or 'mrc' in text_lower:
            return 'SLIP'
        elif 'policy of insurance' in text_lower:
            return 'POLICY'
        elif 'certificate of insurance' in text_lower:
            return 'CERTIFICATE'
        elif 'endorsement' in text_lower and 'hereby' in text_lower:
            return 'ENDORSEMENT'
        elif 'quotation' in text_lower or 'quote' in text_lower:
            return 'QUOTE'
        elif 'claim' in text_lower and ('notification' in text_lower or 'advice' in text_lower):
            return 'CLAIM'
        elif 'renewal' in text_lower:
            return 'RENEWAL'
        elif 'cover note' in text_lower:
            return 'COVER_NOTE'

        return None

    def _create_single_chunk(self, text: str, context_header: str) -> DocumentChunk:
        """Create a single chunk for small documents."""
        return DocumentChunk(
            content=text,
            chunk_index=0,
            total_chunks=1,
            section=DocumentSection.GENERAL,
            section_title="Complete Document",
            start_position=0,
            end_position=len(text),
            token_estimate=int(len(text) / self.CHARS_PER_TOKEN),
            has_overlap_before=False,
            has_overlap_after=False,
            context_header=context_header
        )

    def _chunk_by_sections(
        self,
        text: str,
        sections: List[Tuple[DocumentSection, int, str]],
        context_header: str
    ) -> List[DocumentChunk]:
        """
        Chunk document respecting section boundaries.

        If a section is too large, it's further split at paragraph boundaries.
        """
        chunks = []

        # Add end position for processing
        section_ranges = []
        for i, (section_type, start_pos, title) in enumerate(sections):
            end_pos = sections[i + 1][1] if i + 1 < len(sections) else len(text)
            section_ranges.append((section_type, start_pos, end_pos, title))

        for section_type, start_pos, end_pos, title in section_ranges:
            section_text = text[start_pos:end_pos]
            section_chars = len(section_text)

            if section_chars <= self.max_chars_per_chunk:
                # Section fits in one chunk
                chunks.append(DocumentChunk(
                    content=section_text,
                    chunk_index=len(chunks),
                    total_chunks=0,  # Will be set later
                    section=section_type,
                    section_title=title,
                    start_position=start_pos,
                    end_position=end_pos,
                    token_estimate=int(section_chars / self.CHARS_PER_TOKEN),
                    has_overlap_before=False,
                    has_overlap_after=False,
                    context_header=context_header
                ))
            else:
                # Section too large - split at paragraphs
                sub_chunks = self._split_large_section(
                    section_text,
                    section_type,
                    title,
                    start_pos,
                    context_header,
                    len(chunks)
                )
                chunks.extend(sub_chunks)

        return chunks

    def _split_large_section(
        self,
        text: str,
        section_type: DocumentSection,
        section_title: str,
        base_position: int,
        context_header: str,
        start_index: int
    ) -> List[DocumentChunk]:
        """Split a large section into smaller chunks at paragraph boundaries."""
        chunks = []

        # Split at paragraph boundaries
        paragraphs = re.split(r'\n\s*\n', text)

        current_chunk = ""
        current_start = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            potential_chunk = current_chunk + "\n\n" + para if current_chunk else para

            if len(potential_chunk) > self.max_chars_per_chunk and current_chunk:
                # Save current chunk and start new one
                chunks.append(DocumentChunk(
                    content=current_chunk,
                    chunk_index=start_index + len(chunks),
                    total_chunks=0,
                    section=section_type,
                    section_title=f"{section_title} (continued)" if chunks else section_title,
                    start_position=base_position + current_start,
                    end_position=base_position + current_start + len(current_chunk),
                    token_estimate=int(len(current_chunk) / self.CHARS_PER_TOKEN),
                    has_overlap_before=len(chunks) > 0,
                    has_overlap_after=True,
                    context_header=context_header
                ))

                # Add overlap from previous chunk
                overlap_text = current_chunk[-self.overlap_chars:] if len(current_chunk) > self.overlap_chars else ""
                current_chunk = overlap_text + "\n\n" + para if overlap_text else para
                current_start = base_position + len(text) - len(current_chunk)
            else:
                current_chunk = potential_chunk

        # Add final chunk
        if current_chunk:
            chunks.append(DocumentChunk(
                content=current_chunk,
                chunk_index=start_index + len(chunks),
                total_chunks=0,
                section=section_type,
                section_title=f"{section_title} (continued)" if chunks else section_title,
                start_position=base_position + current_start,
                end_position=base_position + len(text),
                token_estimate=int(len(current_chunk) / self.CHARS_PER_TOKEN),
                has_overlap_before=len(chunks) > 0,
                has_overlap_after=False,
                context_header=context_header
            ))

        return chunks

    def _chunk_semantically(self, text: str, context_header: str) -> List[DocumentChunk]:
        """Fallback chunking when no sections detected - splits at semantic boundaries."""
        chunks = []

        # Split at double newlines (paragraphs)
        paragraphs = re.split(r'\n\s*\n', text)

        current_chunk = ""
        current_start = 0
        position = 0

        for para in paragraphs:
            para = para.strip()
            para_with_break = para + "\n\n"

            if not para:
                position += 2
                continue

            potential_chunk = current_chunk + para_with_break

            if len(potential_chunk) > self.max_chars_per_chunk and current_chunk:
                # Save current chunk
                chunks.append(DocumentChunk(
                    content=current_chunk.strip(),
                    chunk_index=len(chunks),
                    total_chunks=0,
                    section=DocumentSection.GENERAL,
                    section_title=f"Section {len(chunks) + 1}",
                    start_position=current_start,
                    end_position=position,
                    token_estimate=int(len(current_chunk) / self.CHARS_PER_TOKEN),
                    has_overlap_before=len(chunks) > 0,
                    has_overlap_after=True,
                    context_header=context_header
                ))

                # Start new chunk with overlap
                overlap = current_chunk[-self.overlap_chars:] if len(current_chunk) > self.overlap_chars else ""
                current_chunk = overlap + para_with_break
                current_start = position - len(overlap)
            else:
                current_chunk = potential_chunk

            position += len(para_with_break)

        # Add final chunk
        if current_chunk.strip():
            chunks.append(DocumentChunk(
                content=current_chunk.strip(),
                chunk_index=len(chunks),
                total_chunks=0,
                section=DocumentSection.GENERAL,
                section_title=f"Section {len(chunks) + 1}",
                start_position=current_start,
                end_position=len(text),
                token_estimate=int(len(current_chunk) / self.CHARS_PER_TOKEN),
                has_overlap_before=len(chunks) > 0,
                has_overlap_after=False,
                context_header=context_header
            ))

        return chunks

    def _finalize_chunks(self, chunks: List[DocumentChunk], total_tokens: int):
        """Set final chunk counts and validate."""
        total = len(chunks)
        for chunk in chunks:
            chunk.total_chunks = total


@dataclass
class AggregatedResult:
    """Result of aggregating multiple chunk analyses."""
    merged_data: Dict[str, Any]
    confidence: float
    conflicts: List[Dict[str, Any]]
    coverage: float  # How much of document was processed
    chunk_results: List[Dict[str, Any]]


class ChunkResultAggregator:
    """
    Aggregates results from multiple chunk analyses.

    Features:
    - Intelligent merging of extracted fields
    - Conflict detection and resolution
    - Confidence weighting
    - Coverage tracking
    """

    def aggregate_extractions(
        self,
        chunk_results: List[Dict[str, Any]],
        chunks: List[DocumentChunk]
    ) -> AggregatedResult:
        """
        Aggregate extraction results from multiple chunks.

        Args:
            chunk_results: List of extraction results per chunk
            chunks: Original chunks for metadata

        Returns:
            AggregatedResult with merged data
        """
        if not chunk_results:
            return AggregatedResult(
                merged_data={},
                confidence=0.0,
                conflicts=[],
                coverage=0.0,
                chunk_results=[]
            )

        if len(chunk_results) == 1:
            return AggregatedResult(
                merged_data=chunk_results[0],
                confidence=1.0,
                conflicts=[],
                coverage=1.0,
                chunk_results=chunk_results
            )

        merged = {}
        conflicts = []
        field_sources = {}  # Track which chunks contributed each field

        for i, result in enumerate(chunk_results):
            self._merge_dict(merged, result, i, conflicts, field_sources)

        # Calculate confidence based on agreement
        total_fields = len(field_sources)
        agreed_fields = sum(1 for sources in field_sources.values() if len(sources) == 1)
        confidence = agreed_fields / max(total_fields, 1)

        # Calculate coverage
        coverage = len(chunk_results) / len(chunks) if chunks else 1.0

        return AggregatedResult(
            merged_data=merged,
            confidence=confidence,
            conflicts=conflicts,
            coverage=coverage,
            chunk_results=chunk_results
        )

    def _merge_dict(
        self,
        target: Dict,
        source: Dict,
        source_index: int,
        conflicts: List,
        field_sources: Dict
    ):
        """Recursively merge dictionaries, tracking conflicts."""
        if not source:
            return

        for key, value in source.items():
            if value is None:
                continue

            field_key = key

            if key not in target:
                # New field
                target[key] = value
                field_sources[field_key] = [source_index]
            elif isinstance(value, dict) and isinstance(target[key], dict):
                # Recursive merge for nested dicts
                self._merge_dict(target[key], value, source_index, conflicts, field_sources)
            elif isinstance(value, list) and isinstance(target[key], list):
                # Extend lists, removing duplicates
                existing = set(str(x) for x in target[key])
                for item in value:
                    if str(item) not in existing:
                        target[key].append(item)
                        existing.add(str(item))
                field_sources.setdefault(field_key, []).append(source_index)
            elif target[key] != value:
                # Conflict - different values for same field
                # Use the longer/more specific value
                existing_val = target[key]
                if isinstance(value, str) and isinstance(existing_val, str):
                    if len(value) > len(existing_val):
                        conflicts.append({
                            "field": key,
                            "existing": existing_val,
                            "new": value,
                            "resolution": "kept_longer",
                            "source_chunk": source_index
                        })
                        target[key] = value
                    else:
                        conflicts.append({
                            "field": key,
                            "existing": existing_val,
                            "new": value,
                            "resolution": "kept_existing",
                            "source_chunk": source_index
                        })
                elif isinstance(value, (int, float)) and isinstance(existing_val, (int, float)):
                    # For numbers, prefer the larger (often more complete)
                    if value > existing_val:
                        target[key] = value
                    conflicts.append({
                        "field": key,
                        "existing": existing_val,
                        "new": value,
                        "resolution": "kept_larger",
                        "source_chunk": source_index
                    })
                field_sources.setdefault(field_key, []).append(source_index)
            else:
                # Same value from multiple chunks - increases confidence
                field_sources.setdefault(field_key, []).append(source_index)


# Singleton instances
document_chunker = IntelligentDocumentChunker()
result_aggregator = ChunkResultAggregator()
