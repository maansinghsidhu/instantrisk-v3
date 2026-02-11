"""
InstantRisk V3 - Clause Service

Provides access to insurance clauses library for document generation and language translation.
Delegates to ClausesLibraryService for the actual clause data.
"""

import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class ClauseService:
    """
    Facade for clause operations used by document generation and language routers.

    Wraps ClausesLibraryService with a simpler interface.
    """

    def __init__(self):
        self._clauses: List[Dict[str, Any]] = []
        self._categories: Dict[str, List[Dict[str, Any]]] = {}
        self._loaded = False
        self._load_clauses()

    def _load_clauses(self):
        """Load clauses from the clauses library service."""
        try:
            from app.services.clauses_library_service import ClausesLibraryService
            library = ClausesLibraryService()
            # search() with no query returns all clauses as (list, total_count)
            results, total = library.search(page_size=200000)
            self._clauses = results if results else []
            self._loaded = True
            logger.info(f"Loaded {len(self._clauses)} clauses from library")
        except Exception as e:
            logger.warning(f"Could not load clauses library: {e}. Clause features will be limited.")
            self._clauses = []
            self._loaded = False

        # Build category index
        self._categories = {}
        for clause in self._clauses:
            cat = clause.get("category", "general") if isinstance(clause, dict) else "general"
            if cat not in self._categories:
                self._categories[cat] = []
            self._categories[cat].append(clause)

    def get_all_clauses(self) -> List[Dict[str, Any]]:
        """Return all available clauses."""
        return self._clauses

    def get_clause_by_id(self, clause_id: str) -> Optional[Dict[str, Any]]:
        """Find a clause by its ID."""
        for clause in self._clauses:
            if isinstance(clause, dict) and clause.get("id") == clause_id:
                return clause
        return None

    def get_clauses_by_category(self, category: str) -> List[Dict[str, Any]]:
        """Return clauses filtered by category."""
        category_lower = category.lower()
        return self._categories.get(category_lower, [])

    def search_clauses(
        self, query: str, categories: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Search clauses by text query, optionally filtered by categories."""
        query_lower = query.lower()
        results = []
        for clause in self._clauses:
            if not isinstance(clause, dict):
                continue
            # Filter by categories if specified
            if categories:
                clause_cat = clause.get("category", "").lower()
                if clause_cat not in [c.lower() for c in categories]:
                    continue
            # Search in name, text, and category
            name = clause.get("name", "").lower()
            text = clause.get("text", "").lower()
            cat = clause.get("category", "").lower()
            if query_lower in name or query_lower in text or query_lower in cat:
                results.append(clause)
        return results

    def get_categories(self) -> List[str]:
        """Return list of available categories."""
        return list(self._categories.keys())

    def get_categories_translated(self, language: str) -> List[Dict[str, str]]:
        """Return categories with translated names (stub - returns English)."""
        return [
            {"code": cat, "name": cat.replace("_", " ").title()}
            for cat in self._categories.keys()
        ]

    async def get_clauses_translated(
        self, clauses: List[Dict[str, Any]], language: str
    ) -> List[Dict[str, Any]]:
        """Translate clause text to the specified language."""
        if language == "en":
            return clauses
        try:
            from app.services.translation_service import get_translation_service
            translator = get_translation_service()
            translated = []
            for clause in clauses:
                clause_copy = dict(clause)
                if "text" in clause_copy:
                    clause_copy["text"] = await translator.translate(
                        clause_copy["text"], language
                    )
                if "name" in clause_copy:
                    clause_copy["name"] = await translator.translate(
                        clause_copy["name"], language
                    )
                translated.append(clause_copy)
            return translated
        except Exception as e:
            logger.warning(f"Translation failed: {e}. Returning original clauses.")
            return clauses


# Singleton instance
_clause_service: Optional[ClauseService] = None


def get_clause_service() -> ClauseService:
    """Get or create the singleton ClauseService instance."""
    global _clause_service
    if _clause_service is None:
        _clause_service = ClauseService()
    return _clause_service
