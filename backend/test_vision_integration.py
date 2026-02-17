"""
Simple test for Computer Vision Property Inspection feature.

This test verifies the basic structure and integration of the vision analysis system.
Run this after deploying to verify the feature works end-to-end.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.vision_inspector import get_vision_inspector


async def test_vision_service():
    """Test the vision inspector service with mock data."""
    print("=" * 80)
    print("Computer Vision Property Inspection - Integration Test")
    print("=" * 80)

    # Test 1: Service initialization
    print("\n[TEST 1] Initializing VisionInspector service...")
    try:
        inspector = get_vision_inspector()
        print("[PASS] VisionInspector initialized successfully")
        print(f"  - Model: {inspector.vision_model}")
    except Exception as e:
        print(f"[FAIL] Failed to initialize: {e}")
        return False

    # Test 2: Response parsing
    print("\n[TEST 2] Testing response parser...")
    mock_response = """
    ```json
    {
      "risk_score": 35,
      "risk_factors": [
        {
          "category": "roof",
          "severity": "medium",
          "description": "Aging shingles visible with minor wear",
          "recommendation": "Schedule roof inspection within 6 months"
        },
        {
          "category": "security",
          "severity": "low",
          "description": "Basic fencing present, no visible security cameras",
          "recommendation": "Consider adding motion-activated lighting"
        }
      ],
      "overall_assessment": "Property is in acceptable condition with moderate risk factors",
      "insurability": "acceptable",
      "key_concerns": ["Roof age", "Limited security features"]
    }
    ```
    """

    try:
        result = inspector._parse_vision_response(mock_response)
        print("[PASS] Response parsed successfully")
        print(f"  - Risk score: {result.get('risk_score')}")
        print(f"  - Risk factors: {len(result.get('risk_factors', []))}")
        print(f"  - Insurability: {result.get('insurability')}")

        # Validate structure
        assert result.get('risk_score') == 35, "Risk score mismatch"
        assert len(result.get('risk_factors', [])) == 2, "Risk factors count mismatch"
        assert result.get('insurability') == 'acceptable', "Insurability mismatch"
        print("[PASS] All validations passed")

    except Exception as e:
        print(f"[FAIL] Parser test failed: {e}")
        return False

    # Test 3: Verify API endpoints structure
    print("\n[TEST 3] Checking router endpoints...")
    try:
        from app.routers import vision

        # Check router exists
        assert hasattr(vision, 'router'), "Router not defined"
        print("[PASS] Vision router module loaded")

        # Count routes
        route_count = len(vision.router.routes)
        print(f"[PASS] Router has {route_count} endpoints")

        # List endpoints
        for route in vision.router.routes:
            if hasattr(route, 'path') and hasattr(route, 'methods'):
                methods = ', '.join(route.methods)
                print(f"  - {methods} {route.path}")

    except Exception as e:
        print(f"[FAIL] Router check failed: {e}")
        return False

    # Test 4: Verify schema structure
    print("\n[TEST 4] Checking Pydantic schemas...")
    try:
        from app.schemas.vision import (
            VisionAnalysisResult,
            VisionAnalysisRequest,
            PropertyReportResponse,
            RiskFactor
        )

        # Test RiskFactor schema
        risk_factor = RiskFactor(
            category="roof",
            severity="high",
            description="Test description",
            recommendation="Test recommendation"
        )
        print("[PASS] RiskFactor schema validated")

        # Test VisionAnalysisResult schema
        analysis_result = VisionAnalysisResult(
            risk_score=50,
            risk_factors=[risk_factor],
            overall_assessment="Test assessment",
            insurability="good"
        )
        print("[PASS] VisionAnalysisResult schema validated")
        print(f"  - Risk score: {analysis_result.risk_score}")
        print(f"  - Risk factors: {len(analysis_result.risk_factors)}")

    except Exception as e:
        print(f"[FAIL] Schema validation failed: {e}")
        return False

    # Test 5: Verify database model update
    print("\n[TEST 5] Checking Assessment model...")
    try:
        from app.models.assessment import Assessment
        from sqlalchemy.inspection import inspect

        # Get all columns
        mapper = inspect(Assessment)
        columns = [col.key for col in mapper.columns]

        # Check property_analysis column exists
        assert 'property_analysis' in columns, "property_analysis column not found"
        print("[PASS] Assessment model has property_analysis column")

        # Check column type
        prop_col = mapper.columns['property_analysis']
        print(f"  - Column type: {prop_col.type}")

    except Exception as e:
        print(f"[FAIL] Model check failed: {e}")
        return False

    print("\n" + "=" * 80)
    print("All tests passed!")
    print("=" * 80)
    print("\nNext steps:")
    print("1. Deploy the updated code to ECS")
    print("2. Test the API endpoint: POST /api/v1/vision/analyze-property")
    print("3. Verify results are stored in assessment.property_analysis")

    return True


if __name__ == "__main__":
    success = asyncio.run(test_vision_service())
    sys.exit(0 if success else 1)
