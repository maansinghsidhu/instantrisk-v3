# Autonomous Investigation Agent - Implementation Guide

## Overview

The Autonomous Investigation Agent is a multi-agent AI system that autonomously investigates companies in approximately 3 minutes. It uses LangGraph for orchestration and integrates with free public data sources to generate comprehensive 20-page risk investigation reports.

## Architecture

### Technology Stack

- **LangGraph**: Multi-agent workflow orchestration
- **Claude via AWS Bedrock**: Final report synthesis and analysis
- **Free Data Sources**:
  - SEC EDGAR (10-K filings, financial data)
  - OSHA (workplace safety violations)
  - EPA ECHO (environmental compliance)
  - Google News RSS (reputation/news analysis)
  - Have I Been Pwned (data breach history)
  - NIST NVD (CVE vulnerability database)

### Agent Workflow

```
Initial State
    ↓
Financial Agent (SEC EDGAR)
    ↓
Regulatory Agent (OSHA + EPA)
    ↓
Reputation Agent (Google News)
    ↓
Cyber Agent (HIBP + CVE)
    ↓
Synthesis Agent (Claude)
    ↓
Final Report
```

## Installation

### 1. Install Dependencies

```bash
pip install langgraph langchain-anthropic beautifulsoup4 playwright
```

Or add to `requirements.txt`:
```
langgraph==0.2.60
langchain-anthropic==0.3.14
beautifulsoup4==4.12.3
playwright==1.50.0
```

### 2. Run Database Migration

The migration `103_add_autonomous_investigation.py` adds:
- `investigation_report` (JSONB column)
- `investigation_status` (VARCHAR(20) column)

Run migration:
```bash
cd backend
alembic upgrade head
```

Or, the migration auto-runs on app startup via `main.py`.

## API Endpoints

### 1. Trigger Investigation

**Endpoint**: `POST /api/v1/investigation/run/{assessment_id}`

**Description**: Start autonomous investigation for a company (runs in background, ~3 minutes)

**Request**:
```bash
curl -X POST https://your-api.com/api/v1/investigation/run/{assessment_id} \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Response**:
```json
{
  "job_id": "inv-a1b2c3d4e5f6",
  "assessment_id": "uuid-here",
  "company_name": "Acme Corporation",
  "status": "started",
  "message": "Investigation started. This will take approximately 3 minutes."
}
```

### 2. Check Investigation Status

**Endpoint**: `GET /api/v1/investigation/status/{assessment_id}`

**Description**: Check current status of an investigation

**Request**:
```bash
curl -X GET https://your-api.com/api/v1/investigation/status/{assessment_id} \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Response**:
```json
{
  "job_id": "inv-a1b2c3d4e5f6",
  "assessment_id": "uuid-here",
  "status": "completed",
  "started_at": "2026-02-18T12:00:00Z",
  "completed_at": "2026-02-18T12:03:15Z",
  "errors": []
}
```

**Status Values**:
- `not_started`: Investigation not yet triggered
- `in_progress`: Investigation running
- `completed`: Investigation finished successfully
- `failed`: Investigation encountered errors

### 3. Get Investigation Report

**Endpoint**: `GET /api/v1/investigation/report/{assessment_id}`

**Description**: Retrieve full investigation report

**Request**:
```bash
curl -X GET https://your-api.com/api/v1/investigation/report/{assessment_id} \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Response**:
```json
{
  "assessment_id": "uuid-here",
  "company_name": "Acme Corporation",
  "overall_risk_score": 45,
  "recommendation": "GO",
  "generated_at": "2026-02-18T12:03:15Z",
  "report": {
    "report_text": "# EXECUTIVE SUMMARY\n...",
    "overall_risk_score": 45,
    "recommendation": "GO",
    "executive_summary": "Overall risk rating: Medium...",
    "investigation_summary": {
      "financial_findings": {...},
      "regulatory_findings": {...},
      "reputation_findings": {...},
      "cyber_findings": {...}
    }
  }
}
```

## Report Structure

The generated report includes:

### 1. Executive Summary
- Overall risk rating (Low/Medium/High/Critical)
- Key findings (3-5 bullet points)
- Underwriting recommendation (GO/NO-GO/REFER)

### 2. Financial Analysis
- SEC filing history and compliance
- Industry classification (SIC code)
- Financial health indicators
- Red flags or concerns

### 3. Regulatory Compliance
- OSHA violation history
- EPA environmental compliance
- Regulatory risk assessment

### 4. Reputation & News Analysis
- Recent news sentiment (0-100 scale)
- Public perception analysis
- Crisis indicators
- Brand risk assessment

### 5. Cyber Security Posture
- Data breach history (HIBP)
- Known vulnerabilities (CVEs)
- Cyber risk exposure

### 6. Risk Scoring Matrix
Scores (0-100) for:
- Financial Risk
- Regulatory Risk
- Reputation Risk
- Cyber Risk
- Overall Composite Risk

### 7. Underwriting Recommendations
- Coverage considerations
- Premium loading factors
- Policy exclusions
- Required due diligence

## Usage Example

### Python Client Example

```python
import requests
import time

API_BASE = "https://your-api.com/api/v1"
TOKEN = "your_jwt_token"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

# 1. Trigger investigation
assessment_id = "your-assessment-uuid"
response = requests.post(
    f"{API_BASE}/investigation/run/{assessment_id}",
    headers=headers
)

result = response.json()
print(f"Investigation started: {result['job_id']}")

# 2. Poll for completion (every 30 seconds)
while True:
    status_resp = requests.get(
        f"{API_BASE}/investigation/status/{assessment_id}",
        headers=headers
    )
    status = status_resp.json()

    if status['status'] == 'completed':
        print("Investigation completed!")
        break
    elif status['status'] == 'failed':
        print(f"Investigation failed: {status['errors']}")
        break

    print(f"Status: {status['status']}, waiting...")
    time.sleep(30)

# 3. Get full report
report_resp = requests.get(
    f"{API_BASE}/investigation/report/{assessment_id}",
    headers=headers
)

report = report_resp.json()
print(f"Risk Score: {report['overall_risk_score']}")
print(f"Recommendation: {report['recommendation']}")
print(f"\nReport:\n{report['report']['report_text']}")
```

## Data Sources

### 1. SEC EDGAR (Financial Data)

**API**: `https://data.sec.gov/submissions/CIK{number}.json`

**Data Retrieved**:
- Recent 10-K and 10-Q filings
- Company SIC code and industry
- Business address
- Fiscal year end

**Rate Limits**: Fair access policy (identify with User-Agent)

### 2. OSHA (Workplace Safety)

**API**: `https://data.dol.gov/get/inspection_detail/{company}`

**Data Retrieved**:
- Inspection dates
- Violation types
- Penalties assessed

### 3. EPA ECHO (Environmental Compliance)

**API**: `https://echodata.epa.gov/echo/facility_search.get_facility_info`

**Data Retrieved**:
- Facility violations (3-year history)
- Compliance status
- Facility locations

### 4. Google News (Reputation)

**Source**: Google News RSS feeds

**Data Retrieved**:
- Recent news articles (last 10)
- Publication dates
- News sources
- Sentiment indicators (negative keyword count)

### 5. Have I Been Pwned (Data Breaches)

**API**: `https://haveibeenpwned.com/api/v3/breaches`

**Data Retrieved**:
- Known data breaches
- Breach dates
- Number of accounts compromised
- Data classes exposed

### 6. NIST NVD (Vulnerabilities)

**API**: `https://services.nvd.nist.gov/rest/json/cves/2.0`

**Data Retrieved**:
- CVE IDs
- Severity ratings
- Vulnerability descriptions

## Configuration

### Environment Variables

No additional environment variables required beyond existing Bedrock configuration:

- `AWS_BEDROCK_REGION` (default: us-east-1)
- `BEDROCK_MODEL_ID` (default: us.anthropic.claude-sonnet-4-5-20250929-v1:0)
- `BEDROCK_ENABLED` (default: true)

### Timeouts

Default timeouts for data source requests:
- SEC EDGAR: 30 seconds
- OSHA: 20 seconds
- EPA: 20 seconds
- Google News: 20 seconds
- HIBP: 20 seconds
- CVE: 20 seconds

## Error Handling

### Agent-Level Errors

If an individual agent fails:
- Error logged to `state['errors']`
- Agent returns partial data with `{"error": "..."}` field
- Workflow continues to next agent
- Final report notes missing data

### Complete Failure

If synthesis agent fails:
- `investigation_status` set to `"failed"`
- `investigation_report` contains `{"error": "..."}`
- Assessment risk_score unchanged

### Network Timeouts

All HTTP requests have timeouts. On timeout:
- Agent returns `{"error": "Request timeout"}`
- Investigation continues with available data

## Permissions

### Required User Permissions

Users can trigger investigations for:
- Assessments they created (`created_by == current_user.id`)
- Any assessment (if user role is `admin`)

### Prerequisites

Assessment must have:
- `insured_entity_name` OR `insured_name` set
- Valid UUID

## Database Schema

### Assessment Model Changes

**New Columns**:

```python
investigation_report = Column(JSON, nullable=True, default=dict)
investigation_status = Column(String(20), nullable=True, default="not_started")
```

**Indexes**:

```sql
CREATE INDEX idx_assessments_investigation_status ON assessments(investigation_status);
CREATE INDEX idx_assessments_investigation_report ON assessments USING gin (investigation_report);
```

## Performance

### Expected Timing

- **Financial Agent**: ~5-10 seconds
- **Regulatory Agent**: ~10-15 seconds
- **Reputation Agent**: ~5-10 seconds
- **Cyber Agent**: ~10-15 seconds
- **Synthesis Agent**: ~60-120 seconds
- **Total**: ~90-180 seconds (1.5-3 minutes)

### Optimization Tips

1. Run as background task (already implemented)
2. Cache API responses for repeated company lookups
3. Use Redis for job status tracking (future enhancement)
4. Implement webhooks for completion notifications (future enhancement)

## Integration with Assessment Analysis

### Optional Trigger During Analysis

You can optionally trigger investigation during the assessment analysis workflow:

```python
# In assessments.py or analysis.py
from app.services.autonomous_investigator import run_autonomous_investigation

# After main analysis
if assessment.insured_entity_name:
    background_tasks.add_task(
        run_autonomous_investigation,
        company_name=assessment.insured_entity_name,
        assessment_id=str(assessment.id),
        companies_house_number=assessment.companies_house_number
    )
```

## Monitoring and Logging

### Log Locations

Logs written to standard logger: `logger = logging.getLogger(__name__)`

### Key Log Events

- `"Starting autonomous investigation for: {company_name}"`
- `"Financial Agent investigating: {company_name}"`
- `"Regulatory Agent investigating: {company_name}"`
- `"Reputation Agent investigating: {company_name}"`
- `"Cyber Agent investigating: {company_name}"`
- `"Synthesis Agent creating report for: {company_name}"`
- `"Investigation completed for {company_name}: {status}"`

### Error Tracking

Errors stored in:
1. Application logs
2. `investigation_report['errors']` array
3. `investigation_status` field

## Testing

### Manual Test

```bash
# 1. Create assessment with company name
curl -X POST https://api.com/api/v1/assessments \
  -H "Authorization: Bearer TOKEN" \
  -d '{
    "title": "Test Investigation",
    "insured_entity_name": "Microsoft Corporation",
    "risk_category": "cyber"
  }'

# 2. Trigger investigation
curl -X POST https://api.com/api/v1/investigation/run/{assessment_id} \
  -H "Authorization: Bearer TOKEN"

# 3. Wait 3 minutes, then get report
curl -X GET https://api.com/api/v1/investigation/report/{assessment_id} \
  -H "Authorization: Bearer TOKEN"
```

### Test Companies

Good test companies (known SEC filers):
- Microsoft Corporation
- Apple Inc.
- Tesla Inc.
- Goldman Sachs Group Inc.

## Troubleshooting

### "No investigation report available"

**Cause**: Investigation not yet triggered or still in progress

**Solution**:
1. Check status endpoint
2. Trigger investigation if not started
3. Wait for completion

### "Assessment must have insured_entity_name"

**Cause**: Assessment missing company name

**Solution**: Update assessment with `insured_entity_name` or `insured_name`

### "Company not found in SEC database"

**Cause**: Company not a US public company or name mismatch

**Solution**:
- Use exact legal name from SEC filings
- Private companies won't have SEC data (report will note this)

### Investigation status stuck at "in_progress"

**Cause**: Background task crashed or timeout

**Solution**:
1. Check application logs
2. Re-trigger investigation
3. Verify Bedrock credentials are valid

## Future Enhancements

### Phase 2 Improvements

1. **UK Companies House Integration**
   - Use `companies_house_number` for UK company data
   - Financial statements from Companies House API

2. **Real-time Progress Updates**
   - WebSocket support for live progress
   - Agent-by-agent completion notifications

3. **Report Caching**
   - Cache results for 24 hours
   - Incremental updates for repeat investigations

4. **Enhanced Data Sources**
   - Dun & Bradstreet integration
   - LinkedIn company profiles
   - Glassdoor reviews
   - Better Business Bureau ratings

5. **Multi-language Support**
   - Translate reports to user's preferred language
   - Support international company names

6. **Custom Agent Plugins**
   - Allow users to add custom data sources
   - Industry-specific agents (e.g., healthcare, aviation)

## Support

For issues or questions:
- Check application logs: `/var/log/instantrisk/`
- Review this documentation
- Contact: engineering@instantrisk.com

---

**Version**: 1.0
**Last Updated**: 2026-02-18
**Maintainer**: InstantRisk Engineering Team
