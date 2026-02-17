# Autonomous Investigation Agent - Architecture Diagram

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           INSTANTRISK FRONTEND                               │
│                        (React/Next.js/Flutter)                               │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      │ HTTPS (JWT Auth)
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        FASTAPI APPLICATION (main.py)                         │
│                                                                               │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │              /api/v1/investigation/* Router                            │ │
│  │                (investigation.py)                                      │ │
│  ├────────────────────────────────────────────────────────────────────────┤ │
│  │  POST   /run/{assessment_id}      → Trigger Investigation             │ │
│  │  GET    /status/{assessment_id}   → Check Status                      │ │
│  │  GET    /report/{assessment_id}   → Get Report                        │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                        │
│                                      │ Background Task                        │
│                                      ▼                                        │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │         Autonomous Investigator Service                                │ │
│  │          (autonomous_investigator.py)                                  │ │
│  │                                                                         │ │
│  │   ┌─────────────────────────────────────────────────────────────────┐ │ │
│  │   │              LangGraph State Machine                             │ │
│  │   │                                                                   │ │
│  │   │    InvestigationState:                                           │ │
│  │   │    - company_name                                                │ │
│  │   │    - assessment_id                                               │ │
│  │   │    - financial_data                                              │ │
│  │   │    - regulatory_data                                             │ │
│  │   │    - reputation_data                                             │ │
│  │   │    - cyber_data                                                  │ │
│  │   │    - final_report                                                │ │
│  │   │    - status, errors                                              │ │
│  │   └─────────────────────────────────────────────────────────────────┘ │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      │ Sequential Workflow
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        AGENT EXECUTION PIPELINE                              │
└─────────────────────────────────────────────────────────────────────────────┘

        ┌──────────────────────────────────────────────────────────┐
        │                  1. Financial Agent                      │
        │                  (~5-10 seconds)                         │
        │                                                           │
        │  Data Source: SEC EDGAR                                  │
        │  API: https://data.sec.gov/submissions/CIK{}.json       │
        │                                                           │
        │  Retrieves:                                              │
        │  ✓ Recent 10-K/10-Q filings                             │
        │  ✓ SIC code & industry classification                   │
        │  ✓ Company address & fiscal year end                    │
        └──────────────────────────────────────────────────────────┘
                              │
                              ▼
        ┌──────────────────────────────────────────────────────────┐
        │                  2. Regulatory Agent                     │
        │                  (~10-15 seconds)                        │
        │                                                           │
        │  Data Sources: OSHA + EPA ECHO                          │
        │  APIs:                                                   │
        │  - https://data.dol.gov/get/inspection_detail/{}        │
        │  - https://echodata.epa.gov/echo/facility_search/...    │
        │                                                           │
        │  Retrieves:                                              │
        │  ✓ OSHA workplace violations & penalties                │
        │  ✓ EPA environmental violations (3yr history)           │
        │  ✓ Compliance status                                    │
        └──────────────────────────────────────────────────────────┘
                              │
                              ▼
        ┌──────────────────────────────────────────────────────────┐
        │                  3. Reputation Agent                     │
        │                  (~5-10 seconds)                         │
        │                                                           │
        │  Data Source: Google News RSS                           │
        │  API: https://news.google.com/rss/search?q={}           │
        │                                                           │
        │  Retrieves:                                              │
        │  ✓ Recent news articles (last 10)                       │
        │  ✓ Sentiment analysis (0-100 scale)                     │
        │  ✓ Negative keyword count                               │
        └──────────────────────────────────────────────────────────┘
                              │
                              ▼
        ┌──────────────────────────────────────────────────────────┐
        │                    4. Cyber Agent                        │
        │                  (~10-15 seconds)                        │
        │                                                           │
        │  Data Sources: HIBP + NIST NVD                          │
        │  APIs:                                                   │
        │  - https://haveibeenpwned.com/api/v3/breaches           │
        │  - https://services.nvd.nist.gov/rest/json/cves/2.0     │
        │                                                           │
        │  Retrieves:                                              │
        │  ✓ Data breach history                                  │
        │  ✓ CVE vulnerabilities                                  │
        │  ✓ Security incident count                              │
        └──────────────────────────────────────────────────────────┘
                              │
                              ▼
        ┌──────────────────────────────────────────────────────────┐
        │                  5. Synthesis Agent                      │
        │                  (~60-120 seconds)                       │
        │                                                           │
        │  AI Model: Claude Sonnet 4.5 (AWS Bedrock)             │
        │  Model ID: us.anthropic.claude-sonnet-4-5-20250929-v1:0 │
        │                                                           │
        │  Generates:                                              │
        │  ✓ Comprehensive 20-page investigation report           │
        │  ✓ Executive summary                                    │
        │  ✓ Risk scoring matrix (0-100)                          │
        │  ✓ Underwriting recommendation (GO/NO-GO/REFER)         │
        │  ✓ Detailed analysis of all findings                    │
        └──────────────────────────────────────────────────────────┘
                              │
                              ▼
        ┌──────────────────────────────────────────────────────────┐
        │                   Final Report Output                    │
        │                                                           │
        │  {                                                        │
        │    "report_text": "# EXECUTIVE SUMMARY\n...",           │
        │    "overall_risk_score": 45,                            │
        │    "recommendation": "GO",                              │
        │    "executive_summary": "...",                          │
        │    "investigation_summary": {                           │
        │      "financial_findings": {...},                       │
        │      "regulatory_findings": {...},                      │
        │      "reputation_findings": {...},                      │
        │      "cyber_findings": {...}                            │
        │    }                                                     │
        │  }                                                        │
        └──────────────────────────────────────────────────────────┘
                              │
                              │ Store Results
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       POSTGRESQL DATABASE (RDS)                              │
│                                                                               │
│   assessments table:                                                         │
│   ┌────────────────────────────────────────────────────────────┐            │
│   │ id                      UUID                                │            │
│   │ insured_entity_name     VARCHAR(500)                       │            │
│   │ investigation_status    VARCHAR(20)  ← "completed"         │            │
│   │ investigation_report    JSONB        ← Full report JSON    │            │
│   │ risk_score              INTEGER      ← Overall score       │            │
│   │ ...                                                         │            │
│   └────────────────────────────────────────────────────────────┘            │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Data Flow Sequence

```
User Request
    │
    ├─► 1. POST /api/v1/investigation/run/{assessment_id}
    │      │
    │      ├─► Validate assessment exists
    │      ├─► Check user permissions
    │      ├─► Extract company_name
    │      ├─► Set investigation_status = "in_progress"
    │      └─► Trigger background task
    │
    ├─► 2. Background Task: run_autonomous_investigation()
    │      │
    │      ├─► Initialize LangGraph state
    │      │
    │      ├─► Execute Financial Agent
    │      │   └─► Fetch SEC EDGAR data
    │      │       ├─► Search for CIK
    │      │       └─► Get company submissions
    │      │
    │      ├─► Execute Regulatory Agent
    │      │   ├─► Fetch OSHA violations
    │      │   └─► Fetch EPA violations
    │      │
    │      ├─► Execute Reputation Agent
    │      │   └─► Scrape Google News RSS
    │      │       ├─► Parse articles
    │      │       └─► Calculate sentiment
    │      │
    │      ├─► Execute Cyber Agent
    │      │   ├─► Check HIBP breaches
    │      │   └─► Query CVE database
    │      │
    │      ├─► Execute Synthesis Agent
    │      │   └─► Call Claude via Bedrock
    │      │       ├─► Build comprehensive prompt
    │      │       ├─► Generate 20-page report
    │      │       └─► Extract risk score & recommendation
    │      │
    │      └─► Store results in database
    │          ├─► investigation_report = final_report
    │          ├─► investigation_status = "completed"
    │          └─► risk_score = overall_risk_score
    │
    ├─► 3. GET /api/v1/investigation/status/{assessment_id}
    │      └─► Return current status (in_progress/completed/failed)
    │
    └─► 4. GET /api/v1/investigation/report/{assessment_id}
           └─► Return full investigation report
```

## Component Interaction Diagram

```
┌──────────────┐
│   Frontend   │
└──────┬───────┘
       │ HTTP/HTTPS
       │
┌──────▼───────────────────────────────────────────────────┐
│                   FastAPI Router                         │
│                (investigation.py)                        │
│                                                           │
│  ┌─────────────────────────────────────────────────┐    │
│  │  POST /run/{id}                                 │    │
│  │  - Validate assessment                          │    │
│  │  - Check permissions                            │    │
│  │  - Trigger background task ────────────┐       │    │
│  └─────────────────────────────────────────────────┘    │
│                                             │             │
│  ┌─────────────────────────────────────────────────┐    │
│  │  GET /status/{id}                       │       │    │
│  │  - Query database                       │       │    │
│  │  - Return status ◄──────────────────────┼───────┤    │
│  └─────────────────────────────────────────────────┘    │
│                                             │             │
│  ┌─────────────────────────────────────────────────┐    │
│  │  GET /report/{id}                       │       │    │
│  │  - Query database                       │       │    │
│  │  - Return full report ◄─────────────────┼───────┤    │
│  └─────────────────────────────────────────────────┘    │
└──────────────────────────────────────────┬───────────────┘
                                           │
                    Background Task        │
                                           │
       ┌───────────────────────────────────▼─────────────────────┐
       │      Autonomous Investigator Service                     │
       │     (autonomous_investigator.py)                         │
       │                                                           │
       │  ┌──────────────────────────────────────────────┐       │
       │  │        LangGraph Workflow Engine             │       │
       │  │                                               │       │
       │  │   StateGraph(InvestigationState)            │       │
       │  │   │                                           │       │
       │  │   ├─► Financial Agent ──────┐               │       │
       │  │   │                          │               │       │
       │  │   ├─► Regulatory Agent ──────┤               │       │
       │  │   │                          │               │       │
       │  │   ├─► Reputation Agent ──────┤               │       │
       │  │   │                          │               │       │
       │  │   ├─► Cyber Agent ───────────┤               │       │
       │  │   │                          │               │       │
       │  │   └─► Synthesis Agent ───────┴─► Final Report│       │
       │  └──────────────────────────────────────────────┘       │
       └───────────────┬─────────────────────┬────────────────────┘
                       │                     │
                External APIs        AWS Bedrock (Claude)
                       │                     │
       ┌───────────────▼─────────────┐      │
       │  Free Data Sources:         │      │
       │  - SEC EDGAR                │      │
       │  - OSHA                     │      │
       │  - EPA ECHO                 │      │
       │  - Google News RSS          │      │
       │  - HIBP                     │      │
       │  - NIST NVD                 │      │
       └─────────────────────────────┘      │
                                             │
                    ┌────────────────────────▼────────────┐
                    │   AWS Bedrock Runtime               │
                    │   Model: Claude Sonnet 4.5          │
                    │   Region: us-east-1                 │
                    └─────────────────────────────────────┘
```

## Error Handling Flow

```
Agent Execution
    │
    ├─► Try: Fetch data from external API
    │      │
    │      ├─► Success
    │      │   └─► Store data in state
    │      │
    │      └─► Error (timeout/network/API failure)
    │          ├─► Log error
    │          ├─► Add to state['errors']
    │          ├─► Store partial data with {"error": "..."}
    │          └─► Continue to next agent
    │
    └─► Workflow continues regardless of individual agent failures

Final Report Generation
    │
    ├─► All agent data available (including errors)
    │   └─► Claude synthesis includes notes about missing data
    │
    └─► Synthesis fails
        ├─► investigation_status = "failed"
        ├─► investigation_report = {"error": "..."}
        └─► User notified via status endpoint
```

## Scalability & Performance

```
┌─────────────────────────────────────────────────────────────┐
│                    Performance Profile                      │
├─────────────────────────────────────────────────────────────┤
│  Concurrency: Async/await throughout                        │
│  - FastAPI async endpoints                                  │
│  - aiohttp for all HTTP requests                           │
│  - Bedrock async client (run_in_executor)                  │
│                                                              │
│  Resource Usage (per investigation):                        │
│  - Memory: ~200MB                                           │
│  - CPU: <5% (I/O bound)                                    │
│  - Network: ~10 external API calls                         │
│  - Bedrock tokens: ~16,000 (synthesis)                     │
│                                                              │
│  Timeouts:                                                  │
│  - Individual agents: 20-30s                               │
│  - Total workflow: 180s max                                │
│                                                              │
│  Rate Limits:                                               │
│  - SEC EDGAR: Fair access policy                           │
│  - EPA: 1000 req/hour                                      │
│  - HIBP: 1 req/1.5s                                        │
│  - NVD: 5 req/30s                                          │
│                                                              │
│  Optimization:                                              │
│  - Background task execution (non-blocking)                │
│  - Sequential agent execution (no parallelization yet)     │
│  - No caching (Phase 2 enhancement)                        │
└─────────────────────────────────────────────────────────────┘
```

## Security Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                     Security Layers                          │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  1. Authentication & Authorization                           │
│     ├─► JWT token validation (all endpoints)                │
│     ├─► User ownership check (assessment.created_by)        │
│     └─► Admin override permission                           │
│                                                               │
│  2. Data Privacy                                             │
│     ├─► All data sources are PUBLIC                         │
│     ├─► No PII collected                                    │
│     ├─► Reports encrypted at rest (RDS)                     │
│     └─► HTTPS for all external API calls                    │
│                                                               │
│  3. Rate Limiting                                            │
│     ├─► SlowAPI middleware (existing)                       │
│     ├─► Per-user rate limits                                │
│     └─► External API timeouts (20-30s)                      │
│                                                               │
│  4. Error Isolation                                          │
│     ├─► Agent failures don't crash workflow                 │
│     ├─► Timeout protection on all HTTP calls                │
│     └─► Graceful degradation (partial reports)              │
│                                                               │
│  5. Audit Trail                                              │
│     ├─► All investigations logged                           │
│     ├─► Status transitions tracked                          │
│     └─► Error details stored in database                    │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

---

**Architecture Version**: 1.0
**Last Updated**: 2026-02-18
**Status**: Production Ready
