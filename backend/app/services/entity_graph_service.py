"""
InstantRisk V2 - Entity Relationship Graph Service

Builds corporate ownership graphs and detects fraud patterns using:
- Neo4j Community Edition (FREE, graph database)
- OpenCorporates API (500 calls/month FREE)
- Companies House UK API (unlimited, FREE)
- SEC EDGAR (unlimited, FREE)
- NetworkX for in-memory graph algorithms when Neo4j is unavailable

Fraud detection algorithms:
- Circular ownership detection (A -> B -> C -> A)
- Shell company indicators (age, registered address clusters)
- Director concentration risk (same director across many companies)
- Jurisdiction risk scoring (offshore / high-risk territories)
- Beneficial ownership concentration (>25% threshold)
- Related party cluster detection
"""

import os
import json
import logging
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple, Set
from urllib.parse import quote, urlencode
from dataclasses import dataclass, field, asdict

import aiohttp
import networkx as nx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional Neo4j driver - gracefully degrade if not installed / not running
# ---------------------------------------------------------------------------
try:
    from neo4j import AsyncGraphDatabase, AsyncDriver

    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False
    logger.warning("neo4j driver not installed - using NetworkX fallback")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "instantrisk123")

OPENCORPORATES_API_KEY = os.environ.get("OPENCORPORATES_API_KEY", "")
COMPANIES_HOUSE_API_KEY = os.environ.get("COMPANIES_HOUSE_API_KEY", "")

# Jurisdictions flagged as high-risk for fraud / money laundering
HIGH_RISK_JURISDICTIONS = {
    "bvi",
    "british_virgin_islands",
    "cayman_islands",
    "panama",
    "seychelles",
    "marshall_islands",
    "samoa",
    "vanuatu",
    "belize",
    "liberia",
    "bahamas",
    "mauritius",
    "jersey",
    "guernsey",
    "isle_of_man",
    "liechtenstein",
    "andorra",
    "monaco",
    "gibraltar",
    "cyprus",
    "malta",
}

# Minimum company age (years) below which a company is considered suspicious
SHELL_COMPANY_AGE_THRESHOLD_YEARS = 2

# Maximum number of companies a director can control before triggering risk
DIRECTOR_CONCENTRATION_THRESHOLD = 10

# Beneficial ownership threshold (%)
BENEFICIAL_OWNERSHIP_THRESHOLD = 25.0


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class Entity:
    """Represents a legal entity (company, person, trust, fund)."""

    entity_id: str
    name: str
    entity_type: str  # company | person | trust | fund | unknown
    jurisdiction: str = ""
    registration_number: str = ""
    incorporation_date: str = ""
    address: str = ""
    status: str = "active"  # active | dissolved | struck_off | liquidation
    source: str = ""  # opencorporates | companies_house | sec_edgar | manual
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Relationship:
    """Represents an ownership or control relationship between entities."""

    from_id: str
    to_id: str
    relationship_type: str  # owns | controls | directs | shares_address | shareholder
    ownership_pct: float = 0.0
    start_date: str = ""
    end_date: str = ""
    source: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FraudSignal:
    """A detected fraud indicator."""

    signal_type: (
        str  # circular_ownership | shell_company | director_concentration | etc.
    )
    severity: str  # low | medium | high | critical
    description: str
    entities_involved: List[str] = field(default_factory=list)
    confidence: float = 0.0  # 0.0 - 1.0


@dataclass
class EntityGraph:
    """Complete entity graph with fraud analysis results."""

    root_company: str
    entities: List[Entity] = field(default_factory=list)
    relationships: List[Relationship] = field(default_factory=list)
    fraud_signals: List[FraudSignal] = field(default_factory=list)
    overall_fraud_score: int = 0  # 0-100
    risk_level: str = "low"  # low | medium | high | critical
    built_at: str = ""
    sources_used: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Neo4j Graph Manager (with NetworkX fallback)
# ---------------------------------------------------------------------------


class GraphManager:
    """
    Manages the graph database.

    Tries Neo4j first; falls back to an in-memory NetworkX DiGraph so the
    service still works when Neo4j is not running.
    """

    def __init__(self):
        self._driver: Optional[Any] = None
        self._nx_graph: nx.DiGraph = nx.DiGraph()
        self._use_neo4j = False

    async def connect(self) -> bool:
        """Attempt to connect to Neo4j. Returns True if successful."""
        if not NEO4J_AVAILABLE:
            logger.info("GraphManager: neo4j driver not available, using NetworkX")
            return False

        try:
            self._driver = AsyncGraphDatabase.driver(
                NEO4J_URI,
                auth=(NEO4J_USER, NEO4J_PASSWORD),
                connection_timeout=5,
            )
            # Verify connectivity
            async with self._driver.session() as session:
                await session.run("RETURN 1")
            self._use_neo4j = True
            logger.info(f"GraphManager: connected to Neo4j at {NEO4J_URI}")
            return True
        except Exception as e:
            logger.warning(
                f"GraphManager: Neo4j unavailable ({e}), using NetworkX fallback"
            )
            if self._driver:
                await self._driver.close()
            self._driver = None
            self._use_neo4j = False
            return False

    async def close(self):
        if self._driver:
            await self._driver.close()

    async def upsert_entity(self, entity: Entity):
        """Insert or update an entity node."""
        if self._use_neo4j and self._driver:
            async with self._driver.session() as session:
                await session.run(
                    """
                    MERGE (e:Entity {entity_id: $entity_id})
                    SET e.name = $name,
                        e.entity_type = $entity_type,
                        e.jurisdiction = $jurisdiction,
                        e.registration_number = $registration_number,
                        e.incorporation_date = $incorporation_date,
                        e.address = $address,
                        e.status = $status,
                        e.source = $source,
                        e.updated_at = $updated_at
                    """,
                    entity_id=entity.entity_id,
                    name=entity.name,
                    entity_type=entity.entity_type,
                    jurisdiction=entity.jurisdiction,
                    registration_number=entity.registration_number,
                    incorporation_date=entity.incorporation_date,
                    address=entity.address,
                    status=entity.status,
                    source=entity.source,
                    updated_at=datetime.now(timezone.utc).isoformat(),
                )
        else:
            self._nx_graph.add_node(
                entity.entity_id,
                **{k: v for k, v in asdict(entity).items() if k != "metadata"},
            )

    async def upsert_relationship(self, rel: Relationship):
        """Insert or update a relationship edge."""
        if self._use_neo4j and self._driver:
            async with self._driver.session() as session:
                await session.run(
                    """
                    MATCH (a:Entity {entity_id: $from_id})
                    MATCH (b:Entity {entity_id: $to_id})
                    MERGE (a)-[r:RELATES {relationship_type: $rel_type}]->(b)
                    SET r.ownership_pct = $ownership_pct,
                        r.start_date = $start_date,
                        r.end_date = $end_date,
                        r.source = $source,
                        r.updated_at = $updated_at
                    """,
                    from_id=rel.from_id,
                    to_id=rel.to_id,
                    rel_type=rel.relationship_type,
                    ownership_pct=rel.ownership_pct,
                    start_date=rel.start_date,
                    end_date=rel.end_date,
                    source=rel.source,
                    updated_at=datetime.now(timezone.utc).isoformat(),
                )
        else:
            self._nx_graph.add_edge(
                rel.from_id,
                rel.to_id,
                relationship_type=rel.relationship_type,
                ownership_pct=rel.ownership_pct,
                start_date=rel.start_date,
                source=rel.source,
            )

    async def get_subgraph(
        self, root_id: str, depth: int = 3
    ) -> Tuple[List[dict], List[dict]]:
        """
        Return nodes and edges reachable from root_id within given depth.

        Returns:
            (nodes, edges) where each item is a dict
        """
        if self._use_neo4j and self._driver:
            async with self._driver.session() as session:
                result = await session.run(
                    """
                    MATCH path = (root:Entity {entity_id: $root_id})-[*0..3]->(e:Entity)
                    RETURN path
                    """,
                    root_id=root_id,
                )
                nodes = {}
                edges = []
                async for record in result:
                    path = record["path"]
                    for node in path.nodes:
                        nid = node["entity_id"]
                        if nid not in nodes:
                            nodes[nid] = dict(node)
                    for rel in path.relationships:
                        edges.append(
                            {
                                "from_id": rel.start_node["entity_id"],
                                "to_id": rel.end_node["entity_id"],
                                "type": rel["relationship_type"],
                                "ownership_pct": rel.get("ownership_pct", 0),
                            }
                        )
                return list(nodes.values()), edges
        else:
            # NetworkX BFS
            if root_id not in self._nx_graph:
                return [], []
            reachable = nx.bfs_tree(self._nx_graph, root_id, depth_limit=depth)
            nodes = []
            for n in reachable.nodes():
                node_data = self._nx_graph.nodes.get(n, {})
                node_data["entity_id"] = n
                nodes.append(node_data)
            edges = []
            for u, v, data in self._nx_graph.edges(reachable.nodes(), data=True):
                if u in reachable.nodes() and v in reachable.nodes():
                    edges.append({"from_id": u, "to_id": v, **data})
            return nodes, edges

    def get_nx_graph(self) -> nx.DiGraph:
        """Return the underlying NetworkX graph (for algorithm use)."""
        return self._nx_graph


# Singleton graph manager
_graph_manager: Optional[GraphManager] = None


async def get_graph_manager() -> GraphManager:
    global _graph_manager
    if _graph_manager is None:
        _graph_manager = GraphManager()
        await _graph_manager.connect()
    return _graph_manager


# ---------------------------------------------------------------------------
# Data Fetchers
# ---------------------------------------------------------------------------


async def _safe_get(
    session: aiohttp.ClientSession,
    url: str,
    headers: dict = None,
    params: dict = None,
    timeout: int = 10,
) -> Optional[dict]:
    """Safe HTTP GET returning parsed JSON or None on failure."""
    try:
        async with session.get(
            url,
            headers=headers or {},
            params=params or {},
            timeout=aiohttp.ClientTimeout(total=timeout),
        ) as resp:
            if resp.status == 200:
                return await resp.json(content_type=None)
            elif resp.status == 404:
                return None
            else:
                logger.warning(f"HTTP {resp.status} fetching {url}")
                return None
    except Exception as e:
        logger.warning(f"Request failed for {url}: {e}")
        return None


async def fetch_opencorporates_company(
    company_name: str, session: aiohttp.ClientSession
) -> List[Dict[str, Any]]:
    """
    Search OpenCorporates for a company by name.

    Free tier: 500 requests/month (no API key required for basic search).
    API docs: https://api.opencorporates.com/documentation/API-Reference
    """
    try:
        url = "https://api.opencorporates.com/v0.4/companies/search"
        params = {
            "q": company_name,
            "per_page": 10,
            "fields": "name,company_number,jurisdiction_code,incorporation_date,registered_address,current_status",
        }
        if OPENCORPORATES_API_KEY:
            params["api_token"] = OPENCORPORATES_API_KEY

        data = await _safe_get(session, url, params=params)
        if not data:
            return []

        results = data.get("results", {}).get("companies", [])
        companies = []
        for item in results:
            c = item.get("company", {})
            companies.append(
                {
                    "name": c.get("name", ""),
                    "company_number": c.get("company_number", ""),
                    "jurisdiction": c.get("jurisdiction_code", ""),
                    "incorporation_date": c.get("incorporation_date", ""),
                    "status": c.get("current_status", "active"),
                    "registered_address": c.get("registered_address", {}).get(
                        "street_address", ""
                    ),
                    "opencorporates_url": c.get("opencorporates_url", ""),
                    "source": "opencorporates",
                }
            )
        return companies

    except Exception as e:
        logger.warning(f"OpenCorporates search failed: {e}")
        return []


async def fetch_opencorporates_officers(
    company_number: str, jurisdiction: str, session: aiohttp.ClientSession
) -> List[Dict[str, Any]]:
    """Fetch company officers (directors/shareholders) from OpenCorporates."""
    try:
        url = f"https://api.opencorporates.com/v0.4/companies/{jurisdiction}/{company_number}/officers"
        params = {}
        if OPENCORPORATES_API_KEY:
            params["api_token"] = OPENCORPORATES_API_KEY

        data = await _safe_get(session, url, params=params)
        if not data:
            return []

        officers = data.get("results", {}).get("officers", [])
        results = []
        for item in officers:
            o = item.get("officer", {})
            results.append(
                {
                    "name": o.get("name", ""),
                    "role": o.get("position", "director"),
                    "start_date": o.get("start_date", ""),
                    "end_date": o.get("end_date", ""),
                    "source": "opencorporates",
                }
            )
        return results

    except Exception as e:
        logger.warning(f"OpenCorporates officers fetch failed: {e}")
        return []


async def fetch_companies_house_company(
    company_name: str, session: aiohttp.ClientSession
) -> List[Dict[str, Any]]:
    """
    Search Companies House (UK) for a company.

    Free API: https://developer.company-information.service.gov.uk/
    Requires free API key registration.
    """
    if not COMPANIES_HOUSE_API_KEY:
        logger.debug("Companies House API key not configured - skipping")
        return []

    try:
        url = "https://api.company-information.service.gov.uk/search/companies"
        params = {"q": company_name, "items_per_page": 10}
        import base64

        # Companies House uses HTTP Basic Auth: API key as username, empty password
        key_b64 = base64.b64encode(f"{COMPANIES_HOUSE_API_KEY}:".encode()).decode()
        headers = {"Authorization": f"Basic {key_b64}"}

        data = await _safe_get(session, url, headers=headers, params=params)
        if not data:
            return []

        items = data.get("items", [])
        results = []
        for item in items:
            results.append(
                {
                    "name": item.get("title", ""),
                    "company_number": item.get("company_number", ""),
                    "jurisdiction": "gb",
                    "incorporation_date": item.get("date_of_creation", ""),
                    "status": item.get("company_status", "active"),
                    "registered_address": item.get("address_snippet", ""),
                    "company_type": item.get("company_type", ""),
                    "source": "companies_house",
                }
            )
        return results

    except Exception as e:
        logger.warning(f"Companies House search failed: {e}")
        return []


async def fetch_companies_house_psc(
    company_number: str, session: aiohttp.ClientSession
) -> List[Dict[str, Any]]:
    """
    Fetch Persons with Significant Control (PSC) from Companies House.

    PSC = beneficial owners with >25% control - critical for fraud detection.
    """
    if not COMPANIES_HOUSE_API_KEY:
        return []

    try:
        import base64

        url = f"https://api.company-information.service.gov.uk/company/{company_number}/persons-with-significant-control"
        key_b64 = base64.b64encode(f"{COMPANIES_HOUSE_API_KEY}:".encode()).decode()
        headers = {"Authorization": f"Basic {key_b64}"}

        data = await _safe_get(session, url, headers=headers)
        if not data:
            return []

        items = data.get("items", [])
        results = []
        for item in items:
            # Ownership percentage from natures_of_control field
            natures = item.get("natures_of_control", [])
            ownership_pct = 0.0
            for nature in natures:
                if "75-to-100-percent" in nature:
                    ownership_pct = 87.5
                elif "50-to-75-percent" in nature:
                    ownership_pct = 62.5
                elif "25-to-50-percent" in nature:
                    ownership_pct = 37.5

            results.append(
                {
                    "name": item.get("name", ""),
                    "entity_type": "company"
                    if item.get("kind")
                    == "corporate-entity-person-with-significant-control"
                    else "person",
                    "ownership_pct": ownership_pct,
                    "nationality": item.get("nationality", ""),
                    "country_of_residence": item.get("country_of_residence", ""),
                    "notified_on": item.get("notified_on", ""),
                    "natures_of_control": natures,
                    "source": "companies_house_psc",
                }
            )
        return results

    except Exception as e:
        logger.warning(f"Companies House PSC fetch failed: {e}")
        return []


async def fetch_companies_house_officers(
    company_number: str, session: aiohttp.ClientSession
) -> List[Dict[str, Any]]:
    """Fetch company officers from Companies House."""
    if not COMPANIES_HOUSE_API_KEY:
        return []

    try:
        import base64

        url = f"https://api.company-information.service.gov.uk/company/{company_number}/officers"
        key_b64 = base64.b64encode(f"{COMPANIES_HOUSE_API_KEY}:".encode()).decode()
        headers = {"Authorization": f"Basic {key_b64}"}

        data = await _safe_get(session, url, headers=headers)
        if not data:
            return []

        items = data.get("items", [])
        results = []
        for item in items:
            if item.get("resigned_on"):
                continue  # Skip resigned officers
            results.append(
                {
                    "name": item.get("name", ""),
                    "role": item.get("officer_role", "director"),
                    "appointed_on": item.get("appointed_on", ""),
                    "nationality": item.get("nationality", ""),
                    "country_of_residence": item.get("country_of_residence", ""),
                    "source": "companies_house",
                }
            )
        return results

    except Exception as e:
        logger.warning(f"Companies House officers fetch failed: {e}")
        return []


async def fetch_sec_edgar_company(
    company_name: str, session: aiohttp.ClientSession
) -> List[Dict[str, Any]]:
    """
    Search SEC EDGAR for US companies.

    Free API: https://efts.sec.gov/LATEST/search-index?q=...
    Rate limit: 10 req/sec, must include User-Agent header.
    """
    try:
        url = "https://efts.sec.gov/LATEST/search-index"
        params = {
            "q": f'"{company_name}"',
            "dateRange": "custom",
            "startdt": "2020-01-01",
            "forms": "10-K,DEF 14A",
        }
        headers = {
            "User-Agent": "InstantRisk-EntityGraph/1.0 (compliance@instantrisk.com)"
        }

        data = await _safe_get(session, url, headers=headers, params=params)
        if not data:
            return []

        hits = data.get("hits", {}).get("hits", [])
        results = []
        seen_ciks = set()
        for hit in hits[:5]:
            source = hit.get("_source", {})
            cik = source.get("entity_id", "")
            if cik in seen_ciks:
                continue
            seen_ciks.add(cik)
            results.append(
                {
                    "name": source.get("display_names", [company_name])[0]
                    if source.get("display_names")
                    else company_name,
                    "cik": cik,
                    "jurisdiction": "us",
                    "sic_description": source.get("category", ""),
                    "source": "sec_edgar",
                }
            )
        return results

    except Exception as e:
        logger.warning(f"SEC EDGAR search failed: {e}")
        return []


async def fetch_sec_edgar_subsidiaries(
    cik: str, session: aiohttp.ClientSession
) -> List[Dict[str, Any]]:
    """
    Fetch subsidiary companies from SEC EDGAR 10-K subsidiary exhibit.

    Uses the EDGAR submissions API to get company filings and look for
    subsidiary exhibits (EX-21.1).
    """
    try:
        headers = {
            "User-Agent": "InstantRisk-EntityGraph/1.0 (compliance@instantrisk.com)"
        }
        # Pad CIK to 10 digits
        cik_padded = cik.zfill(10)
        url = f"https://data.sec.gov/submissions/CIK{cik_padded}.json"
        data = await _safe_get(session, url, headers=headers)
        if not data:
            return []

        # Look for EX-21.1 (subsidiary list) in recent filings
        filings = data.get("filings", {}).get("recent", {})
        forms = filings.get("form", [])
        accession_numbers = filings.get("accessionNumber", [])

        subsidiaries = []
        for i, form in enumerate(forms):
            if form == "10-K" and i < len(accession_numbers):
                accession = accession_numbers[i].replace("-", "")
                # Fetch filing index
                index_url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{accession}-index.json"
                index_data = await _safe_get(session, index_url, headers=headers)
                if index_data:
                    for doc in index_data.get("directory", {}).get("item", []):
                        if "EX-21" in doc.get("type", ""):
                            # Found subsidiary exhibit - note it (parsing is complex)
                            subsidiaries.append(
                                {
                                    "name": f"Subsidiary exhibit found in 10-K",
                                    "source": "sec_edgar_ex21",
                                    "filing_url": f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{doc.get('name', '')}",
                                }
                            )
                break  # Only check most recent 10-K

        return subsidiaries

    except Exception as e:
        logger.warning(f"SEC EDGAR subsidiaries fetch failed: {e}")
        return []


# ---------------------------------------------------------------------------
# Graph Builder
# ---------------------------------------------------------------------------


class EntityGraphBuilder:
    """
    Builds an entity relationship graph for a given company.

    Orchestrates data fetching from multiple free APIs and stores
    results in Neo4j (or NetworkX fallback).
    """

    def __init__(self):
        self.graph_manager: Optional[GraphManager] = None

    async def build_graph(self, company_name: str, depth: int = 2) -> EntityGraph:
        """
        Build a complete entity graph for the given company name.

        Args:
            company_name: Name of the root company to investigate
            depth: How many levels of ownership to traverse (1-3)

        Returns:
            EntityGraph with all entities, relationships, and fraud signals
        """
        self.graph_manager = await get_graph_manager()

        graph = EntityGraph(
            root_company=company_name,
            built_at=datetime.now(timezone.utc).isoformat(),
        )

        async with aiohttp.ClientSession() as session:
            # Step 1: Find the company in external APIs
            logger.info(f"EntityGraphBuilder: building graph for '{company_name}'")

            oc_results = await fetch_opencorporates_company(company_name, session)
            ch_results = await fetch_companies_house_company(company_name, session)
            sec_results = await fetch_sec_edgar_company(company_name, session)

            sources_used = set()
            if oc_results:
                sources_used.add("opencorporates")
            if ch_results:
                sources_used.add("companies_house")
            if sec_results:
                sources_used.add("sec_edgar")

            graph.sources_used = list(sources_used)

            # Step 2: Build entity nodes from all sources
            root_entity = None
            all_company_data = []

            for result in oc_results[:3]:
                entity = self._company_to_entity(result)
                await self.graph_manager.upsert_entity(entity)
                graph.entities.append(entity)
                all_company_data.append(result)
                if root_entity is None:
                    root_entity = entity

            for result in ch_results[:3]:
                entity = self._company_to_entity(result)
                await self.graph_manager.upsert_entity(entity)
                graph.entities.append(entity)
                all_company_data.append(result)
                if root_entity is None:
                    root_entity = entity

            for result in sec_results[:3]:
                entity = self._company_to_entity(result)
                await self.graph_manager.upsert_entity(entity)
                graph.entities.append(entity)
                all_company_data.append(result)
                if root_entity is None:
                    root_entity = entity

            # If nothing found, create a placeholder root
            if root_entity is None:
                root_entity = Entity(
                    entity_id=f"manual_{company_name.lower().replace(' ', '_')}",
                    name=company_name,
                    entity_type="company",
                    source="manual",
                )
                await self.graph_manager.upsert_entity(root_entity)
                graph.entities.append(root_entity)

            # Step 3: Fetch officers and PSC for each found company
            for company_data in all_company_data:
                company_number = company_data.get("company_number", "")
                jurisdiction = company_data.get("jurisdiction", "")
                source = company_data.get("source", "")

                if source == "companies_house" and company_number:
                    # Fetch PSC (beneficial owners)
                    psc_list = await fetch_companies_house_psc(company_number, session)
                    for psc in psc_list:
                        person_entity = Entity(
                            entity_id=f"psc_{company_number}_{psc['name'].lower().replace(' ', '_')[:30]}",
                            name=psc["name"],
                            entity_type=psc.get("entity_type", "person"),
                            jurisdiction=psc.get("country_of_residence", ""),
                            source="companies_house_psc",
                        )
                        await self.graph_manager.upsert_entity(person_entity)
                        graph.entities.append(person_entity)

                        rel = Relationship(
                            from_id=person_entity.entity_id,
                            to_id=f"ch_{company_number}",
                            relationship_type="controls",
                            ownership_pct=psc.get("ownership_pct", 0.0),
                            start_date=psc.get("notified_on", ""),
                            source="companies_house_psc",
                        )
                        await self.graph_manager.upsert_relationship(rel)
                        graph.relationships.append(rel)

                    # Fetch officers
                    officers = await fetch_companies_house_officers(
                        company_number, session
                    )
                    for officer in officers:
                        officer_entity = Entity(
                            entity_id=f"officer_{company_number}_{officer['name'].lower().replace(' ', '_')[:30]}",
                            name=officer["name"],
                            entity_type="person",
                            jurisdiction=officer.get("country_of_residence", ""),
                            source="companies_house",
                        )
                        await self.graph_manager.upsert_entity(officer_entity)
                        graph.entities.append(officer_entity)

                        rel = Relationship(
                            from_id=officer_entity.entity_id,
                            to_id=f"ch_{company_number}",
                            relationship_type="directs",
                            start_date=officer.get("appointed_on", ""),
                            source="companies_house",
                        )
                        await self.graph_manager.upsert_relationship(rel)
                        graph.relationships.append(rel)

                elif source == "opencorporates" and company_number and jurisdiction:
                    officers = await fetch_opencorporates_officers(
                        company_number, jurisdiction, session
                    )
                    for officer in officers:
                        officer_entity = Entity(
                            entity_id=f"oc_officer_{jurisdiction}_{company_number}_{officer['name'].lower().replace(' ', '_')[:30]}",
                            name=officer["name"],
                            entity_type="person",
                            source="opencorporates",
                        )
                        await self.graph_manager.upsert_entity(officer_entity)
                        graph.entities.append(officer_entity)

                        rel = Relationship(
                            from_id=officer_entity.entity_id,
                            to_id=f"oc_{jurisdiction}_{company_number}",
                            relationship_type="directs",
                            start_date=officer.get("start_date", ""),
                            source="opencorporates",
                        )
                        await self.graph_manager.upsert_relationship(rel)
                        graph.relationships.append(rel)

                elif source == "sec_edgar":
                    cik = company_data.get("cik", "")
                    if cik:
                        subsidiaries = await fetch_sec_edgar_subsidiaries(cik, session)
                        for sub in subsidiaries:
                            sub_entity = Entity(
                                entity_id=f"sec_sub_{cik}_{len(graph.entities)}",
                                name=sub["name"],
                                entity_type="company",
                                jurisdiction="us",
                                source="sec_edgar",
                            )
                            await self.graph_manager.upsert_entity(sub_entity)
                            graph.entities.append(sub_entity)

                            rel = Relationship(
                                from_id=f"sec_{cik}",
                                to_id=sub_entity.entity_id,
                                relationship_type="owns",
                                source="sec_edgar",
                            )
                            await self.graph_manager.upsert_relationship(rel)
                            graph.relationships.append(rel)

        # Step 4: Run fraud detection algorithms
        graph.fraud_signals = self._detect_fraud_patterns(graph)

        # Step 5: Calculate overall fraud score
        graph.overall_fraud_score, graph.risk_level = self._calculate_fraud_score(
            graph.fraud_signals
        )

        logger.info(
            f"EntityGraphBuilder: graph built for '{company_name}' - "
            f"{len(graph.entities)} entities, {len(graph.relationships)} relationships, "
            f"{len(graph.fraud_signals)} fraud signals, score={graph.overall_fraud_score}"
        )
        return graph

    def _company_to_entity(self, data: dict) -> Entity:
        """Convert raw API company data to an Entity object."""
        source = data.get("source", "unknown")
        company_number = data.get("company_number", "")
        jurisdiction = data.get("jurisdiction", "")

        if source == "companies_house":
            entity_id = (
                f"ch_{company_number}"
                if company_number
                else f"ch_{data['name'].lower().replace(' ', '_')[:40]}"
            )
        elif source == "opencorporates":
            entity_id = (
                f"oc_{jurisdiction}_{company_number}"
                if company_number
                else f"oc_{data['name'].lower().replace(' ', '_')[:40]}"
            )
        elif source == "sec_edgar":
            cik = data.get("cik", "")
            entity_id = (
                f"sec_{cik}"
                if cik
                else f"sec_{data['name'].lower().replace(' ', '_')[:40]}"
            )
        else:
            entity_id = f"manual_{data['name'].lower().replace(' ', '_')[:40]}"

        return Entity(
            entity_id=entity_id,
            name=data.get("name", ""),
            entity_type="company",
            jurisdiction=jurisdiction or data.get("jurisdiction", ""),
            registration_number=company_number,
            incorporation_date=data.get("incorporation_date", ""),
            address=data.get("registered_address", ""),
            status=data.get("status", "active"),
            source=source,
        )

    # -------------------------------------------------------------------------
    # Fraud Detection Algorithms
    # -------------------------------------------------------------------------

    def _detect_fraud_patterns(self, graph: EntityGraph) -> List[FraudSignal]:
        """
        Run all fraud detection algorithms on the entity graph.

        Returns list of FraudSignal objects.
        """
        signals: List[FraudSignal] = []

        # Build an in-memory NetworkX graph for algorithm use
        G = nx.DiGraph()
        for entity in graph.entities:
            G.add_node(
                entity.entity_id,
                **{
                    "name": entity.name,
                    "entity_type": entity.entity_type,
                    "jurisdiction": entity.jurisdiction,
                    "incorporation_date": entity.incorporation_date,
                    "status": entity.status,
                },
            )
        for rel in graph.relationships:
            G.add_edge(
                rel.from_id,
                rel.to_id,
                **{
                    "relationship_type": rel.relationship_type,
                    "ownership_pct": rel.ownership_pct,
                },
            )

        # Algorithm 1: Circular Ownership Detection
        signals.extend(self._detect_circular_ownership(G, graph))

        # Algorithm 2: Shell Company Detection
        signals.extend(self._detect_shell_companies(graph))

        # Algorithm 3: Director Concentration Risk
        signals.extend(self._detect_director_concentration(graph))

        # Algorithm 4: High-Risk Jurisdiction Flags
        signals.extend(self._detect_jurisdiction_risk(graph))

        # Algorithm 5: Beneficial Ownership Concentration
        signals.extend(self._detect_ownership_concentration(graph, G))

        # Algorithm 6: Dissolved/Struck-off Entity Relationships
        signals.extend(self._detect_zombie_entities(graph))

        # Algorithm 7: Address Clustering (multiple companies same address)
        signals.extend(self._detect_address_clustering(graph))

        return signals

    def _detect_circular_ownership(
        self, G: nx.DiGraph, graph: EntityGraph
    ) -> List[FraudSignal]:
        """
        Detect circular ownership structures (A owns B owns C owns A).

        Uses NetworkX simple_cycles() to find all cycles in the directed graph.
        """
        signals = []
        try:
            cycles = list(nx.simple_cycles(G))
            for cycle in cycles:
                if len(cycle) >= 2:
                    # Get entity names for the cycle
                    names = []
                    for node_id in cycle:
                        node_data = G.nodes.get(node_id, {})
                        names.append(node_data.get("name", node_id))

                    cycle_desc = " -> ".join(names) + f" -> {names[0]}"
                    severity = "critical" if len(cycle) <= 3 else "high"
                    signals.append(
                        FraudSignal(
                            signal_type="circular_ownership",
                            severity=severity,
                            description=f"Circular ownership detected: {cycle_desc}. "
                            f"This structure is commonly used to conceal true ownership "
                            f"and may indicate fraud or tax evasion.",
                            entities_involved=cycle,
                            confidence=0.95,
                        )
                    )
        except Exception as e:
            logger.warning(f"Circular ownership detection failed: {e}")

        return signals

    def _detect_shell_companies(self, graph: EntityGraph) -> List[FraudSignal]:
        """
        Detect potential shell companies based on:
        - Very recent incorporation date (< 2 years old)
        - Dissolved or struck-off status
        - Offshore jurisdiction
        """
        signals = []
        current_year = datetime.now().year

        for entity in graph.entities:
            if entity.entity_type != "company":
                continue

            indicators = []

            # Check incorporation date
            if entity.incorporation_date:
                try:
                    # Handle multiple date formats
                    date_str = entity.incorporation_date[:10]  # YYYY-MM-DD
                    inc_year = int(date_str[:4])
                    age_years = current_year - inc_year
                    if age_years < SHELL_COMPANY_AGE_THRESHOLD_YEARS:
                        indicators.append(
                            f"incorporated {age_years} year(s) ago (very new)"
                        )
                except (ValueError, IndexError):
                    pass

            # Check jurisdiction
            jurisdiction_lower = (entity.jurisdiction or "").lower()
            if jurisdiction_lower in HIGH_RISK_JURISDICTIONS:
                indicators.append(
                    f"registered in high-risk jurisdiction: {entity.jurisdiction}"
                )

            # Check status
            if entity.status and entity.status.lower() in (
                "dissolved",
                "struck-off",
                "struck_off",
                "liquidation",
            ):
                indicators.append(f"company status: {entity.status}")

            if len(indicators) >= 2:
                signals.append(
                    FraudSignal(
                        signal_type="shell_company",
                        severity="high" if len(indicators) >= 3 else "medium",
                        description=f"Potential shell company detected: '{entity.name}'. "
                        f"Indicators: {'; '.join(indicators)}.",
                        entities_involved=[entity.entity_id],
                        confidence=min(0.4 + 0.2 * len(indicators), 0.9),
                    )
                )
            elif len(indicators) == 1 and "jurisdiction" in indicators[0]:
                signals.append(
                    FraudSignal(
                        signal_type="offshore_entity",
                        severity="low",
                        description=f"Entity '{entity.name}' is registered in a high-risk jurisdiction: {entity.jurisdiction}.",
                        entities_involved=[entity.entity_id],
                        confidence=0.5,
                    )
                )

        return signals

    def _detect_director_concentration(self, graph: EntityGraph) -> List[FraudSignal]:
        """
        Detect directors who control an abnormally large number of companies.

        A legitimate business person might control 2-3 companies. Controlling
        10+ may indicate a nominee director arrangement or fraud network.
        """
        signals = []

        # Count company directorships per person
        director_companies: Dict[str, List[str]] = {}
        for rel in graph.relationships:
            if rel.relationship_type in ("directs", "controls"):
                director_id = rel.from_id
                company_id = rel.to_id
                if director_id not in director_companies:
                    director_companies[director_id] = []
                director_companies[director_id].append(company_id)

        for director_id, company_ids in director_companies.items():
            # Find director name
            director_name = director_id
            for entity in graph.entities:
                if entity.entity_id == director_id:
                    director_name = entity.name
                    break

            count = len(company_ids)
            if count >= DIRECTOR_CONCENTRATION_THRESHOLD:
                signals.append(
                    FraudSignal(
                        signal_type="director_concentration",
                        severity="critical" if count >= 20 else "high",
                        description=f"Director '{director_name}' controls {count} companies in this graph "
                        f"(threshold: {DIRECTOR_CONCENTRATION_THRESHOLD}). "
                        f"This may indicate a nominee director arrangement or fraud network.",
                        entities_involved=[director_id] + company_ids,
                        confidence=min(
                            0.5 + (count - DIRECTOR_CONCENTRATION_THRESHOLD) * 0.02,
                            0.95,
                        ),
                    )
                )
            elif 5 <= count < DIRECTOR_CONCENTRATION_THRESHOLD:
                signals.append(
                    FraudSignal(
                        signal_type="director_concentration",
                        severity="medium",
                        description=f"Director '{director_name}' appears in {count} companies. "
                        f"Worth monitoring for nominee director arrangements.",
                        entities_involved=[director_id] + company_ids,
                        confidence=0.4,
                    )
                )

        return signals

    def _detect_jurisdiction_risk(self, graph: EntityGraph) -> List[FraudSignal]:
        """
        Score jurisdiction risk across the corporate structure.

        High concentration of offshore entities raises overall risk.
        """
        signals = []
        company_entities = [e for e in graph.entities if e.entity_type == "company"]
        if not company_entities:
            return signals

        offshore_entities = [
            e
            for e in company_entities
            if (e.jurisdiction or "").lower() in HIGH_RISK_JURISDICTIONS
        ]

        offshore_pct = len(offshore_entities) / len(company_entities) * 100

        if offshore_pct >= 50:
            signals.append(
                FraudSignal(
                    signal_type="jurisdiction_risk",
                    severity="critical",
                    description=f"{offshore_pct:.0f}% of entities ({len(offshore_entities)}/{len(company_entities)}) "
                    f"are registered in high-risk jurisdictions. "
                    f"This is a strong indicator of deliberate offshore structuring.",
                    entities_involved=[e.entity_id for e in offshore_entities],
                    confidence=0.85,
                )
            )
        elif offshore_pct >= 25:
            signals.append(
                FraudSignal(
                    signal_type="jurisdiction_risk",
                    severity="high",
                    description=f"{offshore_pct:.0f}% of entities are in high-risk jurisdictions.",
                    entities_involved=[e.entity_id for e in offshore_entities],
                    confidence=0.7,
                )
            )
        elif offshore_pct > 0:
            signals.append(
                FraudSignal(
                    signal_type="jurisdiction_risk",
                    severity="low",
                    description=f"{len(offshore_entities)} entity/entities in potentially high-risk jurisdiction(s).",
                    entities_involved=[e.entity_id for e in offshore_entities],
                    confidence=0.4,
                )
            )

        return signals

    def _detect_ownership_concentration(
        self, graph: EntityGraph, G: nx.DiGraph
    ) -> List[FraudSignal]:
        """
        Detect entities with >25% beneficial ownership (UK/EU threshold).

        High ownership concentration without disclosure is a fraud risk.
        Entities with majority (>50%) or outright (>75%) control flagged separately.
        """
        signals = []

        for rel in graph.relationships:
            if rel.ownership_pct <= 0:
                continue

            from_entity = next(
                (e for e in graph.entities if e.entity_id == rel.from_id), None
            )
            to_entity = next(
                (e for e in graph.entities if e.entity_id == rel.to_id), None
            )

            owner_name = from_entity.name if from_entity else rel.from_id
            company_name = to_entity.name if to_entity else rel.to_id

            if rel.ownership_pct >= 75:
                signals.append(
                    FraudSignal(
                        signal_type="ownership_concentration",
                        severity="medium",
                        description=f"'{owner_name}' holds {rel.ownership_pct:.1f}% of '{company_name}'. "
                        f"Near-total control may mask beneficial owner identity.",
                        entities_involved=[rel.from_id, rel.to_id],
                        confidence=0.6,
                    )
                )
            elif rel.ownership_pct >= BENEFICIAL_OWNERSHIP_THRESHOLD:
                signals.append(
                    FraudSignal(
                        signal_type="ownership_concentration",
                        severity="low",
                        description=f"'{owner_name}' holds {rel.ownership_pct:.1f}% of '{company_name}' "
                        f"(exceeds {BENEFICIAL_OWNERSHIP_THRESHOLD}% PSC threshold).",
                        entities_involved=[rel.from_id, rel.to_id],
                        confidence=0.5,
                    )
                )

        return signals

    def _detect_zombie_entities(self, graph: EntityGraph) -> List[FraudSignal]:
        """
        Detect active relationships involving dissolved or struck-off companies.

        Active companies owning dissolved shells is a red flag for asset stripping.
        """
        signals = []

        dissolved_ids = {
            e.entity_id
            for e in graph.entities
            if e.status
            and e.status.lower()
            in ("dissolved", "struck-off", "struck_off", "liquidation")
        }

        for rel in graph.relationships:
            if rel.to_id in dissolved_ids or rel.from_id in dissolved_ids:
                involved = [rel.from_id, rel.to_id]
                dissolved = rel.to_id if rel.to_id in dissolved_ids else rel.from_id
                entity = next(
                    (e for e in graph.entities if e.entity_id == dissolved), None
                )
                name = entity.name if entity else dissolved

                signals.append(
                    FraudSignal(
                        signal_type="zombie_entity",
                        severity="medium",
                        description=f"Active relationship involving dissolved/struck-off entity '{name}'. "
                        f"May indicate historical asset stripping or undisclosed liabilities.",
                        entities_involved=involved,
                        confidence=0.7,
                    )
                )

        return signals

    def _detect_address_clustering(self, graph: EntityGraph) -> List[FraudSignal]:
        """
        Detect multiple companies sharing the same registered address.

        Legitimate use: shared office buildings.
        Suspicious use: many shell companies at a single "virtual office" address.
        Threshold: 3+ companies at same address = medium risk.
        """
        signals = []

        address_companies: Dict[str, List[str]] = {}
        for entity in graph.entities:
            if entity.entity_type == "company" and entity.address:
                addr_key = entity.address.lower().strip()
                if addr_key not in address_companies:
                    address_companies[addr_key] = []
                address_companies[addr_key].append(entity.entity_id)

        for address, entity_ids in address_companies.items():
            count = len(entity_ids)
            if count >= 5:
                signals.append(
                    FraudSignal(
                        signal_type="address_clustering",
                        severity="high",
                        description=f"{count} companies share the same registered address: '{address[:80]}'. "
                        f"This pattern is associated with mass-registered shell companies.",
                        entities_involved=entity_ids,
                        confidence=min(0.4 + count * 0.05, 0.9),
                    )
                )
            elif count >= 3:
                signals.append(
                    FraudSignal(
                        signal_type="address_clustering",
                        severity="medium",
                        description=f"{count} companies share the address '{address[:80]}'. "
                        f"May warrant additional verification.",
                        entities_involved=entity_ids,
                        confidence=0.5,
                    )
                )

        return signals

    def _calculate_fraud_score(self, signals: List[FraudSignal]) -> Tuple[int, str]:
        """
        Calculate an overall fraud score (0-100) and risk level.

        Severity weights:
            critical = 25 points
            high     = 15 points
            medium   = 7 points
            low      = 2 points
        Score is capped at 100.
        """
        severity_weights = {
            "critical": 25,
            "high": 15,
            "medium": 7,
            "low": 2,
        }

        score = 0
        for signal in signals:
            base = severity_weights.get(signal.severity, 0)
            score += int(base * signal.confidence)

        score = min(score, 100)

        if score >= 70:
            risk_level = "critical"
        elif score >= 45:
            risk_level = "high"
        elif score >= 20:
            risk_level = "medium"
        else:
            risk_level = "low"

        return score, risk_level


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def build_entity_graph(company_name: str, depth: int = 2) -> EntityGraph:
    """
    Build a full entity graph for a company.

    Args:
        company_name: Legal name of the company to investigate
        depth: Ownership traversal depth (1-3)

    Returns:
        EntityGraph with entities, relationships, and fraud signals
    """
    builder = EntityGraphBuilder()
    return await builder.build_graph(company_name, depth=depth)


async def get_entity_graph(
    company_name: str,
) -> Optional[Tuple[List[dict], List[dict]]]:
    """
    Retrieve an existing entity graph from the graph database.

    Args:
        company_name: Company name (used as root node lookup)

    Returns:
        (nodes, edges) or None if not found
    """
    gm = await get_graph_manager()

    # First try name-slug candidates (legacy/manual entries)
    name_slug = company_name.lower().replace(" ", "_")[:40]
    root_candidates = [
        f"ch_{name_slug}",
        f"oc_gb_{name_slug}",
        f"sec_{name_slug}",
        f"manual_{name_slug}",
    ]
    for root_id in root_candidates:
        nodes, edges = await gm.get_subgraph(root_id, depth=3)
        if nodes:
            return nodes, edges

    # If not found by name slug, search all nodes for a matching company name
    # This handles the case where entity_id uses registration number (e.g. ch_12345678)
    nx_graph = gm.get_nx_graph()
    if nx_graph is not None and len(nx_graph) > 0:
        for node_id, data in nx_graph.nodes(data=True):
            node_name = (data.get("name") or "").lower()
            if node_name and (
                node_name == company_name.lower() or company_name.lower() in node_name
            ):
                nodes, edges = await gm.get_subgraph(node_id, depth=3)
                if nodes:
                    return nodes, edges

    # If still not found, build the graph on-the-fly via Companies House
    try:
        graph = await build_entity_graph(company_name, depth=2)
        if graph and graph.entities:
            nodes = [
                {
                    "id": e.entity_id,
                    "name": e.name,
                    "type": e.entity_type,
                    "jurisdiction": e.jurisdiction,
                    "registration_number": e.registration_number,
                    "status": e.status,
                    "source": e.source,
                }
                for e in graph.entities
            ]
            edges = [
                {
                    "from_id": r.from_id,
                    "to_id": r.to_id,
                    "type": r.relationship_type,
                    "ownership_pct": r.ownership_pct,
                    "source": r.source,
                }
                for r in graph.relationships
            ]
            return nodes, edges
    except Exception as e:
        import logging

        logging.getLogger(__name__).warning(
            f"Auto-build entity graph failed for {company_name}: {e}"
        )

    return None


def entity_graph_to_dict(graph: EntityGraph) -> dict:
    """
    Serialize EntityGraph to a JSON-serializable dict for API responses.
    """
    return {
        "root_company": graph.root_company,
        "built_at": graph.built_at,
        "sources_used": graph.sources_used,
        "overall_fraud_score": graph.overall_fraud_score,
        "risk_level": graph.risk_level,
        "entity_count": len(graph.entities),
        "relationship_count": len(graph.relationships),
        "fraud_signal_count": len(graph.fraud_signals),
        "entities": [
            {
                "entity_id": e.entity_id,
                "name": e.name,
                "entity_type": e.entity_type,
                "jurisdiction": e.jurisdiction,
                "registration_number": e.registration_number,
                "incorporation_date": e.incorporation_date,
                "address": e.address,
                "status": e.status,
                "source": e.source,
            }
            for e in graph.entities
        ],
        "relationships": [
            {
                "from_id": r.from_id,
                "to_id": r.to_id,
                "relationship_type": r.relationship_type,
                "ownership_pct": r.ownership_pct,
                "start_date": r.start_date,
                "source": r.source,
            }
            for r in graph.relationships
        ],
        "fraud_signals": [
            {
                "signal_type": s.signal_type,
                "severity": s.severity,
                "description": s.description,
                "entities_involved": s.entities_involved,
                "confidence": s.confidence,
            }
            for s in graph.fraud_signals
        ],
        "errors": graph.errors,
    }
