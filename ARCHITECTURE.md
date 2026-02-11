# InstantRisk v2 - Full Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USERS                                          │
│                     (Web Browser / Mobile App)                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          CLOUDFRONT CDN                                     │
│                   (instantrisk.cloudfront.net)                              │
│                   - SSL termination                                         │
│                   - Caching for static assets                               │
└─────────────────────────────────────────────────────────────────────────────┘
                    │                               │
                    ▼                               ▼
    ┌───────────────────────────┐     ┌───────────────────────────────────────┐
    │      S3 BUCKET            │     │    APPLICATION LOAD BALANCER          │
    │  (Flutter Web Assets)     │     │    instantrisk-alb-307384033          │
    │  - index.html             │     │    - Routes /api/* to ECS             │
    │  - main.dart.js           │     │    - Health checks /api/v1/health     │
    │  - assets/                │     └───────────────────────────────────────┘
    └───────────────────────────┘                     │
                                                      ▼
                                    ┌─────────────────────────────────────────┐
                                    │         ECS FARGATE CLUSTER             │
                                    │           "instantrisk"                 │
                                    ├─────────────────────────────────────────┤
                                    │  ┌─────────────────────────────────┐    │
                                    │  │   Backend Service (FastAPI)     │    │
                                    │  │   - Task Definition: v46        │    │
                                    │  │   - Port: 8000                  │    │
                                    │  │   - 36 API routers              │    │
                                    │  │   - AutoGen AI pipeline         │    │
                                    │  │   - ClaimSense integration      │    │
                                    │  └─────────────────────────────────┘    │
                                    │  ┌─────────────────────────────────┐    │
                                    │  │   Qdrant Service (Vector DB)    │    │
                                    │  │   - Task Definition: v3         │    │
                                    │  │   - Port: 6333                  │    │
                                    │  │   - EFS persistence             │    │
                                    │  └─────────────────────────────────┘    │
                                    └─────────────────────────────────────────┘
                                                      │
                    ┌─────────────────────────────────┼─────────────────────────────────┐
                    │                                 │                                 │
                    ▼                                 ▼                                 ▼
    ┌───────────────────────────┐   ┌───────────────────────────┐   ┌───────────────────────────┐
    │       RDS POSTGRES        │   │     ELASTICACHE REDIS     │   │      EFS STORAGE          │
    │  instantrisk-db           │   │  instantrisk-redis        │   │  fs-090ad3238b9702fb0     │
    │  - Users, Assessments     │   │  - Session cache          │   │  - Qdrant vector data     │
    │  - Documents, Chat        │   │  - Rate limiting          │   │  - Persistent storage     │
    └───────────────────────────┘   └───────────────────────────┘   └───────────────────────────┘
                                                      │
                                                      ▼
                                    ┌─────────────────────────────────────────┐
                                    │        AWS BEDROCK (AI Models)          │
                                    │  - Claude for chat & analysis           │
                                    │  - Embeddings for RAG                   │
                                    └─────────────────────────────────────────┘


## Source Code Repositories

### Current State (from EC2)
```
/home/ubuntu/instantrisk-v2/
├── mobile/           # 152MB - Flutter app (iOS/Android/Web)
├── backend/          # 12GB - Python FastAPI (original)
├── frontend/         # 35MB - React frontend (legacy?)
├── admin/            # Admin panel
├── nginx/            # Nginx config
├── docker-compose.yml
├── sample_docs/      # Test documents
├── scripts/          # Utility scripts
└── docs/             # Documentation
```

### Target State (CodeCommit)
```
instantrisk-v2/
├── backend/                    # FastAPI backend
│   ├── app/
│   │   ├── main.py
│   │   ├── routers/           # 36 API routers
│   │   ├── services/          # 49 business services
│   │   ├── models/            # SQLAlchemy models
│   │   ├── schemas/           # Pydantic schemas
│   │   └── autogen/           # AI agents
│   ├── Dockerfile
│   └── requirements.txt
├── mobile/                     # Flutter frontend
│   ├── lib/
│   │   ├── core/              # Theme, config, auth
│   │   ├── data/              # Models, repositories
│   │   └── presentation/      # Screens, widgets
│   ├── web/
│   └── pubspec.yaml
├── infrastructure/             # IaC (Terraform/CDK)
│   ├── ecs.tf
│   ├── rds.tf
│   ├── elasticache.tf
│   └── cloudfront.tf
└── docs/
    └── ARCHITECTURE.md
```


## Deployment Pipeline

### Backend (Python → ECS Fargate)
```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  CodeCommit │───▶│  CodeBuild  │───▶│     ECR     │───▶│ ECS Fargate │
│  (source)   │    │  (Docker)   │    │  (images)   │    │  (deploy)   │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
     push              build             push              update
```

### Frontend (Flutter → S3/CloudFront)
```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  CodeCommit │───▶│  CodeBuild  │───▶│     S3      │───▶│ CloudFront  │
│  (source)   │    │ flutter web │    │  (assets)   │    │ (invalidate)│
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
     push           build web           sync            invalidation
```


## AWS Resources Summary

| Resource | Name/ID | Purpose |
|----------|---------|---------|
| **ECS Cluster** | instantrisk | Container orchestration |
| **Backend Service** | instantrisk-backend | API containers |
| **Qdrant Service** | instantrisk-qdrant | Vector DB containers |
| **ALB** | instantrisk-alb-307384033 | Load balancing |
| **RDS** | instantrisk-db | PostgreSQL database |
| **ElastiCache** | instantrisk-redis | Redis cache |
| **EFS** | fs-090ad3238b9702fb0 | Qdrant persistence |
| **ECR** | instantrisk-backend | Backend images |
| **ECR** | instantrisk-qdrant | Qdrant images |
| **S3** | instantrisk-frontend | Flutter web assets |
| **CloudFront** | (TBD) | CDN distribution |
| **CodeBuild** | instantrisk-backend | CI/CD for backend |
| **VPC** | Default | Network isolation |
| **Security Groups** | sg-08a3aa7f87aa911ff (backend) | Firewall rules |
| **Service Discovery** | instantrisk.local | Internal DNS |


## Environment Variables

### Backend (ECS Task Definition)
```
POSTGRES_HOST=instantrisk-db.cyjui2sqceiw.us-east-1.rds.amazonaws.com
POSTGRES_PORT=5432
POSTGRES_DB=instantrisk
POSTGRES_USER=postgres
POSTGRES_PASSWORD=<from Secrets Manager>

REDIS_HOST=instantrisk-redis.mudo3b.0001.use1.cache.amazonaws.com
REDIS_PORT=6379

QDRANT_HOST=instantrisk-qdrant.instantrisk.local
QDRANT_PORT=6333

BEDROCK_ENABLED=true
CLAIMSENSE_ENABLED=true
AWS_DEFAULT_REGION=us-east-1

SECRET_KEY=<from Secrets Manager>
```

### Frontend (Flutter)
```dart
// lib/core/config.dart
static const apiBaseUrl = 'https://instantrisk-alb-307384033.us-east-1.elb.amazonaws.com';
```


## Subscription Tiers

| Feature | TRIAL | BASIC | PREMIUM |
|---------|:-----:|:-----:|:-------:|
| Assessments/month | 5 | 25 | 100 |
| Go/No-Go Decision | ✓ | ✓ | ✓ |
| Confidence Score | - | ✓ | ✓ |
| Underwriting % | - | ✓ | ✓ |
| Sum Insured | - | ✓ | ✓ |
| Risk Analysis | - | - | ✓ |
| ClaimSense Chat | - | - | ✓ |
| Document Gen | - | - | ✓ |
| Deep Analysis | - | - | ✓ |


## Test Users

| Email | Password | Tier |
|-------|----------|------|
| trial.user@test.com | TestPass123 | TRIAL |
| basic.user@test.com | TestPass123 | BASIC |
| premium.user@test.com | TestPass123 | PREMIUM |
| demo@instantrisk.com | Demo2026pass | PREMIUM |


## API Endpoints (36 Routers)

### Core
- `POST /api/v1/auth/login` - User login
- `POST /api/v1/auth/register` - User registration
- `GET /api/v1/health/live` - ALB health check
- `GET /api/v1/subscription` - User subscription info

### Assessments
- `POST /api/v1/assessments` - Create assessment
- `GET /api/v1/assessments` - List assessments
- `GET /api/v1/assessments/{id}` - Get assessment detail
- `POST /api/v1/assessments/{id}/analyze` - Run AI analysis

### ClaimSense
- `GET /api/v1/claimsense/benchmark` - Get benchmarks
- `POST /api/v1/chat` - AI chat with tools

### Documents
- `POST /api/v1/documents/upload` - Upload document
- `GET /api/v1/documents/{id}` - Get document


## Current Status

| Component | Status | Version |
|-----------|--------|---------|
| Backend | ✅ Healthy | v46 |
| Qdrant | ✅ Running | v3 |
| RDS | ✅ Running | PostgreSQL 15 |
| Redis | ✅ Running | 7.x |
| ALB | ✅ Healthy | - |
| Frontend | ⚠️ Needs rebuild | - |


## Next Steps

1. **Download Flutter source from EC2** (in progress)
2. **Fix Flutter Assessment model** (int → String for UUID)
3. **Rebuild Flutter for web**
4. **Deploy to S3/CloudFront**
5. **Set up CodeCommit repositories**
6. **Create CI/CD pipelines**
7. **Document all APIs**
