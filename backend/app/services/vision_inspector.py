"""
Computer Vision Property Inspection Service for InstantRisk.

Uses AWS Bedrock Claude 4 Sonnet with vision capability to analyze property
photos and identify risk factors for insurance underwriting.
"""

import json
import logging
import base64
from typing import Dict, List, Any, Optional
from pathlib import Path

from app.services.bedrock_client import get_bedrock_client

logger = logging.getLogger(__name__)


class VisionInspector:
    """
    Property inspection service using AWS Bedrock vision models.

    Analyzes property photos to detect:
    - Roof condition and potential damage
    - Fire hazards
    - Structural issues
    - Security features
    - Environmental risks
    """

    def __init__(self):
        self.bedrock_client = get_bedrock_client()
        # Claude 4 Sonnet supports vision
        self.vision_model = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"

    def _encode_image(self, image_path: str) -> tuple[str, str]:
        """
        Encode image file to base64 for Bedrock API.

        Args:
            image_path: Path to the image file

        Returns:
            Tuple of (base64_data, media_type)
        """
        path = Path(image_path)

        # Determine media type from extension
        ext = path.suffix.lower()
        media_type_map = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.webp': 'image/webp'
        }
        media_type = media_type_map.get(ext, 'image/jpeg')

        # Read and encode image
        with open(image_path, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')

        return image_data, media_type

    def _build_vision_prompt(self) -> str:
        """
        Build the analysis prompt for property inspection.

        Returns:
            System prompt for vision analysis
        """
        return """You are an expert property risk inspector for insurance underwriting.

Analyze the provided property photo and identify ALL relevant risk factors.

Focus on these key areas:

1. **Roof Condition**
   - Age and material type
   - Visible damage, missing shingles, or wear
   - Potential for water intrusion
   - Structural integrity

2. **Fire Hazards**
   - Proximity to vegetation/wildfire fuel
   - Electrical hazards
   - Combustible materials
   - Fire suppression equipment visible

3. **Structural Issues**
   - Foundation condition
   - Wall integrity, cracks, or settling
   - Window/door security
   - Overall building condition

4. **Security Features**
   - Fencing and access control
   - Lighting
   - Security cameras or alarm systems
   - Entry point protection

5. **Environmental Risks**
   - Flood risk indicators (elevation, drainage)
   - Wind exposure
   - Nearby hazards (trees, power lines)
   - Landscape maintenance

Return your analysis in this JSON format:
{
  "risk_score": <0-100, where 100 is highest risk>,
  "risk_factors": [
    {
      "category": "<roof|fire|structural|security|environmental>",
      "severity": "<low|medium|high|critical>",
      "description": "<detailed observation>",
      "recommendation": "<mitigation advice>"
    }
  ],
  "overall_assessment": "<brief summary>",
  "insurability": "<excellent|good|acceptable|marginal|uninsurable>",
  "key_concerns": ["<list of top 3-5 concerns>"]
}

Be thorough but concise. Only include risk factors you can actually observe in the image."""

    async def analyze_property_image(
        self,
        image_path: str,
        additional_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze a property image for risk factors.

        Args:
            image_path: Path to the property image file
            additional_context: Optional context (address, property type, etc.)

        Returns:
            Analysis results with risk score and detailed findings
        """
        try:
            # Encode the image
            image_data, media_type = self._encode_image(image_path)

            # Build the prompt
            system_prompt = self._build_vision_prompt()

            # Build user message with context
            user_content = "Analyze this property image for insurance risk assessment."
            if additional_context:
                user_content += f"\n\nAdditional context: {additional_context}"

            # Create messages with image content
            # Bedrock expects content as a list with text and image blocks
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": user_content
                        },
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_data
                            }
                        }
                    ]
                }
            ]

            # Call Bedrock with vision model
            # We need to use the low-level client for vision
            response = await self._invoke_vision_model(
                messages=messages,
                system_prompt=system_prompt
            )

            # Parse the JSON response
            result = self._parse_vision_response(response)

            logger.info(f"Vision analysis completed: risk_score={result.get('risk_score', 'N/A')}")

            return result

        except Exception as e:
            logger.error(f"Vision analysis failed: {e}", exc_info=True)
            return {
                "error": str(e),
                "risk_score": 50,  # Default moderate risk on error
                "risk_factors": [],
                "overall_assessment": f"Analysis failed: {str(e)}",
                "insurability": "unknown"
            }

    async def _invoke_vision_model(
        self,
        messages: List[Dict],
        system_prompt: str
    ) -> str:
        """
        Invoke Bedrock vision model with image content.

        Args:
            messages: Messages with image content
            system_prompt: System prompt for analysis

        Returns:
            Model response text
        """
        import boto3
        import os
        import asyncio

        # Get boto3 client
        profile = os.getenv("AWS_PROFILE", "")
        region = os.getenv("AWS_BEDROCK_REGION", "us-east-1")

        try:
            if profile:
                session = boto3.Session(profile_name=profile, region_name=region)
            else:
                session = boto3.Session(region_name=region)
        except Exception:
            session = boto3.Session(region_name=region)

        client = session.client("bedrock-runtime")

        # Build request body
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4096,
            "temperature": 0.1,  # Low temperature for consistent analysis
            "system": system_prompt,
            "messages": messages
        }

        # Invoke model (run in executor to avoid blocking)
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.invoke_model(
                modelId=self.vision_model,
                body=json.dumps(body),
                contentType="application/json",
                accept="application/json"
            )
        )

        # Parse response
        response_body = json.loads(response["body"].read())
        content = ""
        for block in response_body.get("content", []):
            if block.get("type") == "text":
                content += block.get("text", "")

        return content

    def _parse_vision_response(self, response: str) -> Dict[str, Any]:
        """
        Parse the vision model response into structured data.

        Args:
            response: Raw response from vision model

        Returns:
            Parsed analysis results
        """
        try:
            # Extract JSON from response (may be wrapped in markdown)
            if "```json" in response:
                json_start = response.find("```json") + 7
                json_end = response.find("```", json_start)
                json_str = response[json_start:json_end].strip()
            elif "```" in response:
                json_start = response.find("```") + 3
                json_end = response.find("```", json_start)
                json_str = response[json_start:json_end].strip()
            else:
                # Try to find JSON object directly
                json_start = response.find("{")
                json_end = response.rfind("}") + 1
                if json_start >= 0 and json_end > json_start:
                    json_str = response[json_start:json_end]
                else:
                    json_str = response

            result = json.loads(json_str)

            # Validate required fields
            if "risk_score" not in result:
                result["risk_score"] = 50
            if "risk_factors" not in result:
                result["risk_factors"] = []

            # Ensure risk_score is in valid range
            result["risk_score"] = max(0, min(100, int(result["risk_score"])))

            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse vision response as JSON: {e}")
            logger.debug(f"Raw response: {response}")

            # Return fallback structure
            return {
                "risk_score": 50,
                "risk_factors": [],
                "overall_assessment": response[:500],  # Use first 500 chars
                "insurability": "unknown",
                "raw_response": response
            }

    async def analyze_multiple_images(
        self,
        image_paths: List[str],
        additional_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze multiple property images and aggregate results.

        Args:
            image_paths: List of image file paths
            additional_context: Optional context for all images

        Returns:
            Aggregated analysis results
        """
        all_results = []
        all_risk_factors = []

        for image_path in image_paths:
            result = await self.analyze_property_image(image_path, additional_context)
            all_results.append(result)
            all_risk_factors.extend(result.get("risk_factors", []))

        # Aggregate risk scores (use maximum)
        max_risk_score = max(
            (r.get("risk_score", 0) for r in all_results),
            default=0
        )

        # Combine assessments
        assessments = [r.get("overall_assessment", "") for r in all_results if r.get("overall_assessment")]

        return {
            "risk_score": max_risk_score,
            "risk_factors": all_risk_factors,
            "overall_assessment": " ".join(assessments),
            "image_count": len(image_paths),
            "individual_results": all_results
        }


# Singleton instance
_vision_inspector = None


def get_vision_inspector() -> VisionInspector:
    """Get the singleton VisionInspector instance."""
    global _vision_inspector
    if _vision_inspector is None:
        _vision_inspector = VisionInspector()
    return _vision_inspector
