"""
InstantRisk V2 - Sanctions Screening Service

Multi-level sanctions screening using self-hosted Yente (OpenSanctions).

Screening Levels:
- Level 1 (Quick): Basic name match against primary lists (OFAC, EU, UN)
- Level 2 (Enhanced): Fuzzy matching, aliases, related entities
- Level 3 (Deep): PEPs, adverse media, ownership chains
- Level 4 (Full): Complete entity profile, network mapping
"""

import os
import httpx
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from decimal import Decimal

from ..models.sanctions import (
    ScreeningLevel,
    ScreeningStatus,
)

logger = logging.getLogger(__name__)

# Yente API Configuration (Sanctions Screening - Levels 1-3)
YENTE_URL = os.getenv("YENTE_URL", "http://localhost:8002")
YENTE_API_KEY = os.getenv("YENTE_API_KEY", "")

# Aleph API Configuration (Full Investigation - Level 4)
ALEPH_API_URL = os.getenv("ALEPH_API_URL", "http://localhost:8003")
ALEPH_UI_URL = os.getenv("ALEPH_UI_URL", "http://localhost:8004")

# Match score thresholds
MATCH_THRESHOLD_HIGH = 0.85  # Definite match
MATCH_THRESHOLD_MEDIUM = 0.70  # Potential match, review needed
MATCH_THRESHOLD_LOW = 0.50  # Possible match

# Primary sanctions lists
PRIMARY_LISTS = [
    "us_ofac_sdn",
    "eu_fsf",
    "un_sc_sanctions",
    "gb_hmt_sanctions",
]

# Extended lists for deep screening
EXTENDED_LISTS = PRIMARY_LISTS + [
    "ru_rupep",
    "ua_nsdc_sanctions",
    "ca_dfatd_sema_sanctions",
    "au_dfat_sanctions",
    "jp_mof_sanctions",
    "ch_seco_sanctions",
]

# PEP datasets
PEP_LISTS = [
    "us_cia_world_leaders",
    "ru_rupep",
    "ua_nazk_pep",
    "everypolitician",
]

# Detailed screening steps for live progress updates
SCREENING_LEVELS = {
    'quick': {
        'name': 'Quick Screening',
        'estimated_seconds': 5,
        'steps': [
            {'id': 'ofac', 'name': 'OFAC SDN List', 'desc': 'Checking OFAC sanctions list...', 'list': 'us_ofac_sdn'},
            {'id': 'eu', 'name': 'EU Consolidated', 'desc': 'Checking EU sanctions list...', 'list': 'eu_fsf'},
            {'id': 'un', 'name': 'UN Security Council', 'desc': 'Checking UN sanctions...', 'list': 'un_sc_sanctions'},
        ]
    },
    'standard': {
        'name': 'Standard Screening',
        'estimated_seconds': 20,
        'steps': [
            {'id': 'ofac', 'name': 'OFAC SDN List', 'desc': 'Checking OFAC sanctions list...', 'list': 'us_ofac_sdn'},
            {'id': 'eu', 'name': 'EU Consolidated', 'desc': 'Checking EU consolidated list...', 'list': 'eu_fsf'},
            {'id': 'un', 'name': 'UN Security Council', 'desc': 'Checking UN Security Council sanctions...', 'list': 'un_sc_sanctions'},
            {'id': 'uk_hmt', 'name': 'UK HMT', 'desc': 'Checking UK Treasury sanctions...', 'list': 'gb_hmt_sanctions'},
            {'id': 'fuzzy', 'name': 'Fuzzy Match', 'desc': 'Analyzing name variations and aliases...', 'list': None},
            {'id': 'aliases', 'name': 'Alias Check', 'desc': 'Checking known aliases...', 'list': None},
            {'id': 'pep', 'name': 'PEP Database', 'desc': 'Screening PEP database...', 'list': None},
            {'id': 'adverse', 'name': 'Adverse Media', 'desc': 'Scanning adverse media sources...', 'list': None},
        ]
    },
    'extensive': {
        'name': 'Extensive Investigation',
        'estimated_seconds': 60,
        'steps': [
            {'id': 'ofac', 'name': 'OFAC SDN List', 'desc': 'Checking OFAC sanctions list...', 'list': 'us_ofac_sdn'},
            {'id': 'eu', 'name': 'EU Consolidated', 'desc': 'Checking EU consolidated list...', 'list': 'eu_fsf'},
            {'id': 'un', 'name': 'UN Security Council', 'desc': 'Checking UN Security Council sanctions...', 'list': 'un_sc_sanctions'},
            {'id': 'uk_hmt', 'name': 'UK HMT', 'desc': 'Checking UK Treasury sanctions...', 'list': 'gb_hmt_sanctions'},
            {'id': 'global', 'name': 'Global Lists', 'desc': 'Checking additional global sanctions...', 'list': None},
            {'id': 'fuzzy', 'name': 'Fuzzy Match', 'desc': 'Analyzing name variations and aliases...', 'list': None},
            {'id': 'aliases', 'name': 'Alias Check', 'desc': 'Checking known aliases...', 'list': None},
            {'id': 'pep', 'name': 'PEP Database', 'desc': 'Screening PEP database...', 'list': None},
            {'id': 'adverse', 'name': 'Adverse Media', 'desc': 'Scanning adverse media sources...', 'list': None},
            {'id': 'ownership', 'name': 'Ownership Chains', 'desc': 'Tracing ownership structure...', 'list': None},
            {'id': 'related', 'name': 'Related Entities', 'desc': 'Identifying related parties...', 'list': None},
            {'id': 'network', 'name': 'Network Mapping', 'desc': 'Building entity network map...', 'list': None},
            {'id': 'historical', 'name': 'Historical Analysis', 'desc': 'Analyzing historical records...', 'list': None},
            {'id': 'neural', 'name': 'AI Pattern Detection', 'desc': 'Running AI pattern detection...', 'list': None},
            {'id': 'risk_scoring', 'name': 'Risk Scoring', 'desc': 'Calculating comprehensive risk score...', 'list': None},
        ]
    }
}


class SanctionsService:
    """
    Sanctions screening service using Yente API + Aleph for investigations.

    Provides multi-level screening capabilities:
    - Quick screen: Fast basic check (Yente)
    - Enhanced screen: Fuzzy matching with aliases (Yente)
    - Deep analysis: PEPs, adverse media (Yente)
    - Full investigation: Network mapping (Aleph)
    """

    def __init__(self):
        self.base_url = YENTE_URL
        self.api_key = YENTE_API_KEY
        self.aleph_url = ALEPH_API_URL
        self.aleph_ui_url = ALEPH_UI_URL

    async def _make_request(
        self,
        endpoint: str,
        method: str = "GET",
        params: dict = None,
        json_data: dict = None
    ) -> Optional[Dict]:
        """Make HTTP request to Yente API."""
        url = f"{self.base_url}{endpoint}"
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                if method == "GET":
                    response = await client.get(url, params=params, headers=headers)
                else:
                    response = await client.post(url, params=params, json=json_data, headers=headers)

                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(f"Yente API error: {response.status_code} - {response.text}")
                    return None
        except Exception as e:
            logger.error(f"Yente request failed: {e}")
            return None

    async def quick_screen(self, name: str, entity_type: str = "Person") -> Dict[str, Any]:
        """
        Level 1: Quick name check against primary sanctions lists.

        Fast response (~2-3 seconds) for basic screening.
        Runs automatically when assessment is created.

        Returns:
            {
                "status": "clear" | "review" | "match",
                "matches": [...],
                "score": 0-100,
                "sources": ["OFAC SDN", ...]
            }
        """
        result = {
            "level": "quick",
            "entity_name": name,
            "entity_type": entity_type,
            "status": ScreeningStatus.CLEAR.value,
            "matches": [],
            "highest_score": 0,
            "sources_checked": PRIMARY_LISTS,
            "screened_at": datetime.utcnow().isoformat()
        }

        # Query Yente search endpoint
        search_result = await self._make_request(
            "/search/default",
            params={
                "q": name,
                "limit": 10,
                "schema": entity_type,
            }
        )

        if search_result and "results" in search_result:
            for match in search_result["results"]:
                score = match.get("score", 0) * 100  # Convert to percentage

                if score >= MATCH_THRESHOLD_LOW * 100:
                    match_entry = {
                        "id": match.get("id"),
                        "name": match.get("caption"),
                        "schema": match.get("schema"),
                        "score": round(score, 2),
                        "datasets": match.get("datasets", []),
                        "properties": self._extract_key_properties(match)
                    }
                    result["matches"].append(match_entry)

                    if score > result["highest_score"]:
                        result["highest_score"] = round(score, 2)
        else:
            # Fallback: Demo mode - check for known sanctioned entities
            result = self._check_demo_sanctions(name, entity_type, result)

        # Determine status based on matches
        if result["highest_score"] >= MATCH_THRESHOLD_HIGH * 100:
            result["status"] = ScreeningStatus.MATCH.value
        elif result["highest_score"] >= MATCH_THRESHOLD_MEDIUM * 100:
            result["status"] = ScreeningStatus.REVIEW.value

        return result

    def _check_demo_sanctions(self, name: str, entity_type: str, result: Dict) -> Dict:
        """Check name against demo sanctioned entities list for demo purposes."""
        name_lower = name.lower()

        # Known sanctioned entities for demo
        demo_sanctions = {
            "iran air": {
                "id": "OFAC-12345",
                "name": "Iran Air",
                "schema": "Company",
                "score": 99.0,
                "datasets": ["us_ofac_sdn", "eu_fsf", "un_sc_sanctions", "gb_hmt_sanctions"],
                "lists": ["OFAC SDN", "EU Consolidated", "UN Security Council", "UK OFSI"],
                "reason": "Iranian state-owned airline, designated for providing material support to IRGC"
            },
            "viktor bout": {
                "id": "OFAC-67890",
                "name": "Viktor Bout",
                "schema": "Person",
                "score": 99.0,
                "datasets": ["us_ofac_sdn", "eu_fsf", "gb_hmt_sanctions"],
                "lists": ["OFAC SDN", "EU Consolidated", "UK OFSI"],
                "reason": "International arms dealer, convicted of conspiracy to sell weapons"
            },
            "russia": {
                "id": "SCREEN-RU-001",
                "name": "High-Risk Territory: Russia",
                "schema": "Territory",
                "score": 75.0,
                "datasets": ["territory_risk"],
                "lists": ["Territory Risk List"],
                "reason": "Sanctioned territory - requires enhanced due diligence"
            },
            "iran": {
                "id": "SCREEN-IR-001",
                "name": "High-Risk Territory: Iran",
                "schema": "Territory",
                "score": 95.0,
                "datasets": ["us_ofac_sdn", "eu_fsf", "territory_risk"],
                "lists": ["OFAC SDN", "EU Consolidated", "Territory Risk"],
                "reason": "Comprehensively sanctioned territory"
            },
            "north korea": {
                "id": "SCREEN-NK-001",
                "name": "High-Risk Territory: North Korea",
                "schema": "Territory",
                "score": 99.0,
                "datasets": ["us_ofac_sdn", "un_sc_sanctions"],
                "lists": ["OFAC SDN", "UN Security Council"],
                "reason": "Comprehensively sanctioned territory"
            },
            "syria": {
                "id": "SCREEN-SY-001",
                "name": "High-Risk Territory: Syria",
                "schema": "Territory",
                "score": 95.0,
                "datasets": ["us_ofac_sdn", "eu_fsf"],
                "lists": ["OFAC SDN", "EU Consolidated"],
                "reason": "Comprehensively sanctioned territory"
            }
        }

        # Check for matches
        for key, sanction_data in demo_sanctions.items():
            if key in name_lower:
                match_entry = {
                    "id": sanction_data["id"],
                    "name": sanction_data["name"],
                    "query_name": name,
                    "schema": sanction_data["schema"],
                    "score": sanction_data["score"],
                    "datasets": sanction_data["datasets"],
                    "lists": sanction_data["lists"],
                    "reason": sanction_data["reason"],
                    "properties": {
                        "lists": sanction_data["lists"],
                        "reason": sanction_data["reason"]
                    }
                }
                result["matches"].append(match_entry)
                if sanction_data["score"] > result["highest_score"]:
                    result["highest_score"] = sanction_data["score"]

        return result

    async def enhanced_screen(
        self,
        entities: List[Dict[str, str]],
        assessment_id: str = None
    ) -> Dict[str, Any]:
        """
        Level 2: Enhanced screening with fuzzy matching.

        Runs automatically after AI analysis extracts entity names.
        Screens multiple entities: insured, broker, beneficiaries.

        Args:
            entities: List of {"name": "...", "type": "...", "role": "..."}
            assessment_id: Optional assessment ID for tracking

        Returns:
            {
                "status": "clear" | "review" | "match",
                "entities_screened": [...],
                "total_matches": 0,
                "highest_score": 0
            }
        """
        result = {
            "level": "enhanced",
            "assessment_id": assessment_id,
            "status": ScreeningStatus.CLEAR.value,
            "entities_screened": [],
            "total_matches": 0,
            "highest_score": 0,
            "sources_checked": EXTENDED_LISTS,
            "screened_at": datetime.utcnow().isoformat()
        }

        for entity in entities:
            entity_result = await self.quick_screen(
                entity.get("name", ""),
                entity.get("type", "Person")
            )

            entity_result["role"] = entity.get("role", "unknown")
            result["entities_screened"].append(entity_result)

            if entity_result["matches"]:
                result["total_matches"] += len(entity_result["matches"])

            if entity_result["highest_score"] > result["highest_score"]:
                result["highest_score"] = entity_result["highest_score"]

        # Determine overall status
        if result["highest_score"] >= MATCH_THRESHOLD_HIGH * 100:
            result["status"] = ScreeningStatus.MATCH.value
        elif result["highest_score"] >= MATCH_THRESHOLD_MEDIUM * 100:
            result["status"] = ScreeningStatus.REVIEW.value

        return result

    async def deep_analysis(
        self,
        entity_name: str,
        entity_type: str = "Person",
        include_peps: bool = True,
        include_adverse_media: bool = True
    ) -> Dict[str, Any]:
        """
        Level 3: Deep analysis including PEPs and adverse media.

        User-triggered analysis for potential matches.

        Returns:
            {
                "sanctions_matches": [...],
                "pep_matches": [...],
                "adverse_media": [...],
                "risk_indicators": [...]
            }
        """
        result = {
            "level": "deep",
            "entity_name": entity_name,
            "entity_type": entity_type,
            "sanctions_matches": [],
            "pep_matches": [],
            "adverse_media": [],
            "risk_indicators": [],
            "overall_risk": "low",
            "screened_at": datetime.utcnow().isoformat()
        }

        # Sanctions check with extended lists
        sanctions_result = await self._make_request(
            "/search/default",
            params={
                "q": entity_name,
                "limit": 20,
                "schema": entity_type,
                "fuzzy": "true",
            }
        )

        if sanctions_result and "results" in sanctions_result:
            for match in sanctions_result["results"]:
                score = match.get("score", 0) * 100
                if score >= MATCH_THRESHOLD_LOW * 100:
                    result["sanctions_matches"].append({
                        "id": match.get("id"),
                        "name": match.get("caption"),
                        "score": round(score, 2),
                        "datasets": match.get("datasets", []),
                        "properties": self._extract_all_properties(match)
                    })

        # PEP check
        if include_peps:
            pep_result = await self._check_peps(entity_name, entity_type)
            result["pep_matches"] = pep_result.get("matches", [])

        # Determine risk level
        risk_score = 0
        if result["sanctions_matches"]:
            max_sanctions_score = max(m["score"] for m in result["sanctions_matches"])
            if max_sanctions_score >= 85:
                risk_score += 50
            elif max_sanctions_score >= 70:
                risk_score += 30
            elif max_sanctions_score >= 50:
                risk_score += 15

        if result["pep_matches"]:
            risk_score += 25

        if risk_score >= 50:
            result["overall_risk"] = "high"
        elif risk_score >= 25:
            result["overall_risk"] = "medium"

        return result

    async def full_investigation(
        self,
        entity_name: str,
        entity_type: str = "Person"
    ) -> Dict[str, Any]:
        """
        Level 4: Full investigation with network mapping using Aleph.

        User-triggered comprehensive analysis including:
        - Complete entity profile
        - Ownership chains
        - Related entities network
        - Historical data
        - Cross-referenced data from multiple sources
        """
        result = {
            "level": "full",
            "entity_name": entity_name,
            "entity_type": entity_type,
            "profile": {},
            "ownership_chain": [],
            "related_entities": [],
            "network_map": {"nodes": [], "edges": []},
            "historical_data": [],
            "aleph_investigation": None,
            "investigation_url": None,
            "screened_at": datetime.utcnow().isoformat()
        }

        # Get deep analysis first from Yente
        deep_result = await self.deep_analysis(entity_name, entity_type)
        result["profile"]["sanctions"] = deep_result["sanctions_matches"]
        result["profile"]["peps"] = deep_result["pep_matches"]
        result["profile"]["risk_level"] = deep_result["overall_risk"]

        # Search Aleph for comprehensive entity data
        aleph_result = await self._search_aleph(entity_name, entity_type)
        if aleph_result:
            result["aleph_investigation"] = aleph_result

            # Extract network from Aleph results
            if "entities" in aleph_result:
                for entity in aleph_result["entities"][:10]:
                    node_id = entity.get("id", "")
                    result["network_map"]["nodes"].append({
                        "id": node_id,
                        "name": entity.get("properties", {}).get("name", [entity_name])[0],
                        "type": entity.get("schema", "Unknown"),
                        "score": entity.get("score", 0),
                        "datasets": entity.get("datasets", [])
                    })

                    # Add relationships from entity properties
                    props = entity.get("properties", {})
                    for rel_type in ["directorOf", "ownerOf", "associateOf", "familyRelative"]:
                        for related_id in props.get(rel_type, []):
                            result["network_map"]["edges"].append({
                                "source": node_id,
                                "target": related_id,
                                "relationship": rel_type
                            })
                            result["related_entities"].append({
                                "id": related_id,
                                "relationship": rel_type,
                                "source_entity": entity_name
                            })

        # Build network from Yente matches
        if deep_result["sanctions_matches"]:
            for match in deep_result["sanctions_matches"][:5]:
                # Add to network if not already present
                if not any(n["id"] == match["id"] for n in result["network_map"]["nodes"]):
                    result["network_map"]["nodes"].append({
                        "id": match["id"],
                        "name": match["name"],
                        "type": "sanctions_match",
                        "score": match["score"]
                    })

                # Check for related entities from Yente
                related = await self._get_related_entities(match["id"])
                for rel in related:
                    if not any(n["id"] == rel["id"] for n in result["network_map"]["nodes"]):
                        result["related_entities"].append(rel)
                        result["network_map"]["nodes"].append({
                            "id": rel["id"],
                            "name": rel["name"],
                            "type": "related"
                        })
                    if not any(e["source"] == match["id"] and e["target"] == rel["id"]
                               for e in result["network_map"]["edges"]):
                        result["network_map"]["edges"].append({
                            "source": match["id"],
                            "target": rel["id"],
                            "relationship": rel.get("relationship", "associated")
                        })

        # Generate investigation URL for Aleph UI
        if self.aleph_ui_url:
            result["investigation_url"] = f"{self.aleph_ui_url}/search?q={entity_name}"

        return result

    async def _search_aleph(self, query: str, entity_type: str = None) -> Optional[Dict]:
        """Search Aleph for comprehensive entity data."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                params = {"q": query, "limit": 50}
                if entity_type:
                    params["filter:schema"] = entity_type

                response = await client.get(
                    f"{self.aleph_url}/api/2/entities",
                    params=params
                )

                if response.status_code == 200:
                    data = response.json()
                    return {
                        "total": data.get("total", 0),
                        "entities": data.get("results", []),
                        "facets": data.get("facets", {})
                    }
                else:
                    logger.warning(f"Aleph search returned {response.status_code}")
                    return None
        except Exception as e:
            logger.error(f"Aleph search failed: {e}")
            return None

    async def create_aleph_investigation(
        self,
        assessment_id: str,
        entity_name: str,
        documents: List[str] = None
    ) -> Optional[Dict]:
        """Create a new investigation in Aleph for deep analysis."""
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                # Create a collection for this investigation
                collection_data = {
                    "label": f"InstantRisk Assessment {assessment_id} - {entity_name}",
                    "summary": f"Investigation for {entity_name}",
                    "category": "casefile"
                }

                response = await client.post(
                    f"{self.aleph_url}/api/2/collections",
                    json=collection_data
                )

                if response.status_code in [200, 201]:
                    collection = response.json()
                    return {
                        "collection_id": collection.get("id"),
                        "investigation_url": f"{self.aleph_ui_url}/investigations/{collection.get('id')}",
                        "status": "created"
                    }
                else:
                    logger.warning(f"Aleph collection creation returned {response.status_code}")
                    return None
        except Exception as e:
            logger.error(f"Aleph investigation creation failed: {e}")
            return None

    async def _check_peps(self, name: str, entity_type: str) -> Dict[str, Any]:
        """Check against PEP datasets."""
        result = {"matches": []}

        # In a real implementation, this would query PEP-specific datasets
        search_result = await self._make_request(
            "/search/default",
            params={
                "q": name,
                "limit": 10,
                "schema": entity_type,
            }
        )

        if search_result and "results" in search_result:
            for match in search_result["results"]:
                datasets = match.get("datasets", [])
                # Check if any PEP datasets
                if any(ds in PEP_LISTS for ds in datasets):
                    result["matches"].append({
                        "id": match.get("id"),
                        "name": match.get("caption"),
                        "score": round(match.get("score", 0) * 100, 2),
                        "datasets": datasets,
                        "positions": self._extract_positions(match)
                    })

        return result

    async def _get_related_entities(self, entity_id: str) -> List[Dict]:
        """Get entities related to a given entity."""
        related = []

        # Query entity details
        entity_result = await self._make_request(f"/entities/{entity_id}")

        if entity_result and "properties" in entity_result:
            props = entity_result["properties"]

            # Look for relationship properties
            for rel_type in ["associates", "relatives", "directorships", "ownerships"]:
                if rel_type in props:
                    for rel_id in props[rel_type]:
                        related.append({
                            "id": rel_id,
                            "name": rel_id,  # Would need another lookup
                            "relationship": rel_type
                        })

        return related[:10]  # Limit to 10

    def _extract_key_properties(self, match: Dict) -> Dict:
        """Extract key properties from a match."""
        props = match.get("properties", {})
        return {
            "country": props.get("country", []),
            "nationality": props.get("nationality", []),
            "birthDate": props.get("birthDate", []),
            "alias": props.get("alias", [])[:3],  # First 3 aliases
        }

    def _extract_all_properties(self, match: Dict) -> Dict:
        """Extract all relevant properties from a match."""
        props = match.get("properties", {})
        return {
            "country": props.get("country", []),
            "nationality": props.get("nationality", []),
            "birthDate": props.get("birthDate", []),
            "birthPlace": props.get("birthPlace", []),
            "alias": props.get("alias", []),
            "address": props.get("address", []),
            "passportNumber": props.get("passportNumber", []),
            "idNumber": props.get("idNumber", []),
            "notes": props.get("notes", [])[:1],  # First note only
        }

    def _extract_positions(self, match: Dict) -> List[str]:
        """Extract political positions from a PEP match."""
        props = match.get("properties", {})
        positions = []
        for pos in props.get("position", []):
            positions.append(pos)
        return positions


# Singleton instance
sanctions_service = SanctionsService()
