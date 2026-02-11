"""
AutoGen Tool Functions

Tools for AutoGen agents to access ClaimSense benchmark data
and RapidRate actuarial pricing.
"""
import json
from typing import Optional, Dict, Any, List
import logging

import boto3
from botocore.exceptions import ClientError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.services.claimsense_service import get_claimsense_service
from app.services.bedrock_client import get_bedrock_client
from app.services.unified_rag import unified_rag

logger = logging.getLogger(__name__)


# Tool definitions for AutoGen agent registration
TOOL_DEFINITIONS = [
    {
        "name": "query_historical_claims",
        "description": """Query ClaimSense benchmark database for historical claims data.
Use this tool to get industry benchmark statistics for loss experience comparison.
Returns aggregated statistics including claim frequency, severity, and percentiles.""",
        "parameters": {
            "type": "object",
            "properties": {
                "policy_type": {
                    "type": "string",
                    "description": "Policy type: GL, WC, AL, PR, PL, CY, DO, EPL",
                    "enum": ["GL", "WC", "AL", "PR", "PL", "CY", "DO", "EPL"],
                },
                "state": {
                    "type": "string",
                    "description": "Two-letter state code (optional)",
                },
                "industry": {
                    "type": "string",
                    "description": "Industry name or NAICS code (optional)",
                },
                "assessment_id": {
                    "type": "string",
                    "description": "Assessment ID to compare against benchmarks (optional)",
                },
            },
            "required": ["policy_type"],
        },
    },
    {
        "name": "actuarial_pricing",
        "description": """Get actuarial pricing using Monte Carlo simulation.
Use this tool to calculate expected loss, VaR percentiles, and premium indication.
Can incorporate insured's loss history for experience rating.""",
        "parameters": {
            "type": "object",
            "properties": {
                "policy_type": {
                    "type": "string",
                    "description": "Policy type: GL, WC, AL, PR",
                    "enum": ["GL", "WC", "AL", "PR"],
                },
                "state": {
                    "type": "string",
                    "description": "Two-letter state code",
                },
                "exposure": {
                    "type": "number",
                    "description": "Exposure base (e.g., revenue, payroll)",
                },
                "deductible": {
                    "type": "number",
                    "description": "Per-claim deductible amount",
                },
                "limit": {
                    "type": "number",
                    "description": "Per-claim limit amount",
                },
                "industry_code": {
                    "type": "string",
                    "description": "NAICS industry code",
                },
                "insured_loss_history": {
                    "type": "object",
                    "description": "Insured's historical loss data for experience rating",
                    "properties": {
                        "claim_counts": {"type": "array", "items": {"type": "integer"}},
                        "claim_amounts": {"type": "array", "items": {"type": "number"}},
                        "years": {"type": "array", "items": {"type": "integer"}},
                    },
                },
            },
            "required": ["policy_type", "state", "exposure"],
        },
    },
    {
        "name": "pricing_what_if",
        "description": """Run what-if scenario for pricing.
Use this to test how changing terms affects the premium.
Useful for underwriting negotiations.""",
        "parameters": {
            "type": "object",
            "properties": {
                "base_scenario": {
                    "type": "object",
                    "description": "Base pricing parameters",
                },
                "deductible": {
                    "type": "number",
                    "description": "New deductible to test",
                },
                "limit": {
                    "type": "number",
                    "description": "New limit to test",
                },
                "exposure_change_pct": {
                    "type": "number",
                    "description": "Percentage change in exposure (e.g., -10 for 10% decrease)",
                },
            },
            "required": ["base_scenario"],
        },
    },
    {
        "name": "search_knowledge_base",
        "description": """Search the insurance knowledge base using RAG.
Searches across user uploads, ACORD clauses, CUAD contracts, JETech underwriting blocks,
and global insurance knowledge (112K+ records). Results are prioritized:
user docs first, then ACORD, CUAD, JETech, and global knowledge.""",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query - describe what insurance knowledge you need",
                },
                "category": {
                    "type": "string",
                    "description": "Optional category filter (e.g., 'clause', 'policy', 'regulatory')",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of results to return (default 5)",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "compare_insured_to_benchmark",
        "description": """Compare insured's loss history to industry benchmarks.
Returns detailed comparison metrics and narrative analysis.
Requires assessment_id with uploaded loss runs.""",
        "parameters": {
            "type": "object",
            "properties": {
                "assessment_id": {
                    "type": "string",
                    "description": "Assessment ID with uploaded loss runs",
                },
                "policy_type": {
                    "type": "string",
                    "description": "Policy type for benchmark comparison",
                },
                "state": {
                    "type": "string",
                    "description": "State for benchmark comparison",
                },
            },
            "required": ["assessment_id", "policy_type"],
        },
    },
]


async def query_historical_claims(
    db: AsyncSession,
    policy_type: str,
    state: Optional[str] = None,
    industry: Optional[str] = None,
    assessment_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Query ClaimSense benchmark data.

    Called by RiskAnalyst agent for historical claims analysis.

    Args:
        db: Database session
        policy_type: Policy type code
        state: State code (optional)
        industry: Industry name or code (optional)
        assessment_id: Assessment ID for comparison (optional)

    Returns:
        Dict with benchmark data and optional comparison
    """
    service = get_claimsense_service(db)

    if assessment_id:
        # Get comparison if assessment_id provided
        result = await service.compare(
            assessment_id=assessment_id,
            policy_type=policy_type,
            state=state,
            industry=industry,
        )
        return result.to_dict()
    else:
        # Get benchmark data only
        result = await service.query_benchmark(
            policy_type=policy_type,
            state=state,
            industry=industry,
        )
        return result.to_dict()


async def actuarial_pricing(
    policy_type: str,
    state: str,
    exposure: float,
    deductible: float = 0,
    limit: Optional[float] = None,
    industry_code: Optional[str] = None,
    insured_loss_history: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Get actuarial pricing from RapidRate Lambda.

    Called by Underwriter agent for premium calculation.

    Args:
        policy_type: Policy type code
        state: State code
        exposure: Exposure base amount
        deductible: Per-claim deductible
        limit: Per-claim limit
        industry_code: NAICS code
        insured_loss_history: Historical loss data

    Returns:
        Dict with pricing results
    """
    lambda_client = boto3.client(
        "lambda",
        region_name=settings.RAPIDRATE_LAMBDA_REGION,
    )

    payload = {
        "action": "price",
        "policy_type": policy_type,
        "state": state,
        "exposure": exposure,
        "deductible": deductible,
        "limit": limit,
        "industry_code": industry_code,
        "features": {
            "exposure": exposure,
            "deductible": deductible,
            "limit": limit or 1000000,
            "state_code": state,
        },
    }

    if insured_loss_history:
        payload["insured_loss_history"] = insured_loss_history

    try:
        response = lambda_client.invoke(
            FunctionName=settings.RAPIDRATE_LAMBDA_NAME,
            InvocationType="RequestResponse",
            Payload=json.dumps(payload),
        )

        result = json.loads(response["Payload"].read())

        if response.get("StatusCode") == 200:
            body = json.loads(result.get("body", "{}"))
            if body.get("success"):
                return body["data"]
            else:
                logger.error(f"RapidRate error: {body.get('error')}")
                return {"error": body.get("error", "Unknown error")}
        else:
            logger.error(f"Lambda invocation failed: {response}")
            return {"error": "Lambda invocation failed"}

    except ClientError as e:
        logger.error(f"Lambda client error: {e}")
        return {"error": str(e)}
    except Exception as e:
        logger.error(f"Actuarial pricing error: {e}")
        return {"error": str(e)}


async def pricing_what_if(
    base_scenario: Dict[str, Any],
    deductible: Optional[float] = None,
    limit: Optional[float] = None,
    exposure_change_pct: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Run what-if pricing scenario.

    Called by Underwriter agent for scenario analysis.

    Args:
        base_scenario: Base pricing parameters
        deductible: New deductible to test
        limit: New limit to test
        exposure_change_pct: Percentage change in exposure

    Returns:
        Dict with base and scenario pricing comparison
    """
    # Modify scenario
    scenario = base_scenario.copy()

    if deductible is not None:
        scenario["deductible"] = deductible

    if limit is not None:
        scenario["limit"] = limit

    if exposure_change_pct is not None:
        current_exposure = scenario.get("exposure", 1000000)
        scenario["exposure"] = current_exposure * (1 + exposure_change_pct / 100)

    # Run pricing for scenario
    result = await actuarial_pricing(
        policy_type=scenario.get("policy_type", "GL"),
        state=scenario.get("state", "CA"),
        exposure=scenario.get("exposure", 1000000),
        deductible=scenario.get("deductible", 0),
        limit=scenario.get("limit"),
        industry_code=scenario.get("industry_code"),
        insured_loss_history=scenario.get("insured_loss_history"),
    )

    return {
        "base_scenario": base_scenario,
        "modified_scenario": scenario,
        "pricing_result": result,
        "changes": {
            "deductible_change": deductible if deductible is not None else "unchanged",
            "limit_change": limit if limit is not None else "unchanged",
            "exposure_change_pct": exposure_change_pct if exposure_change_pct is not None else 0,
        },
    }


async def search_knowledge_base(
    query: str,
    user_id: Optional[str] = None,
    category: Optional[str] = None,
    top_k: int = 5,
) -> Dict[str, Any]:
    """
    Search insurance knowledge base with priority chain.

    Called by any agent needing insurance domain knowledge.

    Args:
        query: Search query text
        user_id: User ID for per-user doc search
        category: Optional category filter
        top_k: Number of results

    Returns:
        Dict with search results and source attribution
    """
    try:
        results = await unified_rag.search(
            query=query,
            user_id=user_id,
            category=category,
            top_k=top_k,
        )

        return {
            "results": results,
            "total": len(results),
            "context": unified_rag.format_as_context(results),
        }
    except Exception as e:
        logger.error(f"Knowledge base search error: {e}")
        return {"results": [], "total": 0, "error": str(e)}


async def compare_insured_to_benchmark(
    db: AsyncSession,
    assessment_id: str,
    policy_type: str,
    state: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Compare insured loss history to benchmarks.

    Called by RiskAnalyst agent for detailed comparison.

    Args:
        db: Database session
        assessment_id: Assessment ID
        policy_type: Policy type for benchmarks
        state: State for benchmarks

    Returns:
        Dict with comparison results and narrative
    """
    service = get_claimsense_service(db)
    result = await service.compare(
        assessment_id=assessment_id,
        policy_type=policy_type,
        state=state,
    )
    return result.to_dict()


# Tool executor for AutoGen integration
class AutoGenToolExecutor:
    """Executor for AutoGen tool calls."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def execute(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Execute a tool call and return result as string.

        Args:
            tool_name: Name of the tool to execute
            arguments: Tool arguments

        Returns:
            JSON string with result
        """
        try:
            if tool_name == "query_historical_claims":
                result = await query_historical_claims(
                    db=self.db,
                    policy_type=arguments.get("policy_type"),
                    state=arguments.get("state"),
                    industry=arguments.get("industry"),
                    assessment_id=arguments.get("assessment_id"),
                )
            elif tool_name == "actuarial_pricing":
                result = await actuarial_pricing(
                    policy_type=arguments.get("policy_type"),
                    state=arguments.get("state"),
                    exposure=arguments.get("exposure"),
                    deductible=arguments.get("deductible", 0),
                    limit=arguments.get("limit"),
                    industry_code=arguments.get("industry_code"),
                    insured_loss_history=arguments.get("insured_loss_history"),
                )
            elif tool_name == "pricing_what_if":
                result = await pricing_what_if(
                    base_scenario=arguments.get("base_scenario", {}),
                    deductible=arguments.get("deductible"),
                    limit=arguments.get("limit"),
                    exposure_change_pct=arguments.get("exposure_change_pct"),
                )
            elif tool_name == "search_knowledge_base":
                result = await search_knowledge_base(
                    query=arguments.get("query", ""),
                    user_id=arguments.get("user_id"),
                    category=arguments.get("category"),
                    top_k=arguments.get("top_k", 5),
                )
            elif tool_name == "compare_insured_to_benchmark":
                result = await compare_insured_to_benchmark(
                    db=self.db,
                    assessment_id=arguments.get("assessment_id"),
                    policy_type=arguments.get("policy_type"),
                    state=arguments.get("state"),
                )
            else:
                result = {"error": f"Unknown tool: {tool_name}"}

            return json.dumps(result, default=str)

        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            return json.dumps({"error": str(e)})


def get_tool_definitions() -> List[Dict[str, Any]]:
    """Get tool definitions for Bedrock tool use."""
    return TOOL_DEFINITIONS


def format_tools_for_bedrock() -> List[Dict[str, Any]]:
    """Format tools for Bedrock Messages API tool_use format."""
    return [
        {
            "name": tool["name"],
            "description": tool["description"],
            "input_schema": tool["parameters"],
        }
        for tool in TOOL_DEFINITIONS
    ]
