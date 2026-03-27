# Sprint v3 — PRD: Production-Ready (Testing + CI/CD + Docker + AWS Deployment)

## Overview
Make Paper-to-Notebook production-ready with comprehensive test coverage following
the testing pyramid (70% unit / 20% integration / 10% E2E), a GitHub Actions CI/CD
pipeline that blocks merges on any failure, Docker containerization, and automated
deployment to AWS ECS Fargate. Includes a real quality validation test that generates
a notebook from the TabR1 paper and validates its structure and content.

## Goals
- Testing pyramid fully implemented: ~70% unit, ~20% integration, ~10% E2E
- Real quality test: generate a notebook from TabR1 paper, validate structure (8 sections,
  valid JSON, valid Python, safety disclaimer)
- CI/CD pipeline on GitHub Actions: pytest, Playwright, semgrep, pip-audit — block merge on failure
- Dockerized backend (FastAPI) with docker-compose for local development
- Terraform config for AWS ECS Fargate — auto-deploy on main after tests pass
- AWS credentials stored as GitHub Secrets (never in code)

## User Stories
- As a developer, I want tests to run automatically on every push, so I catch bugs early
- As a developer, I want Docker to run the app locally with one command, so onboarding is instant
- As a user, I want the app deployed on a public URL, so I can access it from anywhere
- As a product owner, I want a quality gate that validates real notebook generation, so I know
  the app produces usable output

## Technical Architecture

### Testing Pyramid
```
           ┌─────────┐
           │  E2E    │  ~10% — Playwright browser tests
           │ (10-15) │  Full user flow with screenshots
           ├─────────┤
           │ Integr. │  ~20% — FastAPI TestClient
           │ (30-40) │  API endpoints, mocked LLM
           ├─────────┤
           │  Unit   │  ~70% — pytest
           │(80-100) │  pdf_extractor, sanitizer,
           │         │  notebook_builder, errors,
           │         │  history, cleanup, pipeline
           └─────────┘
```

### CI/CD Pipeline
```
Push/PR to GitHub
       │
       ▼
┌─────────────────────────────────────────────┐
│          GitHub Actions Workflow             │
│                                              │
│  Job 1: Backend Tests                        │
│  ├── pip install                             │
│  ├── pytest (unit + integration)             │
│  ├── semgrep --config auto app/              │
│  └── pip-audit -r requirements.txt           │
│                                              │
│  Job 2: E2E Tests                            │
│  ├── Start uvicorn server                    │
│  ├── Playwright tests with screenshots       │
│  └── Upload screenshot artifacts             │
│                                              │
│  Job 3: Deploy (only on main, after 1+2)     │
│  ├── Build Docker image                      │
│  ├── Push to ECR                             │
│  └── Update ECS Fargate service              │
└─────────────────────────────────────────────┘
```

### Docker Architecture
```
┌──────────────────────────────────────┐
│  docker-compose.yml                  │
│                                      │
│  ┌────────────────────────────────┐  │
│  │  p2n-app (FastAPI)             │  │
│  │  Port: 8000                    │  │
│  │  Serves: API + static files    │  │
│  │  Image: python:3.11-slim       │  │
│  │  Env: ENV=production           │  │
│  └────────────────────────────────┘  │
│                                      │
│  Volume: ./generated:/app/generated  │
└──────────────────────────────────────┘
```

### AWS ECS Fargate
```
Internet → ALB (HTTPS:443) → ECS Fargate Task → Container (port 8000)
                                  │
                              ECR Image
                              (pushed by CI/CD)
```

## Out of Scope (v4+)
- User authentication (accounts, OAuth)
- Persistent database (PostgreSQL/DynamoDB) for history
- Custom domain + Route53 DNS
- Auto-scaling policies
- Monitoring/alerting (CloudWatch dashboards)
- Multi-region deployment
- CDN (CloudFront) for static assets

## Dependencies
- Sprint v1 + v2 complete (145 tests, 18/20 security findings resolved)
- GitHub repository (to be connected via `gh` CLI)
- AWS account with IAM user `paper-to-notebook-deploy` (keys at local CSV)
- Docker installed locally
- Terraform installed locally
