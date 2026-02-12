# InstantRisk v2

AI-powered insurance underwriting platform for Lloyd's syndicates. Automates risk assessment, document generation, and compliance analysis using a 19-agent AI pipeline.

## Structure

```
instantrisk-v2/
├── backend/           # FastAPI backend (Python 3.11)
│   ├── app/
│   │   ├── routers/   # API endpoints
│   │   ├── services/  # Business logic & AI pipeline
│   │   ├── models/    # SQLAlchemy models
│   │   ├── schemas/   # Pydantic schemas
│   │   ├── agents/    # 19-agent OpenDraft pipeline
│   │   ├── ml/        # ML models & embeddings
│   │   └── core/      # Config, auth, dependencies
│   ├── alembic/       # Database migrations
│   ├── Dockerfile
│   ├── buildspec.yml  # CodeBuild spec
│   └── requirements.txt
├── frontend/          # Flutter web app (Dart)
│   ├── lib/
│   │   ├── core/      # Theme, services, auth
│   │   └── presentation/ # Screens & widgets
│   ├── web/           # Web assets, icons, manifest
│   ├── assets/        # Images, brand assets
│   └── pubspec.yaml
├── website/           # Marketing website (static HTML/CSS/JS)
│   ├── index.html
│   ├── features.html
│   ├── technology.html
│   ├── platform.html
│   ├── css/
│   └── assets/
├── infrastructure/    # IaC and task definitions
│   ├── cloudformation/
│   ├── terraform/
│   └── *-task-definition.json
├── deploy/            # Deployment scripts
├── lambda/            # Lambda functions (rapidrate)
├── data/              # Training/seed data & embeddings
└── README.md
```

## Key Features

- **Risk Assessment Engine** - Automated property, casualty, marine, and specialty risk analysis
- **19-Agent Document Pipeline** - OpenDraft system with 6 phases: research, extraction, analysis, generation, review, compliance
- **Reference Document Training** - Upload PDFs/docs for OCR processing and vector-based RAG retrieval
- **Real-time Analysis** - WebSocket progress tracking with polling fallback
- **Shareable Results** - Token-based share links with expiry for assessment reports
- **Subscription Tiers** - Trial, professional, and premium access levels
- **AI Chat Assistant** - Context-aware underwriting Q&A

## AWS Infrastructure

| Service | Resource |
|---------|----------|
| ECS Cluster | `instantrisk` (Fargate) |
| Backend | ECS service + ALB (`instantrisk-alb`) |
| Qdrant | ECS service (vector DB on EFS) |
| RDS | PostgreSQL (`instantrisk-db`) |
| ElastiCache | Redis (`instantrisk-redis`) |
| EFS | `fs-090ad3238b9702fb0` (Qdrant storage) |
| ECR | `instantrisk-backend`, `instantrisk-qdrant`, `instantrisk-rapidrate` |
| S3 | Frontend hosting + CodeBuild artifacts |
| CloudFront | Frontend & website CDN |
| CodeBuild | Backend Docker build pipeline |

## Deployment

- **Backend**: zip → S3 → CodeBuild → ECR → ECS (force new deployment)
- **Frontend**: Flutter build web → S3 → CloudFront invalidation
- **Website**: Static files → S3 → CloudFront invalidation
- **Health check**: `GET /api/v1/health/live`

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | FastAPI, SQLAlchemy, asyncpg, pgvector |
| AI/ML | sentence-transformers, OpenAI, AutoGen agents |
| OCR | RapidOCR, PyMuPDF, pytesseract |
| Vector DB | pgvector (PostgreSQL), Qdrant |
| Frontend | Flutter Web (Dart) |
| Auth | JWT (python-jose), bcrypt |
| PDF Gen | WeasyPrint, ReportLab |
| Cache | Redis (aioredis) |
| Infra | AWS ECS Fargate, ALB, RDS, CloudFront |
