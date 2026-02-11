# InstantRisk Deployment Progress

## Account Information
- **Deployment Account**: 995306061991 (Maani-Sandbox)
- **Source Data Account**: 017853624164 (Sandbox-01)
- **Region**: us-east-1

---

## Phase 1: AWS Managed Infrastructure Setup

### Status: COMPLETED ✓

### VPC & Networking
| Resource | ID/Value | Status |
|----------|----------|--------|
| VPC | vpc-08f015d31b6f3e27c | ✓ Created |
| CIDR | 10.0.0.0/16 | - |
| DNS Support | Enabled | ✓ |
| DNS Hostnames | Enabled | ✓ (Fixed for EFS) |
| Internet Gateway | igw-05969bda156018258 | ✓ Attached |
| NAT Gateway | nat-0c44b343e490a3372 | ✓ Available |
| Elastic IP | eipalloc-092ea69fa37f642de | ✓ Allocated |

### Subnets
| Subnet | ID | CIDR | AZ | Status |
|--------|-----|------|-----|--------|
| Private 1a | subnet-0ccf8263c7fbcdfee | 10.0.1.0/24 | us-east-1a | ✓ |
| Private 1b | subnet-05a356fe8d864e572 | 10.0.2.0/24 | us-east-1b | ✓ |
| Public 1a | subnet-0909af4d3f780c5a9 | 10.0.101.0/24 | us-east-1a | ✓ |
| Public 1b | subnet-0f021d9d61c499696 | 10.0.102.0/24 | us-east-1b | ✓ |

### Route Tables
| Route Table | ID | Type | Status |
|-------------|-----|------|--------|
| Public | rtb-032a20c4b98a0d1a7 | Has IGW route | ✓ |
| Private | rtb-0029097b4fcfe87dd | Has NAT route | ✓ |

### Security Groups
| Security Group | ID | Purpose | Status |
|----------------|-----|---------|--------|
| ALB | sg-0cc12226eadd2a7c0 | Port 80/443 from internet | ✓ |
| Backend | sg-08a3aa7f87aa911ff | Port 8000 from ALB | ✓ |
| Qdrant | sg-0f39e0c5d5c59d5bd | Port 6334 from Backend | ✓ |
| RDS | sg-063a69cb90bf757c1 | Port 5432 from Backend | ✓ |
| Redis | sg-009e1c2ba0d893d35 | Port 6379 from Backend | ✓ |
| EFS | sg-015c6d70b3480c92e | Port 2049 from Qdrant | ✓ |

### RDS PostgreSQL
| Property | Value | Status |
|----------|-------|--------|
| Identifier | instantrisk-db | ✓ |
| Instance Class | db.t4g.micro | - |
| Engine | PostgreSQL 16 | - |
| Storage | 20GB gp3 | - |
| Endpoint | instantrisk-db.cyjui2sqceiw.us-east-1.rds.amazonaws.com | ✓ Available |

### ElastiCache Redis
| Property | Value | Status |
|----------|-------|--------|
| Cluster ID | instantrisk-redis | ✓ |
| Node Type | cache.t4g.micro | - |
| Engine | Redis 7.0.7 | - |
| Endpoint | instantrisk-redis.mudo3b.0001.use1.cache.amazonaws.com:6379 | ✓ Available |

### S3 Buckets
| Bucket | Purpose | Status |
|--------|---------|--------|
| instantrisk-documents-995306061991 | Document storage (versioned, encrypted) | ✓ |
| instantrisk-rapidrate-995306061991 | RapidRate models & data | ✓ |
| instantrisk-frontend-995306061991 | Flutter web static files | ✓ |

### EFS
| Property | Value | Status |
|----------|-------|--------|
| File System ID | fs-090ad3238b9702fb0 | ✓ |
| Mount Target 1a | fsmt-02db18a29f94c24a9 (10.0.1.161) | ✓ |
| Mount Target 1b | fsmt-054ffa28c4a5824b4 (10.0.2.104) | ✓ |

### ECR Repositories
| Repository | URI | Status |
|------------|-----|--------|
| Backend | 995306061991.dkr.ecr.us-east-1.amazonaws.com/instantrisk-backend | ✓ |
| RapidRate | 995306061991.dkr.ecr.us-east-1.amazonaws.com/instantrisk-rapidrate | ✓ |

### ECS Cluster
| Property | Value | Status |
|----------|-------|--------|
| Cluster Name | instantrisk | ✓ |
| Capacity Providers | FARGATE, FARGATE_SPOT | ✓ |
| Container Insights | Enabled | ✓ |

### Service Discovery
| Property | Value | Status |
|----------|-------|--------|
| Namespace | instantrisk.local | ✓ |
| Namespace ID | ns-zhiqrwvimhdnflf7 | ✓ |
| Qdrant Service | srv-y5mtjayvsgg7xuuj | ✓ |

### Application Load Balancer
| Property | Value | Status |
|----------|-------|--------|
| Name | instantrisk-alb | ✓ |
| DNS | instantrisk-alb-307384033.us-east-1.elb.amazonaws.com | ✓ |
| Target Group | instantrisk-backend-tg | ✓ |
| HTTP Listener | Port 80 | ✓ |
| Health Check | /api/v1/health | ✓ |

### IAM Roles
| Role | Purpose | Status |
|------|---------|--------|
| instantrisk-ecs-execution-role | ECS task execution (ECR, CloudWatch, Secrets) | ✓ |
| instantrisk-backend-task-role | Backend permissions (Bedrock, S3, Lambda, Secrets) | ✓ |
| instantrisk-rapidrate-lambda-role | Lambda execution (S3 read, CloudWatch) | ✓ |

### Secrets Manager
| Secret | ARN | Status |
|--------|-----|--------|
| Database | arn:aws:secretsmanager:us-east-1:995306061991:secret:instantrisk/database-3KNa2l | ✓ |

### ECS Services
| Service | Status |
|---------|--------|
| instantrisk-qdrant | ✓ Running |
| instantrisk-backend | Pending (needs Docker image) |

---

## Phase 2: Data Migration

### Status: IN PROGRESS

### Source Data (Sandbox-01)
| Data | Location | Records | Status |
|------|----------|---------|--------|
| ClaimSense Benchmark | DynamoDB: AU_GL_PR_10_Yr_Loss_Run... | 18,466 | Pending (needs read access) |
| RapidRate Models | S3: claim-history-rapidrate/models/ | 3 files | Pending (needs read access) |
| RapidRate CSVs | S3: rapidrate-testing/ | 3 files | Pending (needs read access) |

### Issue
CTOReadOnlyAccess role lacks S3:GetObject and DynamoDB:Scan permissions.
**Need credentials with data read access for Sandbox-01.**

---

## Phase 3: Code Changes for Managed Services

### Status: COMPLETED ✓

### Backend Code Created/Updated
| File | Purpose | Status |
|------|---------|--------|
| `app/config.py` | Settings for RDS, Redis, S3, Qdrant, Bedrock | ✓ |
| `app/database.py` | Async SQLAlchemy session management | ✓ |
| `app/auth.py` | JWT authentication | ✓ |
| `app/main.py` | FastAPI application entry point | ✓ |
| `app/models/base.py` | SQLAlchemy base model | ✓ |
| `app/models/user.py` | User model | ✓ |
| `app/models/assessment.py` | Assessment model | ✓ |
| `app/models/loss_run.py` | Benchmark & Insured loss run models | ✓ |
| `app/services/s3_client.py` | S3 client (replaces MinIO) | ✓ |
| `app/services/bedrock_client.py` | AWS Bedrock Claude client | ✓ |
| `app/services/claimsense_service.py` | Benchmark queries & comparisons | ✓ |
| `app/services/loss_run_parser.py` | PDF/Excel/CSV parsing | ✓ |
| `app/services/rag_indexer.py` | Qdrant vector indexing | ✓ |
| `app/services/autogen_tools.py` | AutoGen tool definitions | ✓ |
| `app/routers/health.py` | ALB health check endpoints | ✓ |
| `app/routers/claimsense.py` | ClaimSense API endpoints | ✓ |
| `app/routers/loss_runs.py` | Loss run upload/parse endpoints | ✓ |

### Lambda Code
| File | Purpose | Status |
|------|---------|--------|
| `lambda/rapidrate/handler.py` | Lambda handler (predict, simulate, price) | ✓ |
| `lambda/rapidrate/monte_carlo.py` | Monte Carlo simulation | ✓ |
| `lambda/rapidrate/models.py` | XGBoost model loading | ✓ |

### Build Files
| File | Purpose | Status |
|------|---------|--------|
| `backend/Dockerfile` | Multi-stage production build | ✓ |
| `backend/requirements.txt` | Python dependencies | ✓ |

---

## Credentials (SENSITIVE)

### Database
- Username: instantrisk_admin
- Password: W8xSpGuFkgiGGaIowLFYrNyy
- Host: instantrisk-db.cyjui2sqceiw.us-east-1.rds.amazonaws.com
- Port: 5432
- Database: instantrisk

### Redis
- Host: instantrisk-redis.mudo3b.0001.use1.cache.amazonaws.com
- Port: 6379

### Qdrant (via Service Discovery)
- Host: qdrant.instantrisk.local
- Port: 6334

---

## Access URLs

| Service | URL |
|---------|-----|
| ALB (API) | http://instantrisk-alb-307384033.us-east-1.elb.amazonaws.com |
| Qdrant (internal) | qdrant.instantrisk.local:6334 |

---

## Current Status Summary

| Phase | Status | Notes |
|-------|--------|-------|
| Phase 0: Git Init | ✓ Completed | (On EC2) |
| Phase 1: Infrastructure | ✓ Completed | All AWS resources created |
| Phase 2: Data Migration | ⏸ Blocked | Needs Sandbox-01 data access |
| Phase 3: Code Changes | ✓ Completed | All backend code written |
| Phase 4-7: Features | ✓ Code Complete | Models, services, routers ready |
| Phase 8: ECS Deployment | 🔄 In Progress | Qdrant running, backend needs image |
| Phase 9-14: Remaining | ⏳ Pending | Depends on above phases |

## Next Steps

### Immediate (Unblocked)
1. **Build and push backend Docker image** - Options:
   - Install Docker locally
   - Use AWS CodeBuild
   - Build on EC2 instance
2. **Register backend ECS task definition** (infrastructure/backend-task-definition.json ready)
3. **Create backend ECS service** targeting ALB
4. **Run Alembic migrations** against RDS

### Blocked on Sandbox-01 Access
- Export ClaimSense benchmark data (18K records from DynamoDB)
- Copy RapidRate XGBoost models (S3)
- Copy RapidRate training CSVs (S3)
**Requirement**: Sandbox-01 (017853624164) credentials with S3:GetObject and DynamoDB:Scan permissions

### After Backend Deployed
- Build and push Lambda image to ECR
- Deploy RapidRate Lambda function
- Configure CloudFront for frontend
- Run E2E tests

---

## Estimated Monthly Cost

| Service | Cost |
|---------|------|
| ECS Fargate (2 services) | ~$30 |
| RDS (db.t4g.micro) | ~$15 |
| ElastiCache (t4g.micro) | ~$12 |
| ALB | ~$18 |
| NAT Gateway | ~$32 |
| S3 + EFS | ~$5 |
| **Total** | **~$112/mo** |

*Note: NAT Gateway is the largest cost. Could optimize by removing for dev or using VPC endpoints.*
