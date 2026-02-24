"""
InstantRisk Engine - Comprehensive Clauses Library Service

Provides access to insurance and contract clauses from pgvector (primary)
or file-based sources (fallback).

Sources indexed in pgvector via rag_indexer:
- ACORD: Standard insurance clause wording (16,678 clauses)
- jetech: Insurance contract blocks (48,943 blocks)
- LEDGAR: Contract provisions in 100 categories (80,000 provisions)
- CUAD: Contract clauses with 41 types (508 clauses)
- ContractNLI: NLI contract clauses (10,319 clauses)
- acord_forms: ACORD form data (747 forms)

Features:
- Primary: pgvector semantic search (149K+ vectors)
- Fallback: file-based keyword search if pgvector unavailable
- Category-based browsing
- Pagination for large result sets
- Line of business filtering
"""

import json
import logging
import os
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
import re
import hashlib

logger = logging.getLogger(__name__)


@dataclass
class Clause:
    """Represents a single clause from any source."""

    id: str
    name: str
    text: str
    category: str
    source: str  # cuad, ledgar, contract_nli, templates
    clause_type: Optional[str] = None
    line_of_business: Optional[str] = None
    typical_use: Optional[str] = None
    form_number: Optional[str] = None
    is_exclusion: bool = False
    is_mandatory: bool = False
    keywords: List[str] = field(default_factory=list)


class ClausesLibraryService:
    """
    Comprehensive clauses library service providing access to 102K+ clauses.

    Loads clauses from multiple sources and indexes them for fast search.
    """

    # Data paths
    INSURANCE_DATA_PATH = "/app/app/data/insurance_data"
    TEMPLATES_PATH = "/app/data/templates/clauses"

    # LEDGAR label to category mapping (100 categories)
    LEDGAR_CATEGORIES = {
        0: "Adjustments",
        1: "Agreements",
        2: "Amendments",
        3: "Anti-Corruption",
        4: "Arbitration",
        5: "Assignments",
        6: "Audits",
        7: "Authorized Representative",
        8: "Base Salary",
        9: "Benefits",
        10: "Binding",
        11: "Board Composition",
        12: "Board Meetings",
        13: "Books And Records",
        14: "Brokers",
        15: "Business Combination",
        16: "Buyout",
        17: "Cap On Liability",
        18: "Change Of Control",
        19: "Choice Of Law",
        20: "Closing Date",
        21: "Closing Deliveries",
        22: "Compliance",
        23: "Conditions Precedent",
        24: "Confidentiality",
        25: "Consent Rights",
        26: "Consideration",
        27: "Covenants",
        28: "Definitions",
        29: "Disclosure",
        30: "Disputes",
        31: "Drag Along",
        32: "Effectiveness",
        33: "Employment",
        34: "Entire Agreement",
        35: "Equity",
        36: "Escrow",
        37: "Events Of Default",
        38: "Exclusivity",
        39: "Execution",
        40: "Exercise Period",
        41: "Expenses",
        42: "Fee",
        43: "Financial Reporting",
        44: "Financing",
        45: "Force Majeure",
        46: "Further Assurances",
        47: "General Provisions",
        48: "Good Faith",
        49: "Governing Law",
        50: "Guarantees",
        51: "Holdback",
        52: "IP Rights",
        53: "Indemnification",
        54: "Information Rights",
        55: "Insurance",
        56: "Interest",
        57: "Jurisdiction",
        58: "Knowledge",
        59: "Lease",
        60: "Limitation Of Liability",
        61: "Liquidated Damages",
        62: "Liquidity",
        63: "Litigation",
        64: "Material Adverse Change",
        65: "Milestones",
        66: "Miscellaneous",
        67: "Non-Compete",
        68: "Non-Solicitation",
        69: "Notice",
        70: "Participation",
        71: "Payment Terms",
        72: "Penalties",
        73: "Performance",
        74: "Preemptive Rights",
        75: "Price",
        76: "Publicity",
        77: "Purchase And Sale",
        78: "Recitals",
        79: "Redemption",
        80: "Registration Rights",
        81: "Remedies",
        82: "Renewal",
        83: "Representations",
        84: "Resignation",
        85: "Restrictive Covenants",
        86: "Rights",
        87: "Risk Of Loss",
        88: "Severability",
        89: "Shareholder Rights",
        90: "Stock Options",
        91: "Subordination",
        92: "Survival",
        93: "Tag Along",
        94: "Taxes",
        95: "Term",
        96: "Termination",
        97: "Third Party Rights",
        98: "Transfer",
        99: "Warranties",
    }

    # CUAD clause types (41 types)
    CUAD_TYPES = [
        "Document Name",
        "Parties",
        "Agreement Date",
        "Effective Date",
        "Expiration Date",
        "Renewal Term",
        "Notice Period To Terminate Renewal",
        "Governing Law",
        "Most Favored Nation",
        "Non-Compete",
        "Exclusivity",
        "No-Solicit Of Customers",
        "Competitive Restriction Exception",
        "No-Solicit Of Employees",
        "Non-Disparagement",
        "Termination For Convenience",
        "Rofr/Rofo/Rofn",
        "Change Of Control",
        "Anti-Assignment",
        "Revenue/Profit Sharing",
        "Price Restrictions",
        "Minimum Commitment",
        "Volume Restriction",
        "Ip Ownership Assignment",
        "Joint Ip Ownership",
        "License Grant",
        "Non-Transferable License",
        "Affiliate License-Licensor",
        "Affiliate License-Licensee",
        "Unlimited/All-You-Can-Eat-License",
        "Irrevocable Or Perpetual License",
        "Source Code Escrow",
        "Post-Termination Services",
        "Audit Rights",
        "Uncapped Liability",
        "Cap On Liability",
        "Liquidated Damages",
        "Warranty Duration",
        "Insurance",
        "Covenant Not To Sue",
        "Third Party Beneficiary",
    ]

    def __init__(self):
        self._clauses: List[Clause] = []
        self._categories: Dict[str, int] = defaultdict(int)  # category -> count
        self._sources: Dict[str, int] = defaultdict(int)  # source -> count
        self._index: Dict[str, List[int]] = defaultdict(
            list
        )  # keyword -> clause indices
        self._loaded = False

    def load_all(self) -> None:
        """Load all clauses from all sources."""
        if self._loaded:
            return

        print("Loading InstantRisk Engine clauses library...")

        # Load from each source
        self._load_lma_clauses()
        self._load_ledgar_clauses()
        self._load_cuad_clauses()
        self._load_contract_nli_clauses()
        self._load_template_clauses()

        # Build search index
        self._build_index()

        self._loaded = True
        print(f"Loaded {len(self._clauses)} clauses from {len(self._sources)} sources")
        print(f"Categories: {len(self._categories)}")

    def _load_lma_clauses(self) -> None:
        """Load LMA (Lloyd's Market Association) standard insurance clauses."""
        lma_path = os.path.join(self.INSURANCE_DATA_PATH, "lma", "all_lma_clauses.json")
        if not os.path.exists(lma_path):
            print(f"LMA clauses file not found: {lma_path}")
            return

        try:
            with open(lma_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            for clause_data in data.get("clauses", []):
                clause = Clause(
                    id=clause_data.get("id", ""),
                    name=clause_data.get("name", ""),
                    text=clause_data.get("text", ""),
                    category=clause_data.get("category", "LMA"),
                    source="lma",
                    clause_type=clause_data.get("clause_type"),
                    line_of_business=clause_data.get("line_of_business", "all"),
                    is_exclusion=clause_data.get("is_exclusion", False),
                    is_mandatory=False,  # No mandatory clauses - all recommendations are based on relevance
                    keywords=self._extract_keywords(clause_data.get("text", "")),
                )
                self._clauses.append(clause)
                self._categories[clause.category] += 1
                self._sources["lma"] += 1

            print(f"Loaded {self._sources['lma']} LMA clauses")
        except Exception as e:
            print(f"Error loading LMA clauses: {e}")

    def _load_ledgar_clauses(self) -> None:
        """Load LEDGAR clauses (80,000 provisions in 100 categories)."""
        ledgar_path = os.path.join(
            self.INSURANCE_DATA_PATH, "contract_clauses", "ledgar"
        )

        for filename in ["train.json", "validation.json", "test.json"]:
            filepath = os.path.join(ledgar_path, filename)
            if not os.path.exists(filepath):
                continue

            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data_list = json.load(f)

                for data in data_list:
                    try:
                        text = data.get("text", "")
                        label = data.get("label", 0)

                        # Map label to category
                        category = self.LEDGAR_CATEGORIES.get(
                            label, f"Category_{label}"
                        )

                        # Generate unique ID
                        clause_id = f"ledgar_{hashlib.md5(text.encode(), usedforsecurity=False).hexdigest()[:12]}"

                        clause = Clause(
                            id=clause_id,
                            name=f"{category} Provision",
                            text=text[:2000]
                            if len(text) > 2000
                            else text,  # Limit text length
                            category=category.lower().replace(" ", "_"),
                            source="ledgar",
                            clause_type=category,
                            keywords=self._extract_keywords(text[:500]),
                        )
                        self._clauses.append(clause)
                        self._categories[clause.category] += 1
                        self._sources["ledgar"] += 1

                    except Exception as e:
                        logger.debug(f"LEDGAR clause parse error: {e}")
                        continue

            except Exception as e:
                print(f"Error loading LEDGAR {filename}: {e}")

        print(f"Loaded {self._sources['ledgar']} LEDGAR clauses")

    def _load_cuad_clauses(self) -> None:
        """Load CUAD clauses (12,422 clauses with 41 types)."""
        cuad_path = os.path.join(self.INSURANCE_DATA_PATH, "contract_clauses", "cuad")

        for filename in ["train.json", "test.json", "train_full.json"]:
            filepath = os.path.join(cuad_path, filename)
            if not os.path.exists(filepath):
                continue

            is_full = filename == "train_full.json"

            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data_list = json.load(f)

                for data in data_list:
                    try:
                        if is_full:
                            # train_full.json format: text, category, source, name, contract_title, clause_types
                            text = data.get("text", "")
                            clause_type = data.get("category", "General")
                            name = data.get("name", clause_type)
                        else:
                            # Original SQuAD format: context, question, title
                            text = data.get("context", "")
                            question = data.get("question", "")
                            title = data.get("title", "")

                            clause_type = "General"
                            for ct in self.CUAD_TYPES:
                                if ct.lower() in question.lower():
                                    clause_type = ct
                                    break
                            name = (
                                f"{clause_type} - {title[:50]}"
                                if title
                                else clause_type
                            )

                        if not text:
                            continue

                        # Generate unique ID
                        clause_id = f"cuad_{hashlib.md5(text.encode(), usedforsecurity=False).hexdigest()[:12]}"

                        clause = Clause(
                            id=clause_id,
                            name=name,
                            text=text[:2000] if len(text) > 2000 else text,
                            category=clause_type.lower()
                            .replace(" ", "_")
                            .replace("/", "_"),
                            source="cuad",
                            clause_type=clause_type,
                            keywords=self._extract_keywords(text[:500]),
                        )
                        self._clauses.append(clause)
                        self._categories[clause.category] += 1
                        self._sources["cuad"] += 1

                    except Exception as e:
                        logger.debug(f"CUAD clause parse error: {e}")
                        continue

            except Exception as e:
                print(f"Error loading CUAD {filename}: {e}")

        print(f"Loaded {self._sources['cuad']} CUAD clauses")

    def _load_contract_nli_clauses(self) -> None:
        """Load ContractNLI clauses (10,319 clauses)."""
        nli_path = os.path.join(
            self.INSURANCE_DATA_PATH, "contract_clauses", "contract_nli"
        )

        for filename in ["train.json", "dev.json", "test.json", "train_full.json"]:
            filepath = os.path.join(nli_path, filename)
            if not os.path.exists(filepath):
                continue

            is_full = filename == "train_full.json"

            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data_list = json.load(f)

                for data in data_list:
                    try:
                        if is_full:
                            # train_full.json format: text, category, source, name, hypothesis, label
                            text = data.get("text", "")
                            category = data.get("category", "general")
                            label = data.get("label", "")
                            name = data.get(
                                "name", f"Contract NLI - {category.title()}"
                            )
                        else:
                            # Original format: sentence1, sentence2, gold_label
                            sentence1 = data.get("sentence1", "")
                            sentence2 = data.get("sentence2", "")
                            label = data.get("gold_label", "")
                            text = f"{sentence1}\n\nRelated: {sentence2}"
                            category = self._infer_category(sentence1)
                            name = f"Contract NLI - {category.title()}"

                        if not text:
                            continue

                        # Generate unique ID
                        clause_id = f"nli_{hashlib.md5(text.encode(), usedforsecurity=False).hexdigest()[:12]}"

                        clause = Clause(
                            id=clause_id,
                            name=name,
                            text=text[:2000] if len(text) > 2000 else text,
                            category=category,
                            source="contract_nli",
                            clause_type=label,
                            keywords=self._extract_keywords(text[:500]),
                        )
                        self._clauses.append(clause)
                        self._categories[clause.category] += 1
                        self._sources["contract_nli"] += 1

                    except Exception as e:
                        logger.debug(f"ContractNLI clause parse error: {e}")
                        continue

            except Exception as e:
                print(f"Error loading ContractNLI {filename}: {e}")

        print(f"Loaded {self._sources['contract_nli']} ContractNLI clauses")

    def _load_template_clauses(self) -> None:
        """Load clauses from templates directory."""
        if not os.path.exists(self.TEMPLATES_PATH):
            return

        for subdir in ["by_type", "by_line", "lloyd_specific"]:
            dirpath = os.path.join(self.TEMPLATES_PATH, subdir)
            if not os.path.exists(dirpath):
                continue

            for filename in os.listdir(dirpath):
                if not filename.endswith(".json"):
                    continue

                filepath = os.path.join(dirpath, filename)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    source_category = data.get(
                        "type", data.get("category", filename.replace(".json", ""))
                    )

                    for clause_data in data.get("clauses", []):
                        clause = Clause(
                            id=clause_data.get(
                                "id",
                                f"tmpl_{hashlib.md5(str(clause_data).encode(), usedforsecurity=False).hexdigest()[:12]}",
                            ),
                            name=clause_data.get("name", ""),
                            text=clause_data.get("text", ""),
                            category=source_category,
                            source="templates",
                            typical_use=clause_data.get("typical_use"),
                            line_of_business=clause_data.get("line_of_business"),
                            is_exclusion="exclusion"
                            in clause_data.get("name", "").lower(),
                            keywords=self._extract_keywords(
                                clause_data.get("text", "")
                            ),
                        )
                        self._clauses.append(clause)
                        self._categories[clause.category] += 1
                        self._sources["templates"] += 1

                except Exception as e:
                    print(f"Error loading template {filename}: {e}")

        print(f"Loaded {self._sources['templates']} template clauses")

    def _extract_keywords(self, text: str, max_keywords: int = 10) -> List[str]:
        """Extract keywords from text for indexing."""
        if not text:
            return []

        # Common legal/insurance terms to look for
        legal_terms = {
            "liability",
            "indemnification",
            "termination",
            "confidential",
            "warranty",
            "insurance",
            "coverage",
            "exclusion",
            "premium",
            "claim",
            "loss",
            "damage",
            "policy",
            "insured",
            "insurer",
            "underwriter",
            "broker",
            "risk",
            "peril",
            "deductible",
            "limit",
            "aggregate",
            "occurrence",
            "negligence",
            "breach",
            "contract",
            "agreement",
            "party",
            "parties",
            "obligation",
            "duty",
            "rights",
            "remedy",
            "dispute",
            "arbitration",
            "jurisdiction",
            "governing",
            "law",
            "notice",
            "consent",
            "assignment",
            "sanction",
            "compliance",
            "regulation",
            "statutory",
            "cyber",
            "terrorism",
            "war",
            "nuclear",
            "pollution",
            "asbestos",
            "pandemic",
            "epidemic",
        }

        # Extract words and find matches
        words = re.findall(r"\b[a-zA-Z]{4,}\b", text.lower())
        keywords = []
        seen = set()

        for word in words:
            if word in legal_terms and word not in seen:
                keywords.append(word)
                seen.add(word)
                if len(keywords) >= max_keywords:
                    break

        return keywords

    def _infer_category(self, text: str) -> str:
        """Infer category from text content."""
        text_lower = text.lower()

        if "terminat" in text_lower:
            return "termination"
        elif "indemni" in text_lower:
            return "indemnification"
        elif "confiden" in text_lower:
            return "confidentiality"
        elif "warrant" in text_lower:
            return "warranties"
        elif "liabil" in text_lower:
            return "liability"
        elif "insur" in text_lower:
            return "insurance"
        elif "govern" in text_lower and "law" in text_lower:
            return "governing_law"
        elif "arbitrat" in text_lower:
            return "arbitration"
        elif "disclos" in text_lower:
            return "disclosure"
        elif "assign" in text_lower:
            return "assignment"
        else:
            return "general"

    def _build_index(self) -> None:
        """Build keyword index for fast search."""
        for idx, clause in enumerate(self._clauses):
            # Index by keywords
            for keyword in clause.keywords:
                self._index[keyword].append(idx)

            # Index by category
            self._index[f"cat:{clause.category}"].append(idx)

            # Index by source
            self._index[f"src:{clause.source}"].append(idx)

    # ---- pgvector fallback methods ----

    def _use_pgvector(self) -> bool:
        """Return True if file-based library is empty and pgvector should be used."""
        self.load_all()
        return len(self._clauses) == 0

    # Doc types that contain real clause/contract wording suitable for documents.
    # insurance_qa, mini_insurance, snorkel_underwriting, contract_nli are
    # context-only datasets and must NEVER appear in document section content.
    DOCUMENT_DOC_TYPES = {"acord", "jetech", "ledgar", "cuad", "acord_forms"}

    def _pgvector_search(
        self,
        query: Optional[str] = None,
        category: Optional[str] = None,
        source: Optional[str] = None,
        line_of_business: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Search clauses via pgvector when file-based library is empty.
        Uses RAGIndexer.search() which is synchronous.

        IMPORTANT: Only searches document-appropriate datasets (acord, jetech,
        ledgar, cuad, acord_forms). Context-only datasets (insurance_qa,
        mini_insurance, snorkel_underwriting, contract_nli) are excluded.
        """
        try:
            from app.services.rag_indexer import rag_indexer
        except Exception as e:
            logger.warning(f"Could not import rag_indexer for clause search: {e}")
            return [], 0

        # Build query from available params
        search_query = query or category or line_of_business or "insurance clause"

        # Map source filter to pgvector doc_type
        doc_type_map = {
            "lma": "acord",
            "acord": "acord",
            "cuad": "cuad",
            "ledgar": "ledgar",
            "jetech": "jetech",
            "acord_forms": "acord_forms",
        }
        doc_type = doc_type_map.get((source or "").lower()) if source else None

        # pgvector returns top_k results — request enough to paginate.
        # When no specific doc_type is requested, we search each allowed
        # doc_type individually and merge results to guarantee context-only
        # datasets are never included.
        top_k = min(page * page_size + page_size, 200)

        try:
            if doc_type:
                # Caller specified a source — validate it's document-appropriate
                if doc_type not in self.DOCUMENT_DOC_TYPES:
                    logger.warning(
                        f"Blocked clause search for context-only doc_type={doc_type}"
                    )
                    return [], 0
                raw_results = rag_indexer.search(
                    query=search_query, top_k=top_k, doc_type=doc_type
                )
            else:
                # No source filter — search ONLY document-appropriate types
                raw_results = []
                per_type_k = max(top_k // len(self.DOCUMENT_DOC_TYPES), 20)
                for dt in self.DOCUMENT_DOC_TYPES:
                    try:
                        partial = rag_indexer.search(
                            query=search_query, top_k=per_type_k, doc_type=dt
                        )
                        raw_results.extend(partial)
                    except Exception as e:
                        logger.debug(f"pgvector search for {dt} failed: {e}")
                # Sort merged results by score descending
                raw_results.sort(key=lambda r: r.get("score", 0), reverse=True)
                # Trim to top_k
                raw_results = raw_results[:top_k]
        except Exception as e:
            logger.warning(f"pgvector clause search failed: {e}")
            return [], 0

        if not raw_results:
            return [], 0

        # Filter by category substring if specified
        if category:
            cat_lower = category.lower()
            raw_results = [
                r
                for r in raw_results
                if cat_lower in (r.get("category", "") or "").lower()
                or cat_lower in (r.get("type", "") or "").lower()
            ]

        # Filter by line_of_business substring
        if line_of_business:
            lob_lower = line_of_business.lower()
            lob_filtered = [
                r
                for r in raw_results
                if lob_lower in (r.get("text", "") or "").lower()
                or lob_lower in (r.get("category", "") or "").lower()
            ]
            # Only apply filter if it doesn't eliminate everything
            if lob_filtered:
                raw_results = lob_filtered

        # Filter out non-insurance junk
        non_insurance = [
            "employment",
            "real estate",
            "merger",
            "acquisition",
            "stock purchase",
        ]
        filtered = []
        for r in raw_results:
            cat = (r.get("category", "") or "").lower()
            if any(ni in cat for ni in non_insurance):
                continue
            text = r.get("text", "") or ""
            if len(text) < 30:
                continue
            filtered.append(r)

        total = len(filtered)

        # Paginate
        start = (page - 1) * page_size
        end = start + page_size
        page_results = filtered[start:end]

        # Convert to clause dict format
        results = []
        for r in page_results:
            text = r.get("text", "") or ""
            name = r.get("name", "") or r.get("question", "") or ""
            cat = r.get("category", "") or r.get("type", "") or "general"
            src = r.get("type", "") or r.get("source", "") or "rag"
            clause_id = f"rag_{hashlib.md5(text[:200].encode(), usedforsecurity=False).hexdigest()[:12]}"

            if not name:
                name = f"{cat.replace('_', ' ').title()} Clause"

            results.append(
                {
                    "id": clause_id,
                    "name": name[:200],
                    "category": cat.lower().replace(" ", "_"),
                    "source": src,
                    "clause_type": cat,
                    "line_of_business": line_of_business,
                    "typical_use": None,
                    "form_number": None,
                    "is_exclusion": "exclusion" in cat.lower()
                    or "exclusion" in text[:200].lower(),
                    "is_mandatory": False,
                    "text": text[:2000],
                    "text_preview": text[:300] + ("..." if len(text) > 300 else ""),
                }
            )

        return results, total

    def _pgvector_get_clause_by_id(self, clause_id: str) -> Optional[Dict[str, Any]]:
        """Look up a clause by ID — for pgvector clauses, search by text hash."""
        # pgvector clauses have IDs like rag_abc123def456 — we can't reverse the hash.
        # Return None and let the caller handle it.
        return None

    def search(
        self,
        query: Optional[str] = None,
        category: Optional[str] = None,
        source: Optional[str] = None,
        line_of_business: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Search clauses with filters and pagination.
        Uses pgvector when file-based library is empty.

        Returns:
            Tuple of (list of clause dicts, total count)
        """
        # If file-based library is empty, delegate to pgvector
        if self._use_pgvector():
            return self._pgvector_search(
                query=query,
                category=category,
                source=source,
                line_of_business=line_of_business,
                page=page,
                page_size=page_size,
            )

        # --- Original file-based search below ---

        # Start with all clause indices
        candidates = set(range(len(self._clauses)))

        # Filter by category
        if category:
            cat_key = f"cat:{category.lower()}"
            if cat_key in self._index:
                candidates &= set(self._index[cat_key])
            else:
                candidates = set()

        # Filter by source
        if source:
            src_key = f"src:{source.lower()}"
            if src_key in self._index:
                candidates &= set(self._index[src_key])
            else:
                candidates = set()

        # Filter by search query
        if query:
            query_words = query.lower().split()
            query_matches = set()

            for word in query_words:
                if word in self._index:
                    query_matches |= set(self._index[word])

            # Also do text search for remaining candidates
            for idx in list(candidates):
                clause = self._clauses[idx]
                if (
                    query.lower() in clause.text.lower()
                    or query.lower() in clause.name.lower()
                ):
                    query_matches.add(idx)

            candidates &= query_matches

        # Filter by line of business
        if line_of_business:
            lob_lower = line_of_business.lower()
            lob_matches = set()
            for idx in candidates:
                clause = self._clauses[idx]
                if (
                    clause.line_of_business
                    and lob_lower in clause.line_of_business.lower()
                ):
                    lob_matches.add(idx)
                # Also check text for LOB mentions
                elif (
                    lob_lower in clause.text.lower()
                    or lob_lower in clause.category.lower()
                ):
                    lob_matches.add(idx)
            candidates &= lob_matches if lob_matches else candidates

        # Sort by relevance (source priority)
        source_priority = {"templates": 0, "cuad": 1, "ledgar": 2, "contract_nli": 3}
        sorted_indices = sorted(
            candidates,
            key=lambda i: (
                source_priority.get(self._clauses[i].source, 5),
                self._clauses[i].name,
            ),
        )

        # Paginate
        total = len(sorted_indices)
        start = (page - 1) * page_size
        end = start + page_size
        page_indices = sorted_indices[start:end]

        # Convert to dicts
        results = [self._clause_to_dict(self._clauses[i]) for i in page_indices]

        return results, total

    def get_categories(self) -> List[Dict[str, Any]]:
        """Get all categories with counts."""
        self.load_all()

        categories = []
        for cat, count in sorted(self._categories.items(), key=lambda x: -x[1]):
            categories.append(
                {"id": cat, "name": cat.replace("_", " ").title(), "count": count}
            )
        return categories

    def get_sources(self) -> Dict[str, int]:
        """Get source statistics."""
        self.load_all()
        return dict(self._sources)

    def get_clause_by_id(self, clause_id: str) -> Optional[Dict[str, Any]]:
        """Get a single clause by ID."""
        self.load_all()

        for clause in self._clauses:
            if clause.id == clause_id:
                return self._clause_to_dict(clause, include_full_text=True)

        # If file-based is empty, try pgvector search by name/id
        if self._use_pgvector():
            return self._pgvector_get_clause_by_id(clause_id)

        return None

    def get_statistics(self) -> Dict[str, Any]:
        """Get library statistics."""
        self.load_all()

        return {
            "total_clauses": len(self._clauses),
            "total_categories": len(self._categories),
            "sources": dict(self._sources),
            "top_categories": [
                {"category": cat, "count": count}
                for cat, count in sorted(self._categories.items(), key=lambda x: -x[1])[
                    :20
                ]
            ],
        }

    def _clause_to_dict(
        self, clause: Clause, include_full_text: bool = False
    ) -> Dict[str, Any]:
        """Convert Clause to dictionary."""
        result = {
            "id": clause.id,
            "name": clause.name,
            "category": clause.category,
            "source": clause.source,
            "clause_type": clause.clause_type,
            "line_of_business": clause.line_of_business,
            "typical_use": clause.typical_use,
            "form_number": clause.form_number,
            "is_exclusion": clause.is_exclusion,
            "is_mandatory": clause.is_mandatory,
        }

        if include_full_text:
            result["text"] = clause.text
        else:
            # Always include full text up to 2000 chars for document drafting.
            # SectionDrafter reads result["text"] — a 300-char preview is too short
            # for actual clause wording to be embedded in generated documents.
            result["text"] = (
                clause.text[:2000] if len(clause.text) > 2000 else clause.text
            )
            # Keep text_preview as well for UI display purposes
            result["text_preview"] = (
                clause.text[:300] + "..." if len(clause.text) > 300 else clause.text
            )

        return result


# Singleton instance
clauses_library_service = ClausesLibraryService()
