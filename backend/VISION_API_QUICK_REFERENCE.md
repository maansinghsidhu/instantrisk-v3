# Vision API Quick Reference

## Endpoints

### 1. Analyze Property Image

**POST** `/api/v1/vision/analyze-property`

Upload a property photo and receive AI-powered risk analysis.

**Request:**
```bash
curl -X POST "https://api.instantrisk.com/api/v1/vision/analyze-property" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@property.jpg" \
  -F "assessment_id=123e4567-e89b-12d3-a456-426614174000" \
  -F "additional_context=Commercial property, London"
```

**Parameters:**
- `file` (required): Image file (.jpg, .jpeg, .png, .gif, .webp, max 10MB)
- `assessment_id` (required): UUID of the assessment
- `additional_context` (optional): Additional property details

**Response (200 OK):**
```json
{
  "risk_score": 42,
  "risk_factors": [
    {
      "category": "roof",
      "severity": "medium",
      "description": "Aging shingles visible",
      "recommendation": "Schedule roof inspection"
    }
  ],
  "overall_assessment": "Property in acceptable condition",
  "insurability": "acceptable",
  "key_concerns": ["Roof age", "Fire hazard proximity"]
}
```

**Error Responses:**
- `400` - Invalid file type or size
- `403` - Access denied to assessment
- `404` - Assessment not found
- `500` - Analysis failed

---

### 2. Get Property Report

**GET** `/api/v1/vision/property-report/{assessment_id}`

Retrieve stored vision analysis for an assessment.

**Request:**
```bash
curl -X GET "https://api.instantrisk.com/api/v1/vision/property-report/123e4567-e89b-12d3-a456-426614174000" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Response (200 OK):**
```json
{
  "assessment_id": "123e4567-e89b-12d3-a456-426614174000",
  "property_analysis": {
    "risk_score": 42,
    "risk_factors": [...],
    "overall_assessment": "...",
    "insurability": "acceptable"
  },
  "created_at": "2026-02-18T12:00:00Z",
  "updated_at": "2026-02-18T12:00:00Z"
}
```

**Error Responses:**
- `403` - Access denied to assessment
- `404` - Assessment not found

---

## Risk Categories

| Category | Description |
|----------|-------------|
| `roof` | Roof condition, age, damage, water intrusion risk |
| `fire` | Fire hazards, vegetation, electrical, combustibles |
| `structural` | Foundation, walls, windows, building integrity |
| `security` | Fencing, lighting, alarms, access control |
| `environmental` | Flood risk, wind exposure, nearby hazards |

## Severity Levels

| Level | Description | Typical Action |
|-------|-------------|----------------|
| `low` | Minor concern | Monitor, routine maintenance |
| `medium` | Moderate risk | Schedule inspection, address within 6 months |
| `high` | Significant risk | Immediate attention, address within 3 months |
| `critical` | Severe risk | May affect insurability, urgent action required |

## Insurability Ratings

| Rating | Risk Score Range | Description |
|--------|------------------|-------------|
| `excellent` | 0-20 | Well-maintained, minimal risks |
| `good` | 21-40 | Standard condition, minor issues |
| `acceptable` | 41-60 | Moderate risks, manageable with mitigation |
| `marginal` | 61-80 | Significant concerns, may require conditions |
| `uninsurable` | 81-100 | Severe risks, likely declined |

## Python Example

```python
import requests

# Analyze property
with open('property.jpg', 'rb') as f:
    response = requests.post(
        'https://api.instantrisk.com/api/v1/vision/analyze-property',
        headers={'Authorization': f'Bearer {token}'},
        files={'file': f},
        data={
            'assessment_id': assessment_id,
            'additional_context': 'Commercial warehouse'
        }
    )

result = response.json()
print(f"Risk Score: {result['risk_score']}")
print(f"Insurability: {result['insurability']}")

for factor in result['risk_factors']:
    print(f"\n{factor['category'].upper()} - {factor['severity']}")
    print(f"  {factor['description']}")
    print(f"  Recommendation: {factor['recommendation']}")
```

## JavaScript/TypeScript Example

```typescript
// Analyze property
const formData = new FormData();
formData.append('file', fileInput.files[0]);
formData.append('assessment_id', assessmentId);
formData.append('additional_context', 'Residential property');

const response = await fetch(
  'https://api.instantrisk.com/api/v1/vision/analyze-property',
  {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`
    },
    body: formData
  }
);

const result = await response.json();

// Display results
console.log(`Risk Score: ${result.risk_score}/100`);
console.log(`Insurability: ${result.insurability}`);

result.risk_factors.forEach(factor => {
  console.log(`\n${factor.category}: ${factor.severity}`);
  console.log(`  ${factor.description}`);
});
```

## Database Storage

Results are automatically stored in the `assessments` table:

```sql
SELECT
  id,
  property_analysis->>'risk_score' as risk_score,
  property_analysis->>'insurability' as insurability,
  property_analysis->'risk_factors' as risk_factors
FROM assessments
WHERE id = '123e4567-e89b-12d3-a456-426614174000';
```

## Testing

```bash
# Run integration tests
cd backend
python test_vision_integration.py

# Test endpoint with curl
curl -X POST "http://localhost:8000/api/v1/vision/analyze-property" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@test_image.jpg" \
  -F "assessment_id=YOUR_ASSESSMENT_ID"
```

## Common Issues

### Issue: "File type not supported"
**Solution:** Ensure image is .jpg, .jpeg, .png, .gif, or .webp

### Issue: "Access denied"
**Solution:** Verify you own the assessment or have admin role

### Issue: "Analysis failed"
**Solution:** Check AWS Bedrock credentials and model access

### Issue: "File too large"
**Solution:** Reduce image size to under 10MB

## Performance

- **Average response time:** 5-10 seconds
- **Rate limit:** Standard API limits apply
- **Concurrent requests:** Supported
- **Cost per analysis:** ~$0.015 (Bedrock API charges)

## Support

- Documentation: `/backend/VISION_FEATURE.md`
- Implementation details: `/backend/VISION_IMPLEMENTATION_SUMMARY.txt`
- Integration tests: `/backend/test_vision_integration.py`
