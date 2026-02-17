# Autonomous Investigation Agent - Feature Summary

## ✅ IMPLEMENTATION COMPLETE

The Autonomous Investigation Agent has been successfully built and integrated into InstantRisk V2.

---

## 📋 What Was Built

### 1. Multi-Agent Investigation System

**Technology**: LangGraph for orchestration, Claude (Bedrock) for synthesis

**5 Specialized Agents**:
1. **FinancialAgent** - Scrapes SEC EDGAR for 10-K filings, SIC codes, financial data
2. **RegulatoryAgent** - Checks OSHA workplace violations + EPA environmental compliance
3. **ReputationAgent** - Scrapes Google News for company mentions, sentiment analysis
4. **CyberAgent** - Checks HIBP data breaches + NIST CVE vulnerability database
5. **SynthesisAgent** - Uses Claude to generate comprehensive 20-page investigation report

**Workflow**: Sequential execution (Financial → Regulatory → Reputation → Cyber → Synthesis)

**Timing**: ~90-180 seconds (1.5-3 minutes)

---

## 🗂️ Files Created

### Core Implementation
1. **`backend/app/services/autonomous_investigator.py`** (620 lines)
   - LangGraph state machine
   - 5 agent implementations
   - Free data source integrations (SEC, OSHA, EPA, Google News, HIBP, CVE)
   - Error handling and resilience

2. **`backend/app/routers/investigation.py`** (350 lines)
   - 3 API endpoints (trigger, status, report)
   - Background task execution
   - Permission checks and validation

3. **`backend/alembic/versions/103_add_autonomous_investigation.py`**
   - Database migration
   - Adds `investigation_report` JSONB column
   - Adds `investigation_status` VARCHAR(20) column
   - Creates indexes

### Documentation
4. **`backend/AUTONOMOUS_INVESTIGATION_GUIDE.md`** (comprehensive user guide)
5. **`AUTONOMOUS_INVESTIGATION_DEPLOYMENT.md`** (deployment checklist)
6. **`test_autonomous_investigation.py`** (standalone test suite)

### Modified Files
- **`backend/requirements.txt`** - Added LangGraph, LangChain, BeautifulSoup4, Playwright
- **`backend/app/models/assessment.py`** - Added investigation columns
- **`backend/app/main.py`** - Registered router, added startup migration

---

## 🌐 API Endpoints

### 1. Trigger Investigation
```
POST /api/v1/investigation/run/{assessment_id}
```
Starts autonomous investigation (runs in background, ~3 minutes)

**Response**:
```json
{
  "job_id": "inv-abc123",
  "assessment_id": "uuid",
  "company_name": "Acme Corp",
  "status": "started",
  "message": "Investigation started. This will take approximately 3 minutes."
}
```

### 2. Check Status
```
GET /api/v1/investigation/status/{assessment_id}
```
Check progress of investigation

**Response**:
```json
{
  "job_id": "inv-abc123",
  "assessment_id": "uuid",
  "status": "completed",
  "started_at": "2026-02-18T12:00:00Z",
  "completed_at": "2026-02-18T12:03:15Z",
  "errors": []
}
```

### 3. Get Report
```
GET /api/v1/investigation/report/{assessment_id}
```
Retrieve full 20-page investigation report

**Response**:
```json
{
  "assessment_id": "uuid",
  "company_name": "Acme Corp",
  "overall_risk_score": 45,
  "recommendation": "GO",
  "report": {
    "report_text": "# EXECUTIVE SUMMARY\n...",
    "executive_summary": "...",
    "investigation_summary": {...}
  }
}
```

---

## 📊 Report Structure

Each investigation produces a comprehensive report with:

1. **Executive Summary**
   - Overall risk rating (Low/Medium/High/Critical)
   - Key findings (3-5 bullets)
   - Underwriting recommendation (GO/NO-GO/REFER)

2. **Financial Analysis**
   - SEC filing history
   - Industry classification
   - Financial health indicators

3. **Regulatory Compliance**
   - OSHA violations
   - EPA environmental record
   - Regulatory risk assessment

4. **Reputation Analysis**
   - Recent news sentiment (0-100 scale)
   - Crisis indicators
   - Brand risk

5. **Cyber Security**
   - Data breach history
   - Known vulnerabilities (CVEs)
   - Security maturity estimate

6. **Risk Scoring Matrix**
   - Financial Risk (0-100)
   - Regulatory Risk (0-100)
   - Reputation Risk (0-100)
   - Cyber Risk (0-100)
   - Overall Composite Risk (0-100)

7. **Underwriting Recommendations**
   - Coverage considerations
   - Premium factors
   - Required exclusions
   - Due diligence needs

---

## 🔌 Free Data Sources

All integrations use **free public APIs** (no auth required):

| Source | API | Data Retrieved |
|--------|-----|----------------|
| **SEC EDGAR** | data.sec.gov | 10-K filings, SIC code, fiscal data |
| **OSHA** | data.dol.gov | Workplace violations, penalties |
| **EPA ECHO** | echodata.epa.gov | Environmental violations (3yr) |
| **Google News** | news.google.com/rss | Recent articles, sentiment |
| **HIBP** | haveibeenpwned.com | Data breaches |
| **NIST NVD** | services.nvd.nist.gov | CVE vulnerabilities |

**No API keys required** - all sources are publicly accessible.

---

## 🗄️ Database Schema

### New Columns in `assessments` Table

```sql
-- Investigation report (JSONB)
investigation_report JSONB DEFAULT '{}'

-- Investigation status (VARCHAR)
investigation_status VARCHAR(20) DEFAULT 'not_started'
-- Values: 'not_started', 'in_progress', 'completed', 'failed'
```

### Indexes

```sql
CREATE INDEX idx_assessments_investigation_status ON assessments(investigation_status);
CREATE INDEX idx_assessments_investigation_report ON assessments USING gin (investigation_report);
```

---

## 📦 Dependencies Added

```txt
langgraph==0.2.60          # Multi-agent orchestration
langchain-anthropic==0.3.14 # Claude integration
beautifulsoup4==4.12.3     # HTML/XML parsing
playwright==1.50.0         # Browser automation (future use)
```

---

## 🚀 Deployment Steps

### 1. Install Dependencies
```bash
cd backend
pip install -r requirements.txt
```

### 2. Run Migration (Optional - auto-runs on startup)
```bash
alembic upgrade head
```

### 3. Deploy to AWS
Use existing deployment process (e.g., `deploy_v18.py`)

### 4. Verify
```bash
# Health check
curl https://your-api.com/api/v1/health

# Test investigation
curl -X POST https://your-api.com/api/v1/investigation/run/{assessment_id} \
  -H "Authorization: Bearer TOKEN"
```

---

## ✅ Testing

### Run Test Suite
```bash
python test_autonomous_investigation.py
```

Tests:
1. Individual agent data fetching (6 agents)
2. Full investigation workflow (end-to-end)
3. Report generation and validation

**Test Companies**:
- Microsoft Corporation
- Tesla Inc
- Apple Inc
- Goldman Sachs Group Inc

---

## 🔐 Security & Permissions

### Authentication
- All endpoints require JWT authentication
- User must own assessment OR be admin

### Data Privacy
- All data sources are **public** (no PII)
- Reports encrypted at rest (RDS)
- No sensitive data cached

### Rate Limiting
- Applied via existing middleware
- External API timeouts: 20-30 seconds

---

## 📈 Performance

### Expected Metrics
- **Success Rate**: >80% (depends on data availability)
- **Average Time**: 90-180 seconds
- **Memory Usage**: +200MB (LangGraph overhead)
- **CPU**: Minimal (I/O bound, async)

### Rate Limits (External APIs)
- SEC: Fair access policy
- EPA: 1000 requests/hour
- HIBP: 1 request/1.5 seconds
- NVD: 5 requests/30 seconds

---

## 🛠️ Troubleshooting

### Common Issues

**"Module not found: langgraph"**
→ Run `pip install -r requirements.txt`

**"Column investigation_report does not exist"**
→ Run `alembic upgrade head` or restart app

**"Company not found in SEC database"**
→ Expected for private companies (report will note limitation)

**Investigation stuck at "in_progress"**
→ Check CloudWatch logs, re-trigger investigation

---

## 📚 Documentation

- **User Guide**: `backend/AUTONOMOUS_INVESTIGATION_GUIDE.md`
- **Deployment**: `AUTONOMOUS_INVESTIGATION_DEPLOYMENT.md`
- **Test Script**: `test_autonomous_investigation.py`
- **API Docs**: `/docs` endpoint (Swagger UI)

---

## 🎯 Future Enhancements (Phase 2)

1. **UK Companies House Integration**
   - Use `companies_house_number` for UK entity data
   - Financial statements API

2. **Report Caching**
   - Redis cache for 24 hours
   - Incremental updates

3. **WebSocket Progress**
   - Real-time agent notifications
   - Frontend progress bar

4. **Custom Agents**
   - User-defined data sources
   - Industry-specific plugins

5. **Batch Investigations**
   - Portfolio-level risk analysis
   - Parallel execution

---

## 🏁 Status

**Status**: ✅ **Ready for Deployment**

**Completeness**: 100%

**Checklist**:
- ✅ Service layer (autonomous_investigator.py)
- ✅ API router (investigation.py)
- ✅ Database migration (103_add_autonomous_investigation.py)
- ✅ Model updates (assessment.py)
- ✅ Main.py integration
- ✅ Dependencies (requirements.txt)
- ✅ Documentation (3 comprehensive guides)
- ✅ Test suite (test_autonomous_investigation.py)
- ✅ Error handling and resilience
- ✅ Permission checks
- ✅ Background task execution

---

## 📞 Support

- **Documentation**: See `AUTONOMOUS_INVESTIGATION_GUIDE.md`
- **Issues**: Check CloudWatch logs at `/ecs/instantrisk-backend`
- **Contact**: engineering@instantrisk.com

---

**Feature**: Autonomous Investigation Agent
**Version**: 1.0
**Implemented**: 2026-02-18
**Ready**: ✅ YES
