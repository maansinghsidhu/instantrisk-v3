# Computer Vision Property Inspection Feature

## Overview

The Computer Vision Property Inspection feature uses AWS Bedrock Claude 4 Sonnet with vision capability to analyze property photos and identify risk factors for insurance underwriting.

## Features

- **Automated Risk Detection**: Analyzes property images for roof condition, fire hazards, structural issues, security features, and environmental risks
- **Risk Scoring**: Provides a 0-100 risk score with detailed breakdown by category
- **Insurability Assessment**: Rates properties as excellent, good, acceptable, marginal, or uninsurable
- **Actionable Recommendations**: Provides specific mitigation advice for each identified risk
- **Assessment Integration**: Automatically stores results in the assessment's `property_analysis` field

## Architecture

### 1. Service Layer (`app/services/vision_inspector.py`)

**VisionInspector Class**:
- Uses AWS Bedrock Claude 4 Sonnet vision model (`us.anthropic.claude-sonnet-4-5-20250929-v1:0`)
- Encodes images to base64 for API transmission
- Constructs specialized prompts for property risk assessment
- Parses structured JSON responses from the vision model
- Supports both single and multiple image analysis

**Key Methods**:
- `analyze_property_image(image_path, additional_context)`: Analyze a single property image
- `analyze_multiple_images(image_paths, additional_context)`: Analyze and aggregate multiple images
- `_parse_vision_response(response)`: Parse JSON from model response (handles markdown wrapping)

### 2. API Router (`app/routers/vision.py`)

**Endpoints**:

1. **POST /api/v1/vision/analyze-property**
   - Upload property image for analysis
   - Validates user access to assessment
   - Performs security validation on uploaded file
   - Returns structured risk analysis
   - Stores results in assessment.property_analysis

2. **GET /api/v1/vision/property-report/{assessment_id}**
   - Retrieve stored property analysis for an assessment
   - Returns complete vision analysis results

### 3. Data Schemas (`app/schemas/vision.py`)

**RiskFactor**:
- category: roof, fire, structural, security, environmental
- severity: low, medium, high, critical
- description: Detailed observation
- recommendation: Mitigation advice

**VisionAnalysisResult**:
- risk_score: 0-100 (higher = riskier)
- risk_factors: List of RiskFactor objects
- overall_assessment: Summary text
- insurability: Rating (excellent → uninsurable)
- key_concerns: Top 3-5 issues

### 4. Database Model

**Assessment Model Update**:
- Added `property_analysis` JSON column
- Stores complete vision analysis results
- Migration: v102 (runs automatically on startup)

## API Usage

### Analyze Property Image

```bash
curl -X POST "https://your-api.com/api/v1/vision/analyze-property" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@property_photo.jpg" \
  -F "assessment_id=YOUR_ASSESSMENT_UUID" \
  -F "additional_context=Commercial property in London"
```

**Response**:
```json
{
  "risk_score": 42,
  "risk_factors": [
    {
      "category": "roof",
      "severity": "medium",
      "description": "Aging asphalt shingles with visible wear patterns",
      "recommendation": "Schedule professional roof inspection within 3 months"
    },
    {
      "category": "fire",
      "severity": "high",
      "description": "Dense vegetation within 2 meters of building perimeter",
      "recommendation": "Implement 5-meter defensible space with vegetation removal"
    }
  ],
  "overall_assessment": "Property shows moderate risk factors primarily related to roof age and fire hazard proximity. Structural elements appear sound.",
  "insurability": "acceptable",
  "key_concerns": [
    "Roof replacement needed within 5 years",
    "Fire hazard from vegetation proximity",
    "Limited visible security features"
  ]
}
```

### Get Property Report

```bash
curl -X GET "https://your-api.com/api/v1/vision/property-report/{assessment_id}" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Security Features

1. **File Validation**:
   - Only accepts image formats: .jpg, .jpeg, .png, .gif, .webp
   - Maximum file size: 10MB
   - MIME type validation
   - Malware scanning via existing security utilities

2. **Access Control**:
   - Users can only analyze properties for their own assessments
   - Admins have full access
   - Assessment ownership verification

3. **Temporary File Handling**:
   - Images saved to secure temp files during processing
   - Automatic cleanup after analysis

## Analysis Categories

### 1. Roof Condition
- Age and material type
- Visible damage or wear
- Water intrusion risk
- Structural integrity

### 2. Fire Hazards
- Vegetation proximity
- Electrical hazards
- Combustible materials
- Fire suppression equipment

### 3. Structural Issues
- Foundation condition
- Wall integrity
- Window/door security
- Overall building condition

### 4. Security Features
- Fencing and access control
- Lighting systems
- Security cameras/alarms
- Entry point protection

### 5. Environmental Risks
- Flood risk indicators
- Wind exposure
- Nearby hazards
- Landscape maintenance

## Testing

Run the integration test:

```bash
cd backend
python test_vision_integration.py
```

**Test Coverage**:
- Service initialization
- JSON response parsing
- API endpoint registration
- Pydantic schema validation
- Database model updates

## Deployment

The feature is automatically deployed when you deploy the backend:

1. **Migration**: The `property_analysis` column is added automatically on startup
2. **Router**: Vision endpoints are registered in main.py
3. **Dependencies**: Uses existing AWS Bedrock integration (boto3, bedrock-runtime)

## AWS Bedrock Requirements

- **Model Access**: Requires access to Claude 4 Sonnet vision model in AWS account
- **Credentials**: Uses existing AWS credential chain (environment variables, IAM role, SSO)
- **Region**: Defaults to us-east-1 (configurable via AWS_BEDROCK_REGION)

## Future Enhancements

1. **Google Maps Integration** (Optional):
   - Satellite view analysis
   - Street view analysis
   - Location-based risk factors

2. **Multi-Image Analysis**:
   - Compare multiple angles
   - Track changes over time
   - Before/after comparisons

3. **Risk Trend Analysis**:
   - Historical risk scoring
   - Seasonal variations
   - Predictive maintenance

4. **Enhanced Reporting**:
   - PDF report generation
   - Visual annotations on images
   - Side-by-side comparisons

## Error Handling

The service implements robust error handling:

- **Invalid Images**: Returns 400 with validation error
- **AWS API Errors**: Returns 500 with generic error message (logs details)
- **Parse Failures**: Returns fallback structure with raw response
- **Missing Assessment**: Returns 404
- **Access Denied**: Returns 403

## Logging

All vision analysis events are logged:

```python
logger.info(f"Vision analysis completed for assessment {assessment_id}: risk_score={score}")
logger.error(f"Vision analysis failed: {error}")
```

## Performance

- **Average Analysis Time**: 5-10 seconds per image (depends on Bedrock API latency)
- **File Processing**: Minimal overhead (base64 encoding)
- **Database Storage**: JSON field (efficient indexing available if needed)

## Cost Considerations

- **Bedrock Vision API**: ~$0.015 per image (Claude 4 Sonnet pricing)
- **Storage**: Minimal (JSON results typically < 5KB)
- **Bandwidth**: ~1-10MB per image upload

## Related Features

- Document OCR (`documents.py`) - Text extraction from uploaded documents
- AI Analysis (`analysis.py`) - Text-based risk assessment
- Assessment Management (`assessments.py`) - Core assessment workflow

## Support

For issues or questions:
1. Check logs in CloudWatch (search for "Vision analysis")
2. Verify AWS Bedrock model access in your account
3. Ensure assessment exists and user has access
4. Run integration test to verify setup
