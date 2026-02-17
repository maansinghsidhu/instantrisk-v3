# Autonomous Investigation Agent - Deployment Checklist

## Overview

The Autonomous Investigation Agent feature has been successfully implemented. This document provides a deployment checklist and verification steps.

## Files Created/Modified

### New Files

1. **Service Layer**
   - `backend/app/services/autonomous_investigator.py` (620 lines)
     - Multi-agent LangGraph orchestration
     - 5 specialized agents (Financial, Regulatory, Reputation, Cyber, Synthesis)
     - Free data source integrations (SEC, OSHA, EPA, News, HIBP, CVE)

2. **API Router**
   - `backend/app/routers/investigation.py` (350 lines)
     - POST `/api/v1/investigation/run/{assessment_id}` - Trigger investigation
     - GET `/api/v1/investigation/status/{assessment_id}` - Check status
     - GET `/api/v1/investigation/report/{assessment_id}` - Get report

3. **Database Migration**
   - `backend/alembic/versions/103_add_autonomous_investigation.py`
     - Adds `investigation_report` JSONB column
     - Adds `investigation_status` VARCHAR(20) column
     - Creates GIN and B-tree indexes

4. **Documentation**
   - `backend/AUTONOMOUS_INVESTIGATION_GUIDE.md` (comprehensive guide)
   - `AUTONOMOUS_INVESTIGATION_DEPLOYMENT.md` (this file)

5. **Test Script**
   - `test_autonomous_investigation.py` (standalone test suite)

### Modified Files

1. **Requirements**
   - `backend/requirements.txt`
     - Added: langgraph==0.2.60
     - Added: langchain-anthropic==0.3.14
     - Added: beautifulsoup4==4.12.3
     - Added: playwright==1.50.0

2. **Database Model**
   - `backend/app/models/assessment.py`
     - Added `investigation_report` column
     - Added `investigation_status` column

3. **Main Application**
   - `backend/app/main.py`
     - Imported investigation router
     - Registered router at `/api/v1/investigation`
     - Added migration SQL to startup

## Pre-Deployment Checklist

### 1. Dependencies

- [ ] Install new Python packages:
  ```bash
  cd backend
  pip install -r requirements.txt
  ```

### 2. Database Migration

- [ ] Run Alembic migration:
  ```bash
  cd backend
  alembic upgrade head
  ```

  Or, migration will auto-run on app startup.

### 3. Environment Variables

- [ ] Verify AWS Bedrock credentials are set:
  ```bash
  # Check .env or environment
  AWS_BEDROCK_REGION=us-east-1
  BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-5-20250929-v1:0
  BEDROCK_ENABLED=true
  ```

### 4. AWS Permissions

- [ ] Ensure ECS task role has Bedrock permissions:
  ```json
  {
    "Effect": "Allow",
    "Action": [
      "bedrock:InvokeModel",
      "bedrock:InvokeModelWithResponseStream"
    ],
    "Resource": "arn:aws:bedrock:us-east-1::foundation-model/*"
  }
  ```

### 5. Code Review

- [ ] Review `autonomous_investigator.py` for security
- [ ] Review `investigation.py` for permissions logic
- [ ] Verify error handling in all agents

## Deployment Steps

### Option 1: Local Testing

```bash
# 1. Navigate to backend
cd backend

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run test script
cd ..
python test_autonomous_investigation.py

# 4. Start local server
cd backend
uvicorn app.main:app --reload --port 8200
```

### Option 2: AWS Deployment

Use existing deployment script with updated code:

```bash
# Update AWS credentials first
# Then run deploy script
python deploy/deploy_v18.py
```

Or manually:

```bash
# 1. Zip backend
cd backend
zip -r ../backend.zip . -x "*__pycache__*" -x "*.pyc"

# 2. Upload to S3
aws s3 cp ../backend.zip s3://your-bucket/backend.zip

# 3. Trigger CodeBuild or update ECS task
# (follow existing deployment process)
```

## Post-Deployment Verification

### 1. Health Check

```bash
curl https://your-api.com/api/v1/health
```

Expected: `{"status": "healthy"}`

### 2. Database Columns

Connect to RDS and verify:

```sql
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'assessments'
AND column_name IN ('investigation_report', 'investigation_status');
```

Expected:
- `investigation_report` | `jsonb`
- `investigation_status` | `character varying`

### 3. API Endpoint Test

```bash
# Create test assessment
curl -X POST https://your-api.com/api/v1/assessments \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Test Investigation",
    "insured_entity_name": "Microsoft Corporation",
    "risk_category": "cyber"
  }'

# Trigger investigation (use assessment_id from response)
curl -X POST https://your-api.com/api/v1/investigation/run/{assessment_id} \
  -H "Authorization: Bearer YOUR_TOKEN"

# Check status (wait 3 minutes)
curl -X GET https://your-api.com/api/v1/investigation/status/{assessment_id} \
  -H "Authorization: Bearer YOUR_TOKEN"

# Get report
curl -X GET https://your-api.com/api/v1/investigation/report/{assessment_id} \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 4. Log Verification

Check CloudWatch logs for:
- "Financial Agent investigating: ..."
- "Regulatory Agent investigating: ..."
- "Reputation Agent investigating: ..."
- "Cyber Agent investigating: ..."
- "Synthesis Agent creating report for: ..."
- "Investigation completed for ..."

## Troubleshooting

### Issue: "Module not found: langgraph"

**Solution**: Install dependencies:
```bash
pip install langgraph langchain-anthropic beautifulsoup4 playwright
```

### Issue: "Column investigation_report does not exist"

**Solution**: Run migration:
```bash
alembic upgrade head
```

Or restart app (migration auto-runs).

### Issue: "Bedrock API error"

**Solution**: Verify AWS credentials:
```bash
aws bedrock list-foundation-models --region us-east-1
```

### Issue: Investigation stuck at "in_progress"

**Solution**: Check logs for errors. Background task may have crashed. Re-trigger investigation.

### Issue: "Company not found in SEC database"

**Expected**: Private companies won't have SEC data. Report will note this limitation.

## Performance Notes

### Expected Timing

- Financial Agent: 5-10 seconds
- Regulatory Agent: 10-15 seconds
- Reputation Agent: 5-10 seconds
- Cyber Agent: 10-15 seconds
- Synthesis Agent: 60-120 seconds
- **Total**: 90-180 seconds (~1.5-3 minutes)

### Resource Usage

- **Memory**: ~200MB additional (LangGraph + agents)
- **CPU**: Minimal (I/O bound, async)
- **Network**: ~10 external API calls per investigation

### Rate Limits

All free data sources have rate limits:
- **SEC EDGAR**: Fair access policy (no hard limit)
- **OSHA**: No published limit
- **EPA**: 1000 requests/hour
- **Google News RSS**: No hard limit
- **HIBP**: 1 request/1.5 seconds
- **NIST NVD**: 5 requests/30 seconds

For high-volume deployments, implement caching.

## Monitoring

### Metrics to Track

1. **Investigation Success Rate**
   ```sql
   SELECT
     investigation_status,
     COUNT(*) as count
   FROM assessments
   WHERE investigation_status IS NOT NULL
   GROUP BY investigation_status;
   ```

2. **Average Investigation Time**
   ```sql
   SELECT
     AVG(
       EXTRACT(EPOCH FROM (
         (investigation_report->>'completed_at')::timestamp -
         (investigation_report->>'started_at')::timestamp
       ))
     ) as avg_seconds
   FROM assessments
   WHERE investigation_status = 'completed';
   ```

3. **Agent Failure Rates**
   ```sql
   SELECT
     COUNT(*) as total,
     COUNT(CASE WHEN investigation_report->'financial_data' ? 'error' THEN 1 END) as financial_errors,
     COUNT(CASE WHEN investigation_report->'regulatory_data' ? 'error' THEN 1 END) as regulatory_errors,
     COUNT(CASE WHEN investigation_report->'reputation_data' ? 'error' THEN 1 END) as reputation_errors,
     COUNT(CASE WHEN investigation_report->'cyber_data' ? 'error' THEN 1 END) as cyber_errors
   FROM assessments
   WHERE investigation_status = 'completed';
   ```

### CloudWatch Alarms

Create alarms for:
- Investigation failure rate > 20%
- Average investigation time > 300 seconds
- Agent error rate > 30%

## Rollback Plan

If issues occur:

### 1. Disable Feature

Add to `.env`:
```
INVESTIGATION_ENABLED=false
```

Then check in code (optional enhancement):
```python
INVESTIGATION_ENABLED = os.getenv("INVESTIGATION_ENABLED", "true").lower() == "true"

@router.post("/run/{assessment_id}")
async def trigger_investigation(...):
    if not INVESTIGATION_ENABLED:
        raise HTTPException(status_code=503, detail="Investigation feature disabled")
```

### 2. Database Rollback

```sql
-- Remove columns (if needed)
ALTER TABLE assessments DROP COLUMN IF EXISTS investigation_report;
ALTER TABLE assessments DROP COLUMN IF EXISTS investigation_status;

-- Or run migration downgrade
-- alembic downgrade -1
```

### 3. Code Rollback

Revert to previous deployment:
```bash
# Use previous CodeBuild build
# Or deploy previous version tag
```

## Security Considerations

### Data Privacy

- All data sources are **public** (SEC, OSHA, EPA, News, HIBP, CVE)
- No PII is collected
- Reports stored in JSONB (encrypted at rest in RDS)

### API Security

- All endpoints require JWT authentication
- Permission checks: user must own assessment or be admin
- Rate limiting applied via existing middleware

### External API Risks

- **Timeout protection**: All requests have 20-30s timeouts
- **Error isolation**: Agent failures don't crash workflow
- **User-Agent identification**: All requests identify as InstantRisk

### Data Source Trust

- **SEC**: Official US government source (trusted)
- **OSHA/EPA**: Official US government sources (trusted)
- **Google News RSS**: Public feed (moderate trust)
- **HIBP**: Well-known breach database (trusted)
- **NIST NVD**: Official CVE database (trusted)

## Future Enhancements

### Phase 2 (Post-Deployment)

1. **UK Companies House Integration**
   - Use `companies_house_number` for UK entity data
   - Financial statements API

2. **Report Caching**
   - Redis cache for 24 hours
   - Incremental updates

3. **WebSocket Progress**
   - Real-time agent completion notifications
   - Frontend progress bar

4. **Custom Agents**
   - User-defined data sources
   - Industry-specific plugins

5. **Batch Investigations**
   - Investigate multiple companies in parallel
   - Portfolio-level risk reports

## Support & Contacts

- **Engineering Lead**: engineering@instantrisk.com
- **Documentation**: `backend/AUTONOMOUS_INVESTIGATION_GUIDE.md`
- **Logs**: CloudWatch Logs Group `/ecs/instantrisk-backend`
- **Monitoring**: CloudWatch Dashboard

## Sign-Off

- [ ] Code reviewed and approved
- [ ] Tests passed (local and integration)
- [ ] Database migration verified
- [ ] AWS permissions confirmed
- [ ] Documentation complete
- [ ] Deployment plan reviewed
- [ ] Rollback plan tested
- [ ] Monitoring configured
- [ ] Team trained on new feature

**Deployed By**: ___________________
**Date**: ___________________
**Environment**: ☐ Development ☐ Staging ☐ Production

---

**Version**: 1.0
**Feature**: Autonomous Investigation Agent
**Status**: Ready for Deployment
**Last Updated**: 2026-02-18
