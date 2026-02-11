"""
InstantRisk V3 - LMA Clauses Service

Comprehensive LMA clause management service providing:
- Clause lookup and search
- Risk-based recommendations
- Pricing impact calculation
- Custom clause management
"""

import json
import os
from typing import Dict, List, Optional, Any
from decimal import Decimal


class LMAClausesService:
    """Service for managing and recommending LMA clauses."""

    def __init__(self):
        self._clauses: List[Dict[str, Any]] = []
        self._categories: Dict[str, str] = {}
        self._load_clauses()

    def _load_clauses(self):
        """Load clauses from V3 template files."""
        # V3 clause templates location
        clauses_base_path = "/app/data/templates/clauses"

        self._clauses = []
        self._categories = {}

        # Load clauses from by_type directory
        by_type_path = os.path.join(clauses_base_path, "by_type")
        if os.path.exists(by_type_path):
            for filename in os.listdir(by_type_path):
                if filename.endswith(".json"):
                    filepath = os.path.join(by_type_path, filename)
                    try:
                        with open(filepath, "r") as f:
                            data = json.load(f)
                            clause_type = data.get("type", filename.replace(".json", ""))
                            self._categories[clause_type] = data.get("name", clause_type.title())

                            # Add clauses with category info
                            for clause in data.get("clauses", []):
                                clause["category"] = clause_type
                                clause["description"] = clause.get("text", "")[:200] + "..." if len(clause.get("text", "")) > 200 else clause.get("text", "")
                                self._clauses.append(clause)
                    except (json.JSONDecodeError, IOError) as e:
                        print(f"Error loading {filepath}: {e}")

        # Load clauses from by_line directory
        by_line_path = os.path.join(clauses_base_path, "by_line")
        if os.path.exists(by_line_path):
            for filename in os.listdir(by_line_path):
                if filename.endswith(".json"):
                    filepath = os.path.join(by_line_path, filename)
                    try:
                        with open(filepath, "r") as f:
                            data = json.load(f)
                            for clause in data.get("clauses", []):
                                # Avoid duplicates
                                if not any(c["id"] == clause["id"] for c in self._clauses):
                                    clause["category"] = data.get("line_of_business", "general")
                                    clause["description"] = clause.get("text", "")[:200] + "..." if len(clause.get("text", "")) > 200 else clause.get("text", "")
                                    self._clauses.append(clause)
                    except (json.JSONDecodeError, IOError) as e:
                        print(f"Error loading {filepath}: {e}")

        # Load Lloyd's specific clauses
        lloyd_path = os.path.join(clauses_base_path, "lloyd_specific")
        if os.path.exists(lloyd_path):
            for filename in os.listdir(lloyd_path):
                if filename.endswith(".json"):
                    filepath = os.path.join(lloyd_path, filename)
                    try:
                        with open(filepath, "r") as f:
                            data = json.load(f)
                            for clause in data.get("clauses", []):
                                if not any(c["id"] == clause["id"] for c in self._clauses):
                                    clause["category"] = "lloyds"
                                    clause["description"] = clause.get("text", "")[:200] + "..." if len(clause.get("text", "")) > 200 else clause.get("text", "")
                                    self._clauses.append(clause)
                    except (json.JSONDecodeError, IOError) as e:
                        print(f"Error loading {filepath}: {e}")

    def get_all_clauses(self) -> List[Dict[str, Any]]:
        """Get all available clauses."""
        return self._clauses

    def get_clause_by_id(self, clause_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific clause by ID."""
        for clause in self._clauses:
            if clause["id"] == clause_id:
                return clause
        return None

    def get_clauses_by_category(self, category: str) -> List[Dict[str, Any]]:
        """Get clauses filtered by category."""
        return [c for c in self._clauses if c.get("category") == category]

    def get_mandatory_clauses(self) -> List[Dict[str, Any]]:
        """Get all mandatory clauses that should be included in every policy."""
        return [c for c in self._clauses if c.get("mandatory", False)]

    def search_clauses(self, query: str) -> List[Dict[str, Any]]:
        """Search clauses by name or description."""
        query_lower = query.lower()
        return [
            c for c in self._clauses
            if query_lower in c.get("name", "").lower()
            or query_lower in c.get("description", "").lower()
            or query_lower in c.get("id", "").lower()
        ]

    def get_exclusions(self) -> List[Dict[str, Any]]:
        """Get all exclusion clauses."""
        return [c for c in self._clauses if c.get("is_exclusion", False)]

    def recommend_clauses(
        self,
        risk_category: str,
        territory: Optional[str] = None,
        perils: Optional[List[str]] = None,
        sum_insured: Optional[float] = None,
        special_features: Optional[List[str]] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Recommend clauses based on risk profile.

        Returns:
            Dictionary with 'mandatory', 'recommended', and 'optional' clause lists.
        """
        mandatory = []
        recommended = []
        optional = []

        # Core mandatory clauses for ALL policies (Lloyd's market standard)
        core_mandatory_ids = [
            "LMA5096",  # Several Liability Clause
            "LMA5001",  # Premium Payment Clause
            "LMA5121",  # Nuclear Incident Exclusion
            "LMA5212",  # War Exclusion Clause
        ]

        # Sanctions clauses - always mandatory
        sanctions_mandatory_ids = [
            "LMA3100",  # Sanctions Limitation and Exclusion
        ]

        # Add core mandatory clauses
        for clause_id in core_mandatory_ids + sanctions_mandatory_ids:
            clause = self.get_clause_by_id(clause_id)
            if clause:
                clause["mandatory"] = True
                mandatory.append(clause)
            else:
                # Create placeholder if not in library
                mandatory.append({
                    "id": clause_id,
                    "name": f"Standard Clause {clause_id}",
                    "category": "general",
                    "mandatory": True
                })

        # Also include any that have mandatory=True in the loaded data
        mandatory.extend([c for c in self.get_mandatory_clauses() if c not in mandatory])

        # Category-specific MANDATORY clauses (pre-selected)
        category_mandatory = {
            "marine": ["ICC-A"],
            "cargo": ["ICC-A"],
            "cyber": ["LMA5400", "LMA5401"],
            "property": ["LMA3100"],
            "aviation": ["AVN1", "AVN48B"],
            "professional": ["LMA3001", "LMA3002"],
            "professional_lines": ["LMA3001", "LMA3002"],
        }

        # Category-specific RECOMMENDED clauses
        category_recommended = {
            "marine": ["ICC-B", "ICC-C", "IWC-CARGO", "ISC-CARGO", "ITC-HULLS"],
            "cargo": ["ICC-B", "ICC-C", "IWC-CARGO", "ISC-CARGO"],
            "aviation": ["AVN48", "AVN52E"],
            "property": ["LMA3102", "LMA5014"],
            "casualty": ["LMA3200", "LMA3201"],
            "liability": ["LMA3200", "LMA3201"],
            "professional_lines": ["LSW1600", "LSW1601", "LMA3003"],
            "professional": ["LSW1600", "LSW1601", "LMA3003"],
            "reinsurance": ["LMA9001", "LMA9103", "LMA9106"],
            "energy": ["LSW555", "LSW1001"],
            "cyber": ["LMA5402"],
        }

        risk_category_lower = risk_category.lower().replace(" ", "_")

        # Add category-specific mandatory clauses
        for clause_id in category_mandatory.get(risk_category_lower, []):
            clause = self.get_clause_by_id(clause_id)
            if clause and clause not in mandatory:
                clause["mandatory"] = True
                mandatory.append(clause)

        # Add category-specific recommended clauses
        for clause_id in category_recommended.get(risk_category_lower, []):
            clause = self.get_clause_by_id(clause_id)
            if clause and clause not in mandatory and clause not in recommended:
                recommended.append(clause)

        # Territory-specific recommendations
        if territory:
            territory_lower = territory.lower()
            if "us" in territory_lower or "united states" in territory_lower:
                us_clauses = ["LMA5148", "LMA5255"]
                for clause_id in us_clauses:
                    clause = self.get_clause_by_id(clause_id)
                    if clause and clause not in mandatory and clause not in recommended:
                        recommended.append(clause)

            if "uk" in territory_lower or "england" in territory_lower:
                uk_clauses = ["LMA5147", "LMA5253"]
                for clause_id in uk_clauses:
                    clause = self.get_clause_by_id(clause_id)
                    if clause and clause not in mandatory and clause not in recommended:
                        recommended.append(clause)

        # Peril-specific recommendations
        if perils:
            peril_mappings = {
                "war": ["LMA5212", "LMA5213"],
                "terrorism": ["LMA5253", "LMA5254", "LMA5255"],
                "cyber": ["LMA5400", "LMA5401", "LMA5402"],
                "pandemic": ["LMA5393", "LMA5394", "LMA5395"],
            }
            for peril in perils:
                peril_lower = peril.lower()
                for key, clause_ids in peril_mappings.items():
                    if key in peril_lower:
                        for clause_id in clause_ids:
                            clause = self.get_clause_by_id(clause_id)
                            if clause and clause not in mandatory and clause not in recommended:
                                optional.append(clause)

        # Special feature recommendations
        if special_features:
            features_lower = [f.lower() for f in special_features]
            if "cryptocurrency" in features_lower or "crypto" in features_lower:
                clause = self.get_clause_by_id("CRYPTO-EXCL")
                if clause:
                    recommended.append(clause)
            if "ai" in features_lower or "artificial intelligence" in features_lower:
                clause = self.get_clause_by_id("AI-EXCL")
                if clause:
                    recommended.append(clause)
            if "climate" in features_lower or "esg" in features_lower:
                clause = self.get_clause_by_id("CLIMATE-EXCL")
                if clause:
                    recommended.append(clause)

        # Large risk recommendations
        if sum_insured and sum_insured > 50000000:
            # For large risks, recommend additional exclusions
            large_risk_clauses = ["LMA5400", "LMA5393", "SUPPLY-CHAIN-EXCL"]
            for clause_id in large_risk_clauses:
                clause = self.get_clause_by_id(clause_id)
                if clause and clause not in mandatory and clause not in recommended:
                    optional.append(clause)

        # Remove duplicates
        seen_ids = set()
        unique_mandatory = []
        for c in mandatory:
            if c["id"] not in seen_ids:
                seen_ids.add(c["id"])
                unique_mandatory.append(c)

        unique_recommended = []
        for c in recommended:
            if c["id"] not in seen_ids:
                seen_ids.add(c["id"])
                unique_recommended.append(c)

        unique_optional = []
        for c in optional:
            if c["id"] not in seen_ids:
                seen_ids.add(c["id"])
                unique_optional.append(c)

        return {
            "mandatory": unique_mandatory,
            "recommended": unique_recommended,
            "optional": unique_optional,
        }

    def calculate_pricing_impact(
        self,
        base_premium: float,
        selected_clauses: List[str]
    ) -> Dict[str, Any]:
        """
        Calculate premium impact based on selected clauses.

        Args:
            base_premium: The base premium before adjustments
            selected_clauses: List of clause IDs that are selected

        Returns:
            Dictionary with pricing breakdown
        """
        adjustments = []
        total_impact_pct = Decimal("0")

        for clause_id in selected_clauses:
            clause = self.get_clause_by_id(clause_id)
            if clause:
                impact_pct = Decimal(str(clause.get("pricing_impact", 0)))
                if impact_pct != 0:
                    impact_amount = (Decimal(str(base_premium)) * impact_pct) / 100
                    adjustments.append({
                        "clause_id": clause_id,
                        "clause_name": clause.get("name"),
                        "impact_percentage": float(impact_pct),
                        "impact_amount": float(impact_amount),
                    })
                    total_impact_pct += impact_pct

        final_premium = Decimal(str(base_premium)) * (1 + total_impact_pct / 100)

        return {
            "base_premium": base_premium,
            "adjustments": adjustments,
            "total_adjustment_percentage": float(total_impact_pct),
            "total_adjustment_amount": float(Decimal(str(base_premium)) * total_impact_pct / 100),
            "final_premium": float(final_premium),
        }

    def get_categories(self) -> Dict[str, str]:
        """Get all clause categories."""
        return self._categories

    def get_clause_summary(self, clause_id: str) -> Optional[Dict[str, Any]]:
        """Get a simplified summary of a clause."""
        clause = self.get_clause_by_id(clause_id)
        if clause:
            return {
                "id": clause["id"],
                "name": clause["name"],
                "category": clause.get("category"),
                "description": clause.get("description"),
                "is_exclusion": clause.get("is_exclusion", False),
                "mandatory": clause.get("mandatory", False),
                "pricing_impact": clause.get("pricing_impact", 0),
            }
        return None


# Singleton instance
lma_clauses_service = LMAClausesService()
