# Paper-to-Notebook

Transform research papers into production-quality, runnable Google Colab notebooks — powered by OpenAI's gpt-5.4 reasoning model.

Upload a PDF research paper, and get a graduate-level tutorial notebook with step-by-step algorithm breakdowns, equation-to-code mappings, realistic synthetic data, and visualizations.

## Features

- **PDF Upload** — Drag-and-drop or click to upload any research paper (PDF)
- **Multi-Column Support** — Handles two-column layouts (ACM, IEEE, etc.)
- **Research-Grade Notebooks** — Generated code with type hints, docstrings, and modular design
- **Real-Time Progress** — SSE streaming shows what's happening during generation
- **Open in Colab** — One-click to open the generated notebook in Google Colab
- **Generation History** — Session-based history to revisit past notebooks
- **Security Hardened** — Rate limiting, prompt injection protection, code scanning, CSP headers

## Quick Start

### Prerequisites
- Python 3.10+
- An OpenAI API key

### Local Development

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/paper-to-notebook.git
cd paper-to-notebook

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open http://localhost:8000 in your browser.

### Docker

```bash
# Build and run with Docker Compose
docker-compose up --build

# Or build manually
docker build -t paper-to-notebook .
docker run -p 8000:8000 -e ENV=production paper-to-notebook
```

## Testing

### Test Pyramid

| Tier | Count | Coverage |
|------|-------|----------|
| Unit | ~150 | Backend modules, config validation |
| Integration | ~50 | API endpoints, mocked LLM |
| E2E | ~30 | Playwright browser tests |
| Quality | 1 | Real notebook generation (manual) |
| **Total** | **230+** | |

### Running Tests

```bash
# All tests (excluding quality)
pytest tests/ --ignore=tests/fixtures --ignore=tests/quality

# Unit tests only
pytest tests/unit/ -v

# Integration tests only
pytest tests/integration/ -v

# E2E tests (requires server or auto-starts one)
pytest tests/e2e/ -v

# Quality test (requires OpenAI API key, opens visible browser)
OPENAI_API_KEY=your-key-here pytest tests/quality/ -v -s --headed

# Security scans
semgrep --config auto app/
pip-audit -r requirements.txt
```

## CI/CD Pipeline

### Continuous Integration (`.github/workflows/ci.yml`)

Runs on every push and PR to `main`:

1. **Backend Tests** — pytest (unit + integration), semgrep, pip-audit
2. **E2E Tests** — Playwright browser tests with screenshot artifacts

All checks must pass before merge.

### Continuous Deployment (`.github/workflows/deploy.yml`)

Triggers on push to `main` (after CI passes):

1. Configure AWS credentials (from GitHub Secrets)
2. Build Docker image
3. Push to Amazon ECR (tagged with git SHA)
4. Update ECS Fargate service with new task definition
5. Wait for service stability

### Required GitHub Secrets

| Secret | Description |
|--------|-------------|
| `AWS_ACCESS_KEY_ID` | IAM user access key |
| `AWS_SECRET_ACCESS_KEY` | IAM user secret key |

## AWS Deployment

### Architecture

```
Internet → ALB (HTTP/HTTPS) → ECS Fargate → Container (port 8000)
                                    ↑
                               ECR Image
```

### Infrastructure (Terraform)

```bash
cd terraform/

# Initialize
terraform init

# Preview changes
terraform plan

# Deploy
terraform apply
```

**Resources created:**
- VPC with 2 public subnets
- Application Load Balancer with health checks
- ECS Fargate cluster + service (512 CPU, 1024 MiB memory)
- ECR repository with scan-on-push
- CloudWatch log group (14-day retention)
- IAM execution + task roles
- Security groups (ALB: 80/443, ECS: 8000 from ALB)

### HTTPS Setup

1. Request an ACM certificate for your domain
2. Uncomment the HTTPS listener in `terraform/main.tf`
3. Add the certificate ARN
4. Run `terraform apply`

## Security

### Implemented (v2)

| Finding | Fix |
|---------|-----|
| API key in plaintext | Sent via `X-API-Key` header |
| No rate limiting | slowapi: 5/min generate, 20/min upload |
| Prompt injection | Input sanitizer strips delimiter/override patterns |
| Unvalidated code | Output scanner flags 18 dangerous patterns |
| No security headers | 7 headers on every response (CSP, X-Frame, etc.) |
| File cleanup | Background task deletes notebooks after 1 hour |
| Magic byte validation | Checks `%PDF-` before processing |
| CORS wildcards | Restricted to GET/POST, specific headers only |
| Docs exposed | `/docs` disabled when `ENV=production` |

### Open (deferred to v4)

- SEC-002: No user authentication (BYOK model for now)
- SEC-008: No per-user file access control

## Project Structure

```
paper-to-notebook/
├── app/
│   ├── main.py              # FastAPI routes + middleware
│   ├── pdf_extractor.py      # PyMuPDF text extraction
│   ├── llm_generator.py      # OpenAI gpt-5.4 integration
│   ├── notebook_builder.py   # nbformat .ipynb assembly
│   ├── pipeline.py           # SSE streaming orchestrator
│   ├── sanitizer.py          # Prompt injection + code scanner
│   ├── security.py           # Headers, rate limiting
│   ├── errors.py             # Validation + error classes
│   ├── history.py            # Session-based generation history
│   └── cleanup.py            # Background file cleanup
├── static/                   # Frontend (HTML/CSS/JS)
├── terraform/                # AWS ECS Fargate infrastructure
├── .github/workflows/        # CI + CD pipelines
├── tests/                    # 230+ tests
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## License

MIT
