# InstantRisk v2

AI-powered insurance underwriting platform for Lloyd's syndicates.

## Structure

```
instantrisk-v2/
+-- backend/           # FastAPI backend (Python)
|   +-- app/
|   |   +-- routers/   # API routers
|   |   +-- services/  # Business logic services
|   |   +-- models/    # SQLAlchemy models
|   |   +-- schemas/   # Pydantic schemas
|   |   +-- agents/    # AI agents
|   |   +-- ml/        # ML models
|   |   +-- core/      # Config, auth, dependencies
|   +-- alembic/       # Database migrations
|   +-- Dockerfile
|   +-- buildspec.yml  # CodeBuild spec
|   +-- requirements.txt
+-- frontend/          # Flutter web app (Dart)
|   +-- lib/
|   +-- web/
|   +-- pubspec.yaml
+-- infrastructure/    # IaC and task definitions
|   +-- cloudformation/
|   +-- terraform/
|   +-- *-task-definition.json
|   +-- *-policy.json
+-- deploy/            # Deployment scripts
|   +-- deploy_v*.py   # Versioned deploy scripts
|   +-- ops/           # Operational scripts
|   +-- *.json         # Container definitions
+-- lambda/            # Lambda functions (rapidrate)
+-- data/              # Training/seed data
+-- .github/workflows/ # CI/CD pipelines
+-- README.md
```

## AWS Infrastructure

| Service | Resource |
|---------|----------|
| ECS Cluster | instantrisk (Fargate) |
| Backend | ECS service + ALB |
| Qdrant | ECS service (vector DB) |
| ALB | instantrisk-alb |
| RDS | PostgreSQL (instantrisk-db) |
| ElastiCache | Redis (instantrisk-redis) |
| EFS | Qdrant persistent storage |
| ECR | instantrisk-backend, instantrisk-qdrant, instantrisk-rapidrate |
| S3 | Frontend hosting, CodeBuild artifacts |
| CloudFront | Frontend CDN |
| CodeBuild | Backend CI/CD |

## Deployment

- Backend: deploy scripts -> S3 -> CodeBuild -> ECR -> ECS
- Frontend: S3 + CloudFront
- Health check: /api/v1/health/live
