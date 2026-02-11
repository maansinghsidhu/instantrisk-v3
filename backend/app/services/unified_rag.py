"""
Unified RAG Service - Priority-based search across all knowledge sources.

Search priority chain:
1. User's uploaded training documents (per-user, highest priority)
2. ACORD standard clause library
3. CUAD contract understanding
4. JETech underwriting blocks
5. LEDGAR SEC contract provisions (60K)
6. MAUD merger agreement clauses (5K)
7. Insurance QA pairs (21K)
8. Global knowledge base (149K+ total records)

Returns results tagged with source tier for transparency.
"""

import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class UnifiedRAG:
    """Priority-based RAG search across all knowledge sources."""

    def __init__(self):
        self._qdrant_service = None
        self._rag_indexer = None

    @property
    def qdrant_service(self):
        if self._qdrant_service is None:
            from app.services.qdrant_service import qdrant_service
            self._qdrant_service = qdrant_service
        return self._qdrant_service

    @property
    def rag_indexer(self):
        if self._rag_indexer is None:
            from app.services.rag_indexer import rag_indexer
            self._rag_indexer = rag_indexer
        return self._rag_indexer

    async def search(
        self,
        query: str,
        user_id: Optional[str] = None,
        category: Optional[str] = None,
        top_k: int = 5,
        min_score: float = 0.3,
        source_tiers: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search across all knowledge sources with priority ordering.

        Args:
            query: Search query text.
            user_id: User ID for searching user-uploaded docs (tier 1).
            category: Optional category filter.
            top_k: Total number of results to return.
            min_score: Minimum similarity score threshold.
            source_tiers: Optional list of tiers to search. If None, search all.
                          Options: "user", "acord", "cuad", "jetech", "global"

        Returns:
            List of results with source attribution, ordered by priority then score.
        """
        all_results = []
        remaining = top_k

        # Define search tiers in priority order
        tiers = [
            ("user", self._search_user_docs),
            ("acord", self._search_acord),
            ("cuad", self._search_cuad),
            ("jetech", self._search_jetech),
            ("ledgar", self._search_ledgar),
            ("maud", self._search_maud),
            ("insurance_qa", self._search_insurance_qa),
            ("global", self._search_global),
        ]

        for tier_name, search_fn in tiers:
            if remaining <= 0:
                break

            if source_tiers and tier_name not in source_tiers:
                continue

            try:
                if tier_name == "user" and not user_id:
                    continue

                tier_results = await search_fn(
                    query=query,
                    user_id=user_id,
                    category=category,
                    limit=remaining,
                )

                for result in tier_results:
                    score = result.get("score", 0)
                    if score >= min_score:
                        result["source_tier"] = tier_name
                        result["source_label"] = _TIER_LABELS.get(tier_name, tier_name)
                        all_results.append(result)
                        remaining -= 1
                        if remaining <= 0:
                            break

            except Exception as e:
                logger.warning(f"Search tier '{tier_name}' failed: {e}")
                continue

        return all_results

    async def _search_user_docs(
        self, query: str, user_id: str = None, category: str = None, limit: int = 5
    ) -> List[Dict]:
        """Tier 1: Search user's uploaded training documents."""
        if not user_id:
            return []

        results = await self.qdrant_service.search_similar(
            query=query,
            user_id=user_id,
            limit=limit,
            category=category,
        )

        return [
            {
                "text": r.get("text", ""),
                "source": "user_upload",
                "filename": r.get("filename", ""),
                "category": r.get("category", ""),
                "doc_id": r.get("doc_id", ""),
                "score": r.get("score", 0),
            }
            for r in results
        ]

    async def _search_acord(
        self, query: str, user_id: str = None, category: str = None, limit: int = 5
    ) -> List[Dict]:
        """Tier 2: Search ACORD standard clause library."""
        results = self.rag_indexer.search(query=query, top_k=limit, doc_type="acord")
        return [
            {
                "text": r.get("text", ""),
                "source": "acord_standard",
                "category": r.get("category", ""),
                "name": r.get("name", ""),
                "score": r.get("score", 0),
            }
            for r in results
        ]

    async def _search_cuad(
        self, query: str, user_id: str = None, category: str = None, limit: int = 5
    ) -> List[Dict]:
        """Tier 3: Search CUAD contract clause understanding."""
        results = self.rag_indexer.search(query=query, top_k=limit, doc_type="cuad")
        return [
            {
                "text": r.get("text", ""),
                "source": "cuad",
                "category": r.get("category", ""),
                "score": r.get("score", 0),
            }
            for r in results
        ]

    async def _search_jetech(
        self, query: str, user_id: str = None, category: str = None, limit: int = 5
    ) -> List[Dict]:
        """Tier 4: Search JETech underwriting blocks."""
        results = self.rag_indexer.search(
            query=query, top_k=limit, doc_type="underwriting_block"
        )
        return [
            {
                "text": r.get("text", ""),
                "source": "jetech",
                "category": r.get("category", ""),
                "score": r.get("score", 0),
            }
            for r in results
        ]

    async def _search_ledgar(
        self, query: str, user_id: str = None, category: str = None, limit: int = 5
    ) -> List[Dict]:
        """Tier 5: Search LEDGAR SEC contract provisions (80K records)."""
        results = self.rag_indexer.search(query=query, top_k=limit, doc_type="ledgar")
        return [
            {
                "text": r.get("text", ""),
                "source": "ledgar",
                "category": r.get("category", ""),
                "score": r.get("score", 0),
            }
            for r in results
        ]

    async def _search_maud(
        self, query: str, user_id: str = None, category: str = None, limit: int = 5
    ) -> List[Dict]:
        """Tier 6: Search MAUD merger agreement clauses (25K records)."""
        results = self.rag_indexer.search(query=query, top_k=limit, doc_type="maud")
        return [
            {
                "text": r.get("text", ""),
                "source": "maud",
                "category": r.get("category", ""),
                "score": r.get("score", 0),
            }
            for r in results
        ]

    async def _search_insurance_qa(
        self, query: str, user_id: str = None, category: str = None, limit: int = 5
    ) -> List[Dict]:
        """Tier 7: Search Insurance QA pairs (21K records)."""
        results = self.rag_indexer.search(query=query, top_k=limit, doc_type="insurance_qa")
        return [
            {
                "text": r.get("text", ""),
                "source": "insurance_qa",
                "category": r.get("category", ""),
                "question": r.get("question", ""),
                "score": r.get("score", 0),
            }
            for r in results
        ]

    async def _search_global(
        self, query: str, user_id: str = None, category: str = None, limit: int = 5
    ) -> List[Dict]:
        """Tier 8: Search global knowledge base (all doc types, deduplicated)."""
        results = self.rag_indexer.search(query=query, top_k=limit, doc_type=None)
        # Filter out types already searched in earlier tiers
        already_searched = {"acord", "cuad", "underwriting_block", "ledgar", "maud", "insurance_qa"}
        filtered = [
            {
                "text": r.get("text", ""),
                "source": "knowledge_base",
                "category": r.get("category", ""),
                "name": r.get("name", ""),
                "type": r.get("type", ""),
                "score": r.get("score", 0),
            }
            for r in results
            if r.get("type") not in already_searched
        ]
        return filtered

    def format_as_context(self, results: List[Dict], max_chars: int = 4000) -> str:
        """Format search results as context string for LLM prompts."""
        if not results:
            return ""

        parts = []
        total_chars = 0

        for r in results:
            text = r.get("text", "")
            source = r.get("source_label", r.get("source", "unknown"))
            score = r.get("score", 0)

            entry = f"[Source: {source} | Relevance: {score:.2f}]\n{text}"

            if total_chars + len(entry) > max_chars:
                break

            parts.append(entry)
            total_chars += len(entry)

        return "\n\n---\n\n".join(parts)


# Source tier display labels
_TIER_LABELS = {
    "user": "Your Uploaded Documents",
    "acord": "ACORD Standard Clause",
    "cuad": "CUAD Contract Library",
    "jetech": "JETech Underwriting",
    "ledgar": "LEDGAR SEC Provisions",
    "maud": "MAUD Merger Agreements",
    "insurance_qa": "Insurance Q&A",
    "global": "Insurance Knowledge Base",
}


# Singleton instance
unified_rag = UnifiedRAG()
