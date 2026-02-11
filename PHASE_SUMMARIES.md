# InstantRisk v2 - Phase Summaries

## Phase 0: Prerequisites + Git Init on EC2 - COMPLETED
- SSH into EC2 (`i-03b49f08fa794a0c9`, 35.169.106.135)
- Backed up and git-initialized code on EC2
- Pushed to GitHub `maansinghsidhu/instantrisk-v2`
- EC2 stack: FastAPI + PostgreSQL 16 + MinIO + Qdrant + Redis (all Docker)
- 30+ routers, Bedrock Claude AI, AutoGen 9-agent pipeline, RAG with 112K+ vectors

## Phase 1: AWS Managed Infrastructure Setup - COMPLETED
- **VPC**: vpc-08f015d31b6f3e27c (10.0.0.0/16), 4 subnets (2 public, 2 private)
- **RDS**: instantrisk-db.cyjui2sqceiw.us-east-1.rds.amazonaws.com (PostgreSQL 16, db.t4g.micro)
- **ElastiCache**: instantrisk-redis.mudo3b.0001.use1.cache.amazonaws.com:6379 (Redis 7)
- **S3**: instantrisk-documents-995306061991, instantrisk-rapidrate-995306061991, instantrisk-frontend-995306061991
- **EFS**: fs-090ad3238b9702fb0 (Qdrant storage)
- **ECR**: instantrisk-backend, instantrisk-qdrant, instantrisk-rapidrate
- **ECS Cluster**: instantrisk (Fargate + Fargate Spot)
- **ALB**: instantrisk-alb-307384033.us-east-1.elb.amazonaws.com
- **Cloud Map**: instantrisk.local (qdrant.instantrisk.local)
- **IAM Roles**: ecs-execution, backend-task, rapidrate-lambda
- **Security Groups**: ALB, Backend, Qdrant, RDS, Redis, EFS

## Phase 2: Data Migration - IN PROGRESS
- Database migrated from EC2 PostgreSQL to RDS via pg_dump/pg_restore
- Qdrant running on EFS with vector data
- Sandbox-01 data export blocked (needs read access to DynamoDB + S3 in account 017853624164)

## Phase 3: Code Changes for Managed Services - COMPLETED
- `config.py`: Updated for RDS, ElastiCache, S3, Qdrant, Bedrock endpoints
- MinIO replaced with S3 (`s3_client.py`)
- All connection strings point to managed services
- Redis URL computed from host/port
- Port changed 8200→8000, environment production

## Phase 4: Database Schema + Benchmark Import - COMPLETED
- Created `loss_run.py` models (BenchmarkLossRun, InsuredLossRun, LossRunSummary)
- Added to `models/__init__.py`
- `seed_benchmark.py` auto-seeds on startup

## Phase 5: Loss Run Upload + Parsing - COMPLETED
- `loss_run_parser.py`: CSV/Excel/PDF parsing via pandas + Bedrock
- `loss_runs.py` router: upload, get, delete, reparse endpoints
- S3 storage for raw files, Qdrant indexing for RAG

## Phase 6: ClaimSense Service - COMPLETED
- `claimsense_service.py`: benchmark queries, insured queries, comparison narratives, NL query
- `claimsense.py` router: benchmark, insured, compare, query endpoints
- Bedrock Claude for NL interpretation and narrative generation

## Phase 7: RapidRate Lambda - COMPLETED
- Lambda `instantrisk-rapidrate` deployed (2048MB, 120s timeout)
- Container image in ECR: predict, simulate (Monte Carlo), price
- XGBoost models loaded from S3 at cold start
- Experience modification factor from insured loss history

## Phase 8: ECS Fargate Deployment - IN PROGRESS
- Merged EC2 backend (30+ routers) with new Fargate features
- Fixed issues discovered during deployment:
  1. Hardcoded `/home/maani` paths → `/app` or `/tmp` (10+ files)
  2. Missing `app/data/clause_service.py` module → created stub
  3. `health.py` wrong import `app.database` → `app.core.database`
  4. Missing `pandas` + `openpyxl` in requirements.txt → added
  5. `create_all` schema mismatch (UUID vs Integer) → wrapped in try/except
  6. `rag_indexer.py` hardcoded path → fixed
- Pre-deployment audit: 0 errors, 0 warnings across 131 Python files
- CodeBuild succeeds, ECR image pushed
- Awaiting service stabilization

## Phase 9: AutoGen + Chat Integration + Bedrock Optimization - PENDING
- Register ClaimSense + RapidRate as AutoGen tools
- Update agent prompts for tool calling
- Haiku for simple agents, Sonnet for complex
- Context summarization, prompt caching, Redis caching

## Phase 10: Flutter Frontend + Testing - PENDING
- Loss run upload UI, assessment results cards
- Flutter build web → S3 → CloudFront

## Phase 11: Cutover + Decommission EC2 - PAUSED
- User requested EC2 stays as backup for now

## Phase 12: CI/CD Pipeline - PENDING
- GitHub Actions for backend, frontend, Lambda

## Phase X: Security & Cyber Risk Assessment - PENDING
- Rate limiting, CORS, input validation, secrets management

---

## Key Infrastructure IDs
| Resource | ID/Endpoint |
|----------|-------------|
| ECS Cluster | instantrisk |
| Backend Service | instantrisk-backend |
| ALB | instantrisk-alb-307384033.us-east-1.elb.amazonaws.com |
| RDS | instantrisk-db.cyjui2sqceiw.us-east-1.rds.amazonaws.com |
| Redis | instantrisk-redis.mudo3b.0001.use1.cache.amazonaws.com:6379 |
| Qdrant | qdrant.instantrisk.local:6333 |
| Lambda | instantrisk-rapidrate |
| S3 Docs | instantrisk-documents-995306061991 |
| S3 RapidRate | instantrisk-rapidrate-995306061991 |
| EC2 | i-03b49f08fa794a0c9 (35.169.106.135) |

## Demo Credentials
- Email: demo@instantrisk.com
- Password: Demo2026pass
