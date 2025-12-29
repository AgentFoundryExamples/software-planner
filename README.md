# Software Planner API

A FastAPI-based software planning service with a modular, extensible architecture.

## 📚 Documentation

- **[Deployment Guide](docs/deployment.md)**: Comprehensive deployment instructions for production environments, scaling guidance, and operational procedures

## Quick Start

### Prerequisites

- Python 3.10 or higher

### Installation

1. Create and activate a virtual environment (recommended):

**On Linux/macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**On Windows (Command Prompt):**
```cmd
python -m venv venv
venv\Scripts\activate.bat
```

**On Windows (PowerShell):**
```powershell
python -m venv venv
venv\Scripts\Activate.ps1
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

> **Note:** If you encounter permission errors when activating scripts on Windows PowerShell, you may need to run: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`

## Deployment

For comprehensive deployment guidance including production configurations, scaling considerations, and operational procedures, see **[docs/deployment.md](docs/deployment.md)**.

The deployment guide covers:
- **Environment Variables Reference**: Complete listing of all configuration options with defaults and contexts
- **Deployment Methods**: Docker, Docker Compose, and container platform deployments (ECS, Heroku, Fly.io, Kubernetes)
- **Scaling Considerations**: Worker configuration, rate limiter tuning, database pooling, and metrics
- **Operational Procedures**: API key rotation, database credential rotation, handling failures, zero-downtime deployments
- **CI/CD Integration**: Workflow overview, artifact promotion, and testing requirements
- **Troubleshooting**: Common issues and solutions

## Docker Deployment

The Software Planner API includes a production-ready Dockerfile for containerized deployments. The image is built using a multi-stage process for minimal size and includes a non-root user for security.

> **📖 For detailed deployment instructions, see [docs/deployment.md](docs/deployment.md)**

### Building the Docker Image

Build the Docker image using the provided Dockerfile:

```bash
docker build -t software-planner:latest .
```

**Build Options:**

```bash
# Build with a specific tag
docker build -t software-planner:v0.1.0 .

# Build for multiple platforms (requires Docker Buildx)
docker buildx build --platform linux/amd64,linux/arm64 -t software-planner:latest .

# Build with SSL certificate bypass for CI environments with SSL interception
# Only use this in CI/CD pipelines with corporate proxies - NOT recommended for production
docker build --build-arg TRUST_PYPI=true -t software-planner:latest .
```

### Running the Container

**Basic Usage:**

```bash
# Run with default configuration (port 8000, 1 worker)
docker run -p 8000:8000 software-planner:latest
```

**Production Configuration with Environment Variables:**

```bash
docker run -d \
  --name software-planner \
  -p 8000:8000 \
  -e PORT=8000 \
  -e WORKERS=4 \
  -e HOST=0.0.0.0 \
  -e LOG_LEVEL=info \
  -e LLM_API_KEY=sk-your-openai-api-key \
  -e LLM_MODEL=gpt-4 \
  -e DATABASE_URL=postgresql+asyncpg://user:password@db:5432/software_planner \
  -e PLANNER_API_KEYS='["key1","key2"]' \
  -e PLANNER_API_KEYS_REQUIRED=true \
  -e PLANNER_RATE_LIMIT_MAX_REQUESTS=100 \
  -e PLANNER_RATE_LIMIT_WINDOW_SECONDS=60 \
  software-planner:latest
```

**Using Environment File:**

For easier management, create a `.env.production` file with your configuration:

```bash
# .env.production (NEVER commit this file with real secrets!)
PORT=8000
WORKERS=4
HOST=0.0.0.0
LOG_LEVEL=info

# LLM Configuration
LLM_API_KEY=sk-your-actual-openai-api-key
LLM_MODEL=gpt-4
LLM_TIMEOUT=90

# Database Configuration
DATABASE_URL=postgresql+asyncpg://user:password@db.example.com:5432/software_planner

# API Authentication
PLANNER_API_KEYS=["your-secure-key-1","your-secure-key-2"]
PLANNER_API_KEYS_REQUIRED=true

# Rate Limiting
PLANNER_RATE_LIMIT_MAX_REQUESTS=100
PLANNER_RATE_LIMIT_WINDOW_SECONDS=60

# CORS (Production - specific origins only)
ALLOWED_ORIGINS=["https://app.example.com","https://admin.example.com"]
CORS_WILDCARD_ENABLED=false

# Metrics
PLANNER_METRICS_ENABLED=true
```

Then run with the environment file:

```bash
docker run -d \
  --name software-planner \
  -p 8000:8000 \
  --env-file .env.production \
  software-planner:latest
```

### Essential Environment Variables

The container is configured entirely through environment variables. **No secrets are hardcoded.**

**Required for Production:**

- `LLM_API_KEY` - OpenAI API key (get from https://platform.openai.com/api-keys)
- `DATABASE_URL` - PostgreSQL connection string (format: `postgresql+asyncpg://user:pass@host:port/db`)
- `PLANNER_API_KEYS` - JSON array or comma-separated list of API keys for authentication

**Optional Configuration:**

- `PORT` - Server port (default: 8000)
- `WORKERS` - Number of uvicorn workers (default: 1, recommended: number of CPU cores)
- `HOST` - Server host (default: 0.0.0.0)
- `LOG_LEVEL` - Logging level: debug, info, warning, error, critical (default: info)
- `LLM_MODEL` - OpenAI model identifier (default: gpt-4)
- `LLM_TIMEOUT` - LLM request timeout in seconds (default: 60)
- `PLANNER_RATE_LIMIT_MAX_REQUESTS` - Rate limit per window (default: 10)
- `PLANNER_RATE_LIMIT_WINDOW_SECONDS` - Rate limit window in seconds (default: 60)
- `PLANNER_METRICS_ENABLED` - Enable Prometheus metrics (default: false)
- `ALLOWED_ORIGINS` - CORS allowed origins JSON array (default: ["*"])
- `DEBUG` - Enable debug mode (default: false, **never enable in production**)

See `.env.example` for a complete list of configuration options with detailed descriptions.

## Docker Compose Setup (Recommended for Local Development)

The Software Planner includes a production-ready `docker-compose.yml` configuration that provides:
- **PostgreSQL 17 database** with persistent storage and health checks
- **API service** with automatic database migrations
- **Proper networking** and service dependencies
- **Volume persistence** for database data across restarts
- **Configurable ports** to avoid conflicts

### Quick Start with Docker Compose

**1. Prerequisites:**
- Docker Engine 20.10+ and Docker Compose 2.0+
- At least 2GB RAM available for containers
- OpenAI API key (or other LLM provider key)

**2. Setup:**

```bash
# Clone the repository (if not already done)
git clone https://github.com/your-org/software-planner.git
cd software-planner

# Copy environment file and configure
cp .env.example .env

# Edit .env and set required variables (at minimum):
# - LLM_API_KEY=sk-your-openai-api-key
# Optional: Customize DATABASE_PASSWORD, PORT, etc.
```

**3. Start Services:**

```bash
# Start all services (API + database)
make compose-up

# Or use docker compose directly:
docker compose up -d
```

The `compose-up` command will:
1. Create a `.env` file from `.env.example` if it doesn't exist
2. Pull/build the required Docker images
3. Start PostgreSQL database with health checks
4. Wait for database to be ready
5. Run database migrations automatically
6. Start the API service
7. Display access URLs and helpful commands

**4. Verify Services:**

```bash
# Check health endpoint
curl http://localhost:8000/health
# Expected: {"status":"ok"}

# View service logs
make compose-logs

# Or view specific service logs:
docker compose logs -f app
docker compose logs -f db
```

**5. Access the API:**

- **API Base URL**: http://localhost:8000
- **Interactive Docs**: http://localhost:8000/api/v1/docs
- **Health Check**: http://localhost:8000/health
- **Planning Endpoint**: http://localhost:8000/api/v1/plans

### Docker Compose Commands Reference

The Makefile provides convenient commands for managing the Docker Compose stack:

```bash
# Start services
make compose-up              # Start all services in detached mode

# View logs
make compose-logs            # Follow logs from all services (CTRL+C to exit)

# Stop services
make compose-down            # Stop all services (preserves data)

# Restart services
make compose-restart         # Restart all services without rebuilding

# Rebuild containers
make compose-build           # Rebuild images from scratch (no cache)

# Run migrations
make compose-migrate         # Run database migrations in running container

# Clean up (WARNING: deletes data!)
make compose-clean           # Stop services and remove volumes
```

### Configuration via .env File

Docker Compose reads configuration from `.env` file in the project root. Key variables:

```bash
# Required - LLM Configuration
LLM_API_KEY=sk-your-openai-api-key-here
LLM_MODEL=gpt-4

# Database Configuration (defaults are fine for development)
DATABASE_USER=planner
DATABASE_PASSWORD=planner_dev_password
DATABASE_NAME=software_planner
DATABASE_PORT=5432              # Host port (change if 5432 is in use)

# API Configuration
PORT=8000                       # Host port (change if 8000 is in use)
WORKERS=1                       # Number of API workers
DEBUG=false                     # Enable debug mode (development only)

# Optional - API Authentication
PLANNER_API_KEYS=["dev-key-123"]
PLANNER_API_KEYS_REQUIRED=false

# Optional - Rate Limiting
PLANNER_RATE_LIMIT_MAX_REQUESTS=10
PLANNER_RATE_LIMIT_WINDOW_SECONDS=60

# Optional - CORS (development defaults)
ALLOWED_ORIGINS=["*"]
CORS_WILDCARD_ENABLED=true
```

**Security Note for Production:**
- Set strong `DATABASE_PASSWORD`
- Configure `PLANNER_API_KEYS` with secure random keys
- Set `PLANNER_API_KEYS_REQUIRED=true`
- Set `CORS_WILDCARD_ENABLED=false`
- Specify exact domains in `ALLOWED_ORIGINS`

### Running Database Migrations

Migrations are run automatically when starting the API service. To run migrations manually:

```bash
# Run migrations in the running container
make compose-migrate

# Or use docker compose directly:
docker compose exec app alembic upgrade head

# Check migration status
docker compose exec app alembic current

# View migration history
docker compose exec app alembic history
```

### Seeding Test Jobs

You can create test planning jobs using the API:

```bash
# Create a test job (no API key required in default dev setup)
curl -X POST http://localhost:8000/api/v1/plans \
  -H "Content-Type: application/json" \
  -d '{"description": "Build a REST API for managing tasks"}'

# Response will include job_id:
# {"job_id":"550e8400-e29b-41d4-a716-446655440000","status":"pending"}

# Check job status
curl http://localhost:8000/api/v1/plans/550e8400-e29b-41d4-a716-446655440000

# List all jobs
curl http://localhost:8000/api/v1/plans
```

### Port Conflicts and Customization

If default ports are already in use, customize via `.env`:

```bash
# Use different database port
DATABASE_PORT=5433

# Use different API port  
PORT=8080

# Restart services to apply changes
make compose-down
make compose-up
```

Services will be available at:
- API: http://localhost:8080
- Database: localhost:5433

### Volume Management and Data Persistence

Docker Compose uses named volumes for data persistence:

- **postgres_data**: PostgreSQL database files
- Volume name: `software-planner-db-data`
- Location: Managed by Docker (typically `/var/lib/docker/volumes/`)

**View volumes:**
```bash
docker volume ls | grep software-planner
```

**Inspect volume:**
```bash
docker volume inspect software-planner-db-data
```

**Backup database data:**
```bash
# Backup to SQL dump
docker compose exec db pg_dump -U planner software_planner > backup.sql

# Restore from backup
docker compose exec -T db psql -U planner software_planner < backup.sql
```

**Clean up volumes (WARNING: deletes all data!):**
```bash
# Stop services and remove volumes
make compose-clean

# Or use docker compose directly:
docker compose down -v

# Remove named volume manually if needed:
docker volume rm software-planner-db-data
```

**Reset state for migration changes:**
If you need to reset the database after schema changes:
```bash
# Stop services and remove volumes
make compose-clean

# Start fresh (will run migrations on empty database)
make compose-up
```

### Troubleshooting Docker Compose

**Issue: Services won't start**

Check logs for errors:
```bash
make compose-logs

# Or check specific service:
docker compose logs db
docker compose logs app
```

**Issue: Database connection failed**

1. Verify database is healthy:
```bash
docker compose ps
# Status should show "healthy" for db service
```

2. Check database logs:
```bash
docker compose logs db
```

3. Test database connection:
```bash
docker compose exec db pg_isready -U planner
```

**Issue: Port already in use**

Change ports in `.env`:
```bash
PORT=8080
DATABASE_PORT=5433
```

Then restart:
```bash
make compose-down
make compose-up
```

**Issue: Migrations fail**

1. Check migration status:
```bash
docker compose exec app alembic current
```

2. View database tables:
```bash
docker compose exec db psql -U planner -d software_planner -c "\dt"
```

3. Reset database if needed:
```bash
make compose-clean
make compose-up
```

**Issue: API service keeps restarting**

1. Check for missing LLM_API_KEY:
```bash
docker compose logs app | grep "LLM_API_KEY"
```

2. Verify .env file exists and is valid:
```bash
cat .env | grep LLM_API_KEY
```

3. Check container health:
```bash
docker compose ps
# Health should transition from "starting" to "healthy"
```

**Issue: Changes to code not reflected**

Rebuild containers:
```bash
make compose-build
make compose-up
```

**Issue: Database data not persisting**

Verify volume is being used:
```bash
docker volume ls | grep software-planner
docker volume inspect software-planner-db-data
```

### Container Security Best Practices

The Dockerfile follows security best practices:

1. **Multi-stage Build**: Separates build dependencies from runtime, reducing attack surface
2. **Slim Base Image**: Uses `python:3.11-slim` for minimal size (~150MB vs 1GB+ for full image)
3. **Non-root User**: Runs as user `appuser` (UID 1000) instead of root
4. **No Secrets in Image**: All configuration via environment variables, no hardcoded secrets
5. **Minimal Dependencies**: Only installs required runtime system packages
6. **Health Check**: Built-in health check endpoint for container orchestration
7. **Dependency Pinning**: Uses `requirements.txt` with pinned versions for reproducible builds

### Health Checks and Readiness

The container includes a built-in health check that verifies the `/health` endpoint:

```bash
# Check container health
docker ps --filter name=software-planner

# Manually test health endpoint
curl http://localhost:8000/health
```

For Kubernetes deployments, configure liveness and readiness probes:

```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 3

readinessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 5
  timeoutSeconds: 3
  failureThreshold: 3
```

### Troubleshooting Container Issues

**Container fails to start:**

Check logs for configuration errors:
```bash
docker logs software-planner
```

**Database connection failed:**
- Verify `DATABASE_URL` is correctly formatted
- Ensure PostgreSQL is accessible from container
- Check network connectivity: `docker exec software-planner ping db`
- Run migrations: `docker exec software-planner alembic upgrade head`

**LLM authentication failed:**
- Verify `LLM_API_KEY` is set and starts with "sk-"
- Check key is valid at https://platform.openai.com/api-keys
- Ensure no extra whitespace in environment variable

**Permission errors:**
- Container runs as non-root user (UID 1000)
- If mounting volumes, ensure proper permissions: `chown -R 1000:1000 /path/to/volume`

**Port already in use:**
- Change host port: `docker run -p 8080:8000 software-planner:latest`
- Stop conflicting container: `docker ps -a | grep 8000`

### Production Deployment Considerations

**Worker Configuration:**
- Set `WORKERS` to number of CPU cores for CPU-bound workloads
- For I/O-bound workloads (typical for this API), 2-4 workers per core is acceptable
- Monitor memory usage and adjust accordingly
- Single worker is fine for low-traffic deployments

**Resource Limits:**
```bash
# Run with memory and CPU limits
docker run -d \
  --name software-planner \
  --memory=512m \
  --cpus=1.0 \
  -p 8000:8000 \
  --env-file .env.production \
  software-planner:latest
```

**Log Management:**
- Container logs to stdout/stderr for 12-factor app compliance
- Collect logs with Docker logging drivers or external log aggregator
- Configure log rotation to prevent disk space issues

**Orchestration:**
- Use Docker Swarm, Kubernetes, or ECS for production deployments
- Configure auto-scaling based on CPU/memory metrics
- Set up rolling updates for zero-downtime deployments
- Use secrets management (Docker secrets, Kubernetes secrets, AWS Secrets Manager)

## Development

This project uses standardized tooling for code quality, formatting, and type checking. All development dependencies are included in `requirements.txt`.

### Installing Development Dependencies

Development tools (black, isort, flake8, mypy, coverage) are included in the main requirements file. After installing dependencies as shown above, you'll have all the tools needed for development.

```bash
# Install all dependencies (including dev tools)
pip install -r requirements.txt
```

**Note on `requirements-lock.txt`:**
- `requirements-lock.txt` contains frozen versions generated from `requirements.txt`
- Used by CI and Docker builds for reproducible environments
- **To regenerate the lockfile properly:**
  1. Create a clean virtual environment: `python3 -m venv .venv-clean`
  2. Activate it: `source .venv-clean/bin/activate`
  3. Upgrade pip: `pip install --upgrade pip`
  4. Install from requirements.txt: `pip install -r requirements.txt`
  5. Freeze to lockfile: `pip freeze > requirements-lock.txt`
  6. Deactivate and cleanup: `deactivate && rm -rf .venv-clean`
- **Important:** Never regenerate from an environment with system packages installed. System packages (like `bcc`, `cloud-init`, `python-apt`) often have version strings with `+` symbols (e.g., `2.7.7+ubuntu5`) or are Linux-specific - these aren't on PyPI and will cause CI failures.
  - Always use a clean virtual environment as shown above
  - If you see packages with `+` in version numbers after `pip freeze`, you're in an environment with system packages

### Development Commands

The project includes a `Makefile` with convenient commands for development. All commands are designed to work consistently across local development and CI environments.

**Code Quality:**
```bash
make lint           # Run all linters (flake8, black --check, isort --check)
make format         # Auto-format code with black and isort
make type-check     # Run mypy type checker
```

**Testing:**
```bash
make test           # Run pytest tests
make test-coverage  # Run tests with coverage report
```

**Combined Workflows:**
```bash
make all            # Run lint, type-check, and test in sequence
make dev            # Format code, then run all checks and tests
```

**Utilities:**
```bash
make clean          # Remove build artifacts and cache files
make help           # Show all available commands
```

### Code Quality Standards

The project enforces consistent code quality through:

- **Black** (v24.10.0): Code formatter with 100-character line length
- **isort** (v5.13.2): Import statement organizer compatible with Black
- **flake8** (v7.1.1): Linting for code quality and style
- **mypy** (v1.13.0): Static type checking for Python

Configuration for all tools is centralized in `pyproject.toml` and `.flake8`.

### Type Checking Notes

The project uses mypy for type checking with lenient settings to accommodate the current codebase state. Type checking is currently **informational only** and does not block CI or development workflows.

Third-party libraries that lack type stubs (e.g., anthropic, google-genai, openai) have `ignore_missing_imports = true` configured to prevent failures due to missing type definitions.

**Gradual Type Safety Roadmap:**
- Current: Mypy runs with lenient settings to establish baseline
- Future: Gradually enable stricter type checking as type annotations improve
- Goal: Full strict type checking with minimal ignores

To see type checking results without blocking your workflow:
```bash
make type-check
```

### Pre-Commit Workflow

Before committing code, run:
```bash
make dev
```

This will:
1. Format your code with black and isort
2. Run linting checks (flake8, black --check, isort --check)
3. Run type checking with mypy
4. Run all tests

All steps must pass for the command to succeed (fail-fast behavior with non-zero exit codes).

### Running the Application

Start the development server:
```bash
uvicorn app.main:app --reload
```

Or run directly:
```bash
python -m app.main
```

The API will be available at:
- Main API: http://localhost:8000
- Interactive docs: http://localhost:8000/api/v1/docs
- Health check: http://localhost:8000/health
- Planning endpoint: http://localhost:8000/api/v1/plan
- Async planning endpoint: http://localhost:8000/api/v1/plans

### API Endpoints

The API provides both synchronous and asynchronous planning endpoints. The asynchronous endpoints (POST /api/v1/plans) are recommended for production use as they allow long-running planning operations without blocking the client.

#### GET /health

Returns the health status of the API.

**Example using curl:**
```bash
curl http://localhost:8000/health
```

**Response:**
```json
{
  "status": "ok"
}
```

#### GET /api/v1/models

Discover available LLM models with their metadata and constraints.

**Purpose:**
This discovery endpoint allows clients to:
- See which models are currently enabled and available
- Understand model constraints (timeout limits, context windows, retries)
- Validate model names before submitting planning jobs
- Choose appropriate models based on requirements

**Example using curl:**
```bash
curl http://localhost:8000/api/v1/models
```

**Response:**
```json
{
  "models": [
    {
      "logical_name": "my-gpt-model",
      "provider": "openai",
      "model_id": "gpt-5.1",
      "enabled": true,
      "timeout": 60,
      "max_retries": 3,
      "description": "OpenAI gpt-5.1 - Latest generation model with improved reasoning and performance",
      "metadata": {
        "approximate_max_context": 128000,
        "supports_streaming": false
      }
    },
    {
      "logical_name": "my-claude-model",
      "provider": "anthropic",
      "model_id": "claude-sonnet-4.5",
      "enabled": true,
      "timeout": 90,
      "max_retries": 5,
      "description": "Anthropic claude-sonnet-4.5 - Balanced performance and speed for most tasks",
      "metadata": {
        "approximate_max_context": 200000,
        "supports_streaming": false
      }
    }
  ]
}
```

**Response Fields:**
- `logical_name`: The identifier to use when selecting this model in planning requests
- `provider`: Backend provider (openai, anthropic, google)
- `model_id`: Provider-specific model identifier
- `enabled`: Whether the model is currently available (only enabled models are returned)
- `timeout`: Request timeout in seconds - expect responses within this time
- `max_retries`: Maximum automatic retry attempts for transient failures
- `description`: Human-readable description of the model
- `metadata.approximate_max_context`: Approximate token limit for context window
- `metadata.supports_streaming`: Whether streaming responses are supported (currently always false)

**Empty Registry:**
If no models are configured or all models are disabled, returns an empty list:
```json
{
  "models": []
}
```

**Usage Pattern:**
1. Call `GET /api/v1/models` to discover available models
2. Review model constraints (timeout, context limits)
3. Select appropriate model based on your requirements
4. Include `model` field in your planning request (see "Selecting a Model" below)

#### Selecting a Model for Planning

Both the synchronous (`POST /api/v1/plan`) and asynchronous (`POST /api/v1/plans`) endpoints support model selection via the request body.

**Default Behavior:**
If you don't specify a model, the system uses the configured default model. To see which model is the default, call `GET /api/v1/models` and look for common characteristics (typically the first listed model or one with lower timeout).

**Specifying a Model:**

Include the `model` field in your request body with the logical name from `GET /api/v1/models`:

```bash
curl -X POST http://localhost:8000/api/v1/plans \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Build a REST API for managing tasks",
    "model": "my-claude-model"
  }'
```

**Custom System Prompt (Advanced):**

You can also override the default system prompt. This is for advanced users who understand prompt engineering:

```bash
curl -X POST http://localhost:8000/api/v1/plans \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Build a REST API for managing tasks",
    "model": "my-gpt-model",
    "system_prompt": "You are an expert software architect. Generate detailed technical specifications..."
  }'
```

**Important:** JSON mode is enforced at the provider level regardless of custom system prompts. The API will always return structured JSON even if a custom prompt attempts to disable formatting. This guarantees reliable plan storage and parsing.

**Validation:**
- If you specify an unknown model name, you'll get a 400 Bad Request error listing available models
- If you specify a disabled model, you'll get a 400 Bad Request error
- System prompts must not exceed 32768 bytes
- Models must support JSON mode enforcement (all configured models in MODELS_REGISTRY are verified compatible)

**Viewing Model Used in Job Results:**

When you retrieve a job via `GET /api/v1/plans/{job_id}`, the response includes which model was used:

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "succeeded",
  "model": "my-claude-model",
  "system_prompt_hash": "a7b3c...",
  "created_at": "2025-01-01T12:00:00Z",
  "updated_at": "2025-01-01T12:00:05Z",
  "result": {
    "specs": [...]
  }
}
```

**Fields:**
- `model`: The logical model name that was used (null if default was used with legacy configuration)
- `system_prompt_hash`: SHA-256 hash of the system prompt (only present if custom prompt was provided)

**Backward Compatibility:**

The model selection feature is fully backward compatible:
- If you don't specify a model, the default is used
- Legacy single-model configuration (using `LLM_API_KEY` and `LLM_MODEL`) still works
- Existing API requests without `model` field continue to work unchanged
- The `model` and `system_prompt_hash` fields in responses are optional and may be null

#### POST /api/v1/plan

Generate a software plan based on a project description (synchronous).

> **Note:** This is the synchronous endpoint that blocks until planning completes. For production use or long-running operations, consider using the asynchronous POST /api/v1/plans endpoint instead.

**Example using curl:**
```bash
curl -X POST http://localhost:8000/api/v1/plan \
  -H "Content-Type: application/json" \
  -d '{"description": "Build a REST API for managing tasks"}'
```

> **Note:** When using curl on Windows Command Prompt, use double quotes for JSON and escape inner quotes:
> ```cmd
> curl -X POST http://localhost:8000/api/v1/plan -H "Content-Type: application/json" -d "{\"description\": \"Build a REST API for managing tasks\"}"
> ```

**Request Body:**
```json
{
  "description": "Build a REST API for managing tasks"
}
```

**Validation:**
- `description` must be a non-empty string
- `description` cannot be whitespace-only
- `description` must not exceed 8192 bytes (UTF-8 encoded)

**Success Response (200 OK):**
```json
{
  "specs": [
    {
      "purpose": "Core API Development",
      "vision": "Build a robust and scalable REST API with proper error handling and validation",
      "must": [
        "Implement RESTful endpoints with proper HTTP methods",
        "Add comprehensive input validation",
        "Include error handling with informative messages",
        "Write unit and integration tests"
      ],
      "dont": [
        "Skip validation on user inputs",
        "Expose internal error details to clients",
        "Hardcode configuration values",
        "Ignore security best practices"
      ],
      "nice": [
        "Add API rate limiting",
        "Include request/response logging",
        "Implement API versioning",
        "Add OpenAPI documentation"
      ],
      "assumptions": [
        "Using a relational database for data persistence",
        "RESTful API conventions will be followed",
        "Application will be deployed in a containerized environment"
      ],
      "open_questions": [
        "What authentication method should be used (OAuth2, JWT, API keys)?",
        "Should the API support pagination from the start?",
        "What rate limiting strategy is preferred?"
      ]
    }
  ]
}
```

**Note:** The `assumptions` and `open_questions` fields are optional. If the LLM does not include them in its response, they will default to empty arrays. These fields provide additional context about the specification:
- `assumptions`: Lists any assumptions made about ambiguous or unclear aspects of the project description
- `open_questions`: Lists clarifying questions that could help refine the requirements if answered


**Error Responses:**
- `400 Bad Request`: Empty, whitespace-only, or oversized description
- `422 Unprocessable Entity`: Malformed JSON or missing required fields

### Asynchronous Planning Workflow

The asynchronous planning endpoints allow you to submit long-running planning jobs and poll for results without blocking your client. This is the recommended approach over the synchronous endpoint.

> **Note:** Jobs are stored in a PostgreSQL database and persist across server restarts. See the "Database Setup" section for configuration instructions.

#### Step-by-Step Usage

**1. Create a Planning Job**

Submit a planning request using POST /api/v1/plans:

```bash
curl -X POST http://localhost:8000/api/v1/plans \
  -H "Content-Type: application/json" \
  -d '{"description": "Build a REST API for managing tasks"}'
```

Response (HTTP 202 Accepted):
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending"
}
```

The server returns immediately with a unique `job_id`. Save this ID for polling.

**2. Poll for Job Status**

Use GET /api/v1/plans/{job_id} to check the job status:

```bash
curl http://localhost:8000/api/v1/plans/550e8400-e29b-41d4-a716-446655440000
```

**3. Interpret Job Status**

The job progresses through these states:

**Pending Job** (just created, not yet started):
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "created_at": "2025-01-01T12:00:00Z",
  "updated_at": "2025-01-01T12:00:00Z",
  "result": null
}
```

**Running Job** (currently executing):
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "running",
  "created_at": "2025-01-01T12:00:00Z",
  "updated_at": "2025-01-01T12:00:02Z",
  "result": null
}
```

**Succeeded Job** (planning completed successfully):
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "succeeded",
  "created_at": "2025-01-01T12:00:00Z",
  "updated_at": "2025-01-01T12:00:05Z",
  "result": {
    "specs": [
      {
        "purpose": "Core API Development",
        "vision": "Build a robust REST API",
        "must": ["Implement endpoints"],
        "dont": ["Skip validation"],
        "nice": ["Add rate limiting"],
        "assumptions": ["Using PostgreSQL database"],
        "open_questions": ["What authentication method to use?"]
      }
    ]
  }
}
```

**Failed Job** (planning encountered an error):
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "failed",
  "created_at": "2025-01-01T12:00:00Z",
  "updated_at": "2025-01-01T12:00:05Z",
  "result": null,
  "error": {
    "error": "Planning failed",
    "type": "ValueError"
  }
}
```

**Job Not Found** (invalid job_id or job expired):
```json
{
  "error": "Job not found",
  "status_code": 404
}
```

#### HTTP Status Codes

- **202 Accepted**: Job created successfully (POST /plans)
- **200 OK**: Job metadata retrieved (GET /plans/{job_id}, regardless of job status)
- **404 Not Found**: Job does not exist or has expired
- **400 Bad Request**: Invalid request (empty/oversized description)
- **422 Unprocessable Entity**: Malformed JSON or missing required fields

#### Known Limitations

**⚠️ Important Constraints:**

1. **Database Required**: Jobs require a PostgreSQL database for persistence. See the "Database Setup" section for configuration instructions. Without a database, the application will fail to start.

2. **No Cancellation**: Once a job is created, it cannot be cancelled. It will run to completion (succeeded or failed state).

3. **Background Processing**: Jobs are processed asynchronously in the background. Long-running jobs may be interrupted if the server is restarted before completion.

#### Polling Strategy

For best results when polling:
- Start polling immediately after job creation
- Use an exponential backoff strategy (e.g., 1s, 2s, 4s, 8s intervals)
- Stop polling when status is `succeeded` or `failed`
- Handle 404 errors gracefully (job may have expired)

#### Debug Endpoints

**GET /api/v1/plans** (List All Jobs)

This debug endpoint lists all jobs currently in memory:

```bash
# List all jobs
curl http://localhost:8000/api/v1/plans

# List with custom limit
curl "http://localhost:8000/api/v1/plans?limit=10"
```

Response:
```json
{
  "jobs": [
    {
      "job_id": "550e8400-e29b-41d4-a716-446655440000",
      "status": "succeeded",
      "created_at": "2025-01-01T12:00:00Z",
      "updated_at": "2025-01-01T12:00:05Z",
      "result": {
        "specs": [
          {
            "purpose": "Core API Development",
            "vision": "Build a robust REST API",
            "must": ["Implement endpoints"],
            "dont": ["Skip validation"],
            "nice": ["Add rate limiting"]
          }
        ]
      }
    }
  ],
  "total": 1,
  "limit": 100
}
```

**Note:** This endpoint is intended for debugging and monitoring only. Jobs are returned in most-recently-updated order.

### Job Lifecycle and Persistence

Understanding the job lifecycle is crucial for operations, monitoring, and troubleshooting. This section describes the states jobs transition through, how restarts are handled, and how to inspect job records.

#### Job Status States

Jobs progress through the following states during their lifecycle:

```
QUEUED → RUNNING → SUCCEEDED
                 ↘ FAILED
```

**State Definitions:**

1. **QUEUED** (Initial State)
   - Job has been created and persisted to the database
   - Job is waiting for a background worker to pick it up
   - `created_at` timestamp is set
   - `started_at` and `finished_at` are NULL

2. **RUNNING** (Processing State)
   - Background worker has claimed the job and is executing the LLM request
   - `started_at` timestamp is set when transitioning to this state
   - Job is actively calling the LLM API and processing results
   - If server restarts while job is RUNNING, it will be marked as FAILED (see "Restart Recovery" below)

3. **SUCCEEDED** (Terminal State)
   - Planning completed successfully
   - `result` field contains the generated specifications
   - `finished_at` timestamp records completion time
   - Job will not be processed again

4. **FAILED** (Terminal State)
   - Planning encountered an error (LLM failure, timeout, validation error, or restart recovery)
   - `error` field contains error details with `error` and `type` fields
   - `finished_at` timestamp records when failure was detected
   - Job will not be retried automatically

**Valid Transitions:**
- `QUEUED → RUNNING` - Background worker starts processing
- `RUNNING → SUCCEEDED` - Planning completes successfully
- `RUNNING → FAILED` - Planning encounters an error
- `QUEUED → FAILED` - Rare edge case, used during restart recovery

**Invalid Transitions:**
These transitions are prevented by the repository layer:
- Cannot transition from terminal states (SUCCEEDED, FAILED) to any other state
- Cannot mark a QUEUED job as SUCCEEDED without going through RUNNING
- Cannot transition backwards in the lifecycle

#### Restart Recovery and Behavior

**What Happens on Server Restart:**

When the application starts up, it automatically runs a recovery process to handle jobs that were interrupted by the previous shutdown:

1. **Startup Recovery Process** (runs in `startup_event` in `app/main.py`):
   - Queries database for all jobs in `RUNNING` state
   - Marks them as `FAILED` with error type `RestartRecoveryError`
   - Sets error message: "Job interrupted by server restart"
   - Sets `finished_at` timestamp to the current time
   - Logs a warning with count of recovered jobs

2. **Why Jobs Are Marked as Failed:**
   - Jobs in RUNNING state were actively processing when server stopped
   - LLM requests may have been interrupted mid-flight
   - No way to resume partial work or determine actual completion state
   - Marking as FAILED provides clear signal to operators that these jobs need attention

3. **Expected Log Messages:**
   ```
   WARNING: Startup recovery completed: 5 jobs marked as FAILED
   ```
   Or if no stuck jobs:
   ```
   INFO: No stuck jobs found during startup recovery
   ```

**Restart Semantics:**
- **QUEUED jobs** - Preserved and will be processed normally after restart
- **RUNNING jobs** - Automatically marked as FAILED with restart recovery error
- **SUCCEEDED jobs** - Preserved unchanged
- **FAILED jobs** - Preserved unchanged

**Operational Implications:**
- Users whose jobs were in RUNNING state during restart will see `status: "failed"` with restart recovery error
- These jobs must be manually resubmitted if the planning results are still needed
- Monitor the startup logs to understand how many jobs were affected by a restart
- Consider graceful shutdown procedures for production deployments (see "Production Considerations" below)

#### Database Unreachability at Startup

**What Happens if Database is Unavailable:**

The application **will fail to start** if it cannot connect to the database. This fail-fast behavior is intentional to prevent the application from running in a degraded state.

**Expected Behavior:**
1. Application attempts to initialize the database connection pool
2. If connection fails, the connection module logs detailed error information
3. Application exits with a non-zero exit code
4. Orchestration system (Docker, Kubernetes, systemd) can detect failure and restart

**Error Logs to Expect:**
```
ERROR: Database connection failed: could not connect to server: Connection refused
ERROR: Please verify database configuration and ensure PostgreSQL is running
ERROR: DATABASE_URL=postgresql+asyncpg://user@localhost:5432/software_planner
```

**Troubleshooting Steps:**
1. Verify PostgreSQL is running: `pg_isready -h localhost -p 5432`
2. Check database connection settings in environment variables or `.env`
3. Verify network connectivity: `telnet db.example.com 5432`
4. Check PostgreSQL logs for authentication or permission errors
5. Verify database and user exist: `psql -U postgres -l`
6. Check firewall rules if connecting to remote database

**Production Recommendations:**
- Use health checks in orchestration systems to detect startup failures
- Implement retry logic at the orchestration level (e.g., Kubernetes restart policy)
- Set up monitoring alerts for repeated startup failures
- Ensure database is started before application in dependency management

#### Verifying Job Persistence

**SQL Queries for Debugging and Monitoring:**

1. **Check Total Job Count by Status:**
```sql
SELECT status, COUNT(*) as count
FROM jobs
GROUP BY status
ORDER BY status;
```

2. **Find Recently Created Jobs:**
```sql
SELECT job_id, status, created_at, updated_at
FROM jobs
ORDER BY created_at DESC
LIMIT 10;
```

3. **Find Jobs Stuck in RUNNING State:**
```sql
-- These should be 0 unless actively processing
-- If non-zero after restart, recovery process failed
SELECT job_id, started_at, description
FROM jobs
WHERE status = 'RUNNING'
ORDER BY started_at DESC;
```

4. **Find Jobs That Failed Due to Restart:**
```sql
SELECT job_id, created_at, finished_at, error
FROM jobs
WHERE status = 'FAILED'
  AND error->>'type' = 'RestartRecoveryError'
ORDER BY finished_at DESC;
```

5. **Check Average Processing Time for Successful Jobs:**
```sql
SELECT 
    AVG(EXTRACT(EPOCH FROM (finished_at - started_at))) as avg_seconds,
    MIN(EXTRACT(EPOCH FROM (finished_at - started_at))) as min_seconds,
    MAX(EXTRACT(EPOCH FROM (finished_at - started_at))) as max_seconds
FROM jobs
WHERE status = 'SUCCEEDED'
  AND started_at IS NOT NULL
  AND finished_at IS NOT NULL;
```

6. **Find Jobs Using Specific Models:**
```sql
SELECT model, COUNT(*) as count
FROM jobs
WHERE model IS NOT NULL
GROUP BY model
ORDER BY count DESC;
```

**Database Schema Verification:**
```sql
-- Verify jobs table exists and has correct structure
\d jobs

-- Check indexes
\di jobs*

-- Verify migration version
SELECT version_num FROM alembic_version;
```

#### Production Considerations

**Multi-Instance Deployments:**

When running multiple application instances (e.g., for high availability or load balancing) with a shared database:

1. **Job Processing is NOT Distributed:**
   - Current implementation does not include a job worker queue
   - Each job is processed inline by the instance that received the POST request
   - If that instance crashes, the job will be marked as FAILED on next startup of ANY instance
   - Multiple instances can create jobs concurrently without conflicts (UUID-based job IDs prevent collisions)

2. **Database Contention:**
   - Multiple instances share the same database connection pool limits
   - Recovery process runs on ALL instances at startup (idempotent, last one wins)
   - Consider adjusting `DATABASE_POOL_SIZE` if running many instances

3. **Recommended Architecture for Scale:**
   - Use a dedicated job queue system (e.g., Celery, RabbitMQ, Redis Queue) for background processing
   - Separate API instances from worker instances
   - Implement worker claim/lock mechanism to prevent double-processing
   - Current implementation is suitable for moderate load (single instance or 2-3 instances)

**Graceful Shutdown:**

To minimize job failures during deployments:

1. **Stop Accepting New Requests First:**
   - Remove instance from load balancer
   - Wait for in-flight jobs to complete (monitor RUNNING count)
   - Typical job duration is 5-60 seconds depending on complexity

2. **Set Up Health Check Endpoint:**
   - Use `/health` endpoint for liveness checks
   - Consider adding `/ready` endpoint that checks for RUNNING jobs

3. **Kubernetes Example:**
```yaml
spec:
  containers:
  - name: software-planner
    lifecycle:
      preStop:
        exec:
          # Wait for in-flight jobs to complete before terminating
          # Adjust sleep duration based on your typical job processing time
          command: ["sh", "-c", "sleep 15"]
    livenessProbe:
      httpGet:
        path: /health
        port: 8000
      initialDelaySeconds: 30
      periodSeconds: 10
    # Ensure pod termination grace period is longer than preStop sleep
    terminationGracePeriodSeconds: 30
```

**Preventing Race Conditions:**
- Set `terminationGracePeriodSeconds` higher than the `preStop` sleep duration to avoid forced termination
- Monitor the `RUNNING` job count before shutdown (query: `SELECT COUNT(*) FROM jobs WHERE status = 'RUNNING'`)
- Use readiness probes to stop routing traffic before the pod terminates
- Configure load balancer connection draining to allow existing requests to complete
- For critical jobs, consider implementing a graceful shutdown signal handler that waits for active jobs

**Credential Rotation:**

To rotate database credentials without downtime:

1. **Create new database user:**
```sql
-- IMPORTANT: Replace 'YOUR_NEW_SECURE_PASSWORD' with a strong, randomly generated password
CREATE USER planner_app_new WITH PASSWORD 'YOUR_NEW_SECURE_PASSWORD';
GRANT SELECT, INSERT, UPDATE ON TABLE jobs TO planner_app_new;
GRANT SELECT ON TABLE alembic_version TO planner_app_new;
```

2. **Deploy application with new credentials:**
   - Update `DATABASE_URL` or `DATABASE_PASSWORD` environment variable
   - Perform rolling deployment (Kubernetes) or blue-green deployment
   - New instances use new credentials, old instances continue with old

3. **Verify new instances are healthy:**
   - Check logs for successful database connections
   - Test job creation and retrieval

4. **Remove old user after full rollout:**
```sql
-- After all instances updated and verified
DROP USER planner_app_old;
```

**Credential Security:**
- Use secrets management systems to store and rotate credentials automatically
- Never hardcode credentials in configuration files
- Audit credential access and usage regularly

**Read-Only Replicas:**

The application requires **write access** to the database and cannot run with read-only replicas for job persistence:

- Jobs are created (INSERT) and updated (UPDATE) frequently
- Read replicas can only be used for reporting/analytics queries
- Do NOT point `DATABASE_URL` to a read replica - application will fail when trying to create jobs

**If you need to run analytics without impacting the primary:**
```sql
-- Connect to read replica for reporting only
-- Run queries like job statistics, processing times, etc.
-- DO NOT configure the application to use this connection
```

**Migration Management in Production:**

1. **Safely Re-running Migrations:**
   - Migrations are idempotent: `alembic upgrade head` can be run multiple times safely
   - Alembic tracks applied migrations in `alembic_version` table
   - Only unapplied migrations will be executed

2. **Running Migrations with Zero Downtime:**
   - Most migrations can run while application is live (adding columns, indexes)
   - Schema changes are typically backward-compatible
   - For major schema changes:
     - Stop all application instances
     - Run migration: `alembic upgrade head`
     - Verify migration success: `alembic current`
     - Start application instances with new code

3. **Rolling Back Migrations:**
```bash
# View migration history
alembic history

# Rollback to specific version
alembic downgrade <revision>

# Rollback one version
alembic downgrade -1

# Rollback all migrations (destructive!)
alembic downgrade base
```

4. **Migration Checklist:**
   - [ ] Backup database before running migrations
   - [ ] Test migrations in staging environment first
   - [ ] Verify migrations can run with application user permissions
   - [ ] Monitor migration logs for errors
   - [ ] Verify schema with `alembic current` after upgrade
   - [ ] Test application functionality after migration

### Configuration

Configuration is managed through environment variables or a `.env` file. All settings have sensible defaults and are optional.

**To use a `.env` file:**
1. Copy the example file: `cp .env.example .env`
2. Edit `.env` with your desired values
3. The application will automatically load these settings on startup

**Available settings:**

- `APP_NAME`: Application name (default: "Software Planner API")
- `APP_VERSION`: Application version (default: "0.1.0")
- `DEBUG`: Debug mode (default: False)
- `HOST`: Server host (default: "0.0.0.0")
- `PORT`: Server port (default: 8000)
- `API_PREFIX`: API prefix for routes (default: "/api/v1")
- `MAX_DESCRIPTION_BYTES`: Maximum byte length for plan descriptions (default: 8192)
- `DEFAULT_JOBS_LIST_LIMIT`: Default number of jobs returned by GET /api/v1/plans (default: 100)
- `MAX_JOBS_LIST_LIMIT`: Maximum number of jobs that can be requested (default: 1000)
- `ALLOWED_ORIGINS`: CORS allowed origins (default: ["*"] - development only)
- `ALLOWED_CREDENTIALS`: CORS allow credentials (default: False)
- `ALLOWED_METHODS`: CORS allowed methods (default: ["*"])
- `ALLOWED_HEADERS`: CORS allowed headers (default: ["*"])

See `.env.example` for a complete list of configuration options with detailed descriptions and security guidance.

### API Authentication

The Software Planner API supports optional API key authentication via the `X-API-Key` header. When API keys are configured, all planning endpoints require authentication to prevent unauthorized access and enable per-key rate limiting.

#### Configuration

**Environment Variables:**

Configure API keys using the `PLANNER_API_KEYS` environment variable in your `.env` file:

```bash
# Option 1: JSON array format (recommended for multiple keys)
PLANNER_API_KEYS=["key-prod-abc123def456","key-stage-xyz789","key-dev-test001"]

# Option 2: Comma-separated format
PLANNER_API_KEYS=key-prod-abc123def456,key-stage-xyz789,key-dev-test001
```

**Additional Security Settings:**

```bash
# Require API keys to be configured at startup (production: set to true)
PLANNER_API_KEYS_REQUIRED=false

# Minimum API key length (default: 16, recommended: 32+)
PLANNER_API_KEY_MIN_LENGTH=16
```

**⚠️ Security Best Practices:**

1. **Generate Strong Keys**: Use cryptographically secure random keys
   ```bash
   # Generate a secure API key
   openssl rand -hex 32
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

2. **Never Commit Keys**: Add `.env` to `.gitignore` and never commit actual keys to version control

3. **Use Separate Keys**: Issue separate keys for different environments (dev, staging, production) and clients

4. **Rotate Regularly**: Implement a key rotation schedule (recommended: every 90 days)

5. **Minimum Length**: Use keys with at least 32 characters for production deployments

6. **Monitor Usage**: Track API key usage via logging (keys are logged as hashed identifiers only)

#### Using API Keys

**Making Authenticated Requests:**

Include the `X-API-Key` header in all API requests:

```bash
# Example: Create a planning job with authentication
curl -X POST http://localhost:8000/api/v1/plans \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-here" \
  -d '{"description": "Build a REST API for managing tasks"}'
```

**Header Requirements:**

- **Header Name**: `X-API-Key` (case-insensitive)
- **Value**: Your API key exactly as configured (no whitespace stripping)
- **Authentication**: Uses constant-time comparison to prevent timing attacks

#### Authentication Behavior

**When API Keys Are Configured:**

- All planning endpoints (`POST /api/v1/plan`, `POST /api/v1/plans`, `GET /api/v1/plans/{job_id}`) require authentication
- Missing `X-API-Key` header returns `401 Unauthorized`
- Invalid API key returns `403 Forbidden`
- Valid key allows request to proceed (subject to rate limiting)

**When No API Keys Are Configured:**

- Authentication is skipped for backward compatibility
- Requests proceed without the `X-API-Key` header
- **⚠️ Warning**: This mode is only suitable for development or trusted internal networks

**Backward Compatibility:**

- Existing deployments without API keys continue to work unchanged
- Set `PLANNER_API_KEYS_REQUIRED=false` (default) to allow starting without keys
- For production, set `PLANNER_API_KEYS_REQUIRED=true` to enforce key configuration

#### Key Rotation and Revocation

**Rotating API Keys Without Downtime:**

1. **Generate New Keys**: Create new API keys using secure random generation
   ```bash
   openssl rand -hex 32
   ```

2. **Add to Configuration**: Add new keys to `PLANNER_API_KEYS` alongside existing keys
   ```bash
   # Both old and new keys are valid during rotation
   PLANNER_API_KEYS=["old-key-123","new-key-456"]
   ```

3. **Deploy Updated Configuration**: Restart application with updated environment variables

4. **Distribute New Keys**: Provide new keys to API clients

5. **Monitor Migration**: Track usage of old vs new keys via logs (keys logged as hashed identifiers)

6. **Remove Old Keys**: After all clients migrated, remove old keys from configuration
   ```bash
   # Only new key remains
   PLANNER_API_KEYS=["new-key-456"]
   ```

7. **Deploy Final Configuration**: Restart application to revoke old keys

**Emergency Revocation:**

To immediately revoke a compromised key:
1. Remove the key from `PLANNER_API_KEYS` in `.env`
2. Restart the application
3. All requests using the revoked key will immediately receive `403 Forbidden`

**Key Management Tips:**

- Store keys in a secure secrets management system (HashiCorp Vault, AWS Secrets Manager, Kubernetes Secrets)
- Document which keys are issued to which clients/environments
- Implement automated key rotation using infrastructure-as-code
- Set up alerts for authentication failures that may indicate compromised keys

#### Logging and Privacy

**What Gets Logged:**

- Authentication success/failure events (with request IDs)
- Hashed API key identifiers for correlation (first 16 characters of SHA-256 hash)
- Request IDs for tracing authenticated requests

**What Is NOT Logged:**

- Full API key values (never logged in plaintext)
- API key material in error messages or stack traces
- Prompt content or user data

**Example Log Entries:**

```json
{
  "level": "INFO",
  "message": "Authentication successful",
  "request_id": "req-a1b2c3d4",
  "api_key_hash": "a7b9f3e1c2d4e5f6"
}

{
  "level": "WARNING",
  "message": "Authentication failed: Invalid API key",
  "request_id": "req-x9y8z7w6"
}
```

**Security Note**: API keys are never included in logs, error responses, or exposed to clients. Only hashed identifiers appear in logs for debugging and correlation purposes.

### Rate Limiting

The Software Planner API implements token bucket rate limiting to prevent abuse and ensure fair resource allocation. Rate limits can be applied per API key or per client IP address.

#### How Rate Limiting Works

**Token Bucket Algorithm:**

- Each client (identified by API key or IP) has a token bucket
- Bucket starts full with a maximum capacity of tokens
- Each request consumes one token from the bucket
- Tokens refill at a constant rate over time
- Requests are denied when insufficient tokens are available

**Example**: With a limit of 10 requests per 60 seconds:
- Bucket capacity: 10 tokens
- Refill rate: 10 tokens / 60 seconds = 0.167 tokens/second
- Burst: Can make 10 requests immediately, then must wait for refill

#### Configuration

**Environment Variables:**

Configure rate limiting in your `.env` file:

```bash
# Time window for rate limit tracking (seconds)
PLANNER_RATE_LIMIT_WINDOW_SECONDS=60

# Maximum requests allowed per window
PLANNER_RATE_LIMIT_MAX_REQUESTS=10
```

**Rate Limit Modes:**

1. **Per-API-Key Rate Limiting** (Recommended)
   - When `X-API-Key` header is present and valid
   - Each API key gets its own independent rate limit
   - Most accurate for tracking specific clients

2. **Per-IP Rate Limiting** (Fallback)
   - When no API key is provided or API keys are not configured
   - Uses client IP address for identification
   - Less accurate due to NAT, proxies, and IP sharing

#### Client IP Extraction

**Default Behavior (Secure):**

By default, only the direct connection IP is used to prevent IP spoofing attacks:

```bash
# Default: Do not trust proxy headers (most secure)
PLANNER_TRUST_PROXY_HEADERS=false
```

**Behind a Trusted Proxy:**

If your application is behind a trusted reverse proxy or load balancer, enable proxy header trust:

```bash
# Enable X-Forwarded-For and X-Real-IP header processing
PLANNER_TRUST_PROXY_HEADERS=true
```

**⚠️ Security Warning**: Only enable `PLANNER_TRUST_PROXY_HEADERS` if your application is behind a trusted proxy/load balancer that sanitizes these headers. Untrusted proxy headers can be spoofed by clients to bypass rate limiting.

**Priority Order** (when proxy headers are trusted):
1. `X-Forwarded-For` (rightmost IP in the chain)
2. `X-Real-IP`
3. Direct connection IP (fallback)

#### Rate Limit Responses

**When Rate Limit Is Exceeded:**

HTTP `429 Too Many Requests` response with standardized error format:

```json
{
  "error": {
    "code": "rate_limit_exceeded",
    "message": "Rate limit exceeded. Please retry after 5 seconds.",
    "details": {
      "retry_after_seconds": 5,
      "window_seconds": 60,
      "max_requests": 10
    },
    "request_id": "req-a1b2c3d4"
  }
}
```

**Response Headers:**

```
HTTP/1.1 429 Too Many Requests
Retry-After: 5
X-Request-ID: req-a1b2c3d4
```

**Retry-After Guidance:**

- `Retry-After` header indicates seconds to wait before retrying
- Calculated based on token refill rate
- Always rounded up to the next whole second
- Clients should implement exponential backoff for repeated 429 errors

#### Multi-Instance Deployments

**⚠️ Important Limitation**: Rate limiting in the current implementation is **per-instance** and uses in-memory storage. This has important implications for multi-instance deployments:

**Single Instance:**
- Rate limits work as expected
- All requests to the same instance share the same rate limiter state
- Perfect tracking of per-key and per-IP limits

**Multiple Instances (Load Balanced):**
- Each instance maintains its own independent rate limit state
- Total effective rate limit is `configured_limit × number_of_instances`
- Example: With 10 req/min configured and 3 instances, actual limit is ~30 req/min
- Client requests are distributed across instances by load balancer
- Rate limiting is **not synchronized** between instances

**Workarounds for Multi-Instance:**

1. **Reduce Per-Instance Limits**: Divide desired rate limit by expected instance count
   ```bash
   # For 3 instances with desired 30 req/min total:
   PLANNER_RATE_LIMIT_MAX_REQUESTS=10  # 10 req/min × 3 instances = 30 req/min
   ```

2. **Use Sticky Sessions**: Configure load balancer for session affinity based on API key
   - Routes requests from the same API key to the same instance
   - More accurate rate limiting per key
   - Uneven load distribution

3. **Implement Distributed Rate Limiting** (Future Enhancement)
   - Use Redis or similar shared storage for rate limit state
   - Synchronize token buckets across all instances
   - Requires code changes (not currently implemented)

**Recommendation**: For production deployments with multiple instances, use approach #1 (reduce per-instance limits) or deploy a dedicated rate limiting layer (e.g., API Gateway, Nginx rate limiting module).

#### Per-Key Rate Limit Overrides

**Future Feature**: The rate limiter supports per-API-key custom rate limits, but this is not yet exposed via configuration. Future versions may add:

```bash
# Example future configuration (not yet implemented)
PLANNER_RATE_LIMIT_OVERRIDES={"premium-key-abc": 100, "free-tier-xyz": 5}
```

This would allow different rate limits for different clients (e.g., premium vs free tier).

#### Monitoring Rate Limiting

**Observability:**

Rate limiting decisions are logged with structured fields for monitoring:

```json
{
  "level": "INFO",
  "message": "Rate limit check: denied",
  "request_id": "req-a1b2c3d4",
  "identifier_type": "api_key",
  "allowed": false,
  "retry_after_seconds": 5
}
```

**Metrics** (when `PLANNER_METRICS_ENABLED=true`):

Available at `/api/v1/metrics` endpoint:
- `planner_rate_limit_allowed_total` - Total requests allowed
- `planner_rate_limit_denied_total` - Total requests denied
- Rate by identifier type (API key vs IP)

**Tracking Specific Keys:**

- API keys are logged as hashed identifiers (first 16 chars of SHA-256)
- Allows correlating rate limit events without exposing key material
- Search logs for `api_key_hash` to track specific key usage patterns

#### Edge Cases and Behavior

**Clock Skew:**
- Token bucket gracefully handles system time going backwards
- Logs warning when clock skew is detected
- Resets to current time to continue operation

**Server Restart:**
- Rate limit state is **not persisted** across restarts
- All token buckets reset to full capacity on startup
- Clients may see temporary increase in allowed requests after restart

**Concurrent Requests:**
- Token bucket operations are thread-safe
- Concurrent requests from same client may race for tokens
- Last request to consume remaining tokens wins

**No Identifier Available:**
- If both API key and client IP are unavailable, request is denied
- This is a rare edge case (malformed requests or proxy misconfigurations)

### Standardized Error Responses

All API errors follow a consistent, structured format to enable reliable error handling and debugging. Each error includes a machine-readable code, human-readable message, optional context details, and a request ID for tracing.

#### Error Response Structure

**Standard Format:**

```json
{
  "error": {
    "code": "error_code",
    "message": "Human-readable error description",
    "details": {
      "field": "optional_field_name",
      "additional_context": "..."
    },
    "request_id": "req-a1b2c3d4e5f6"
  }
}
```

**Fields:**

- `code` (string, required): Machine-readable error code for programmatic handling
- `message` (string, required): Human-readable description of the error
- `details` (object, optional): Additional context like field names, validation errors, or retry guidance
- `request_id` (string, optional): Unique identifier for tracing the request (also in `X-Request-ID` response header)

#### Error Codes and Status Codes

**Authentication Errors:**

| HTTP Status | Error Code | Description |
|-------------|------------|-------------|
| `401 Unauthorized` | `missing_authentication` | `X-API-Key` header is missing when API keys are configured |
| `403 Forbidden` | `invalid_authentication` | `X-API-Key` header contains an invalid or revoked key |

**Validation Errors:**

| HTTP Status | Error Code | Description |
|-------------|------------|-------------|
| `400 Bad Request` | `validation_error` | Request validation failed (empty description, oversized payload, etc.) |
| `400 Bad Request` | `payload_too_large` | Request body exceeds size limits |
| `400 Bad Request` | `invalid_description` | Description is empty, whitespace-only, or exceeds character limit |
| `400 Bad Request` | `invalid_model` | Specified model is unknown, disabled, or not available |
| `400 Bad Request` | `invalid_system_prompt` | System prompt exceeds maximum length |

**Request Format Errors:**

| HTTP Status | Error Code | Description |
|-------------|------------|-------------|
| `422 Unprocessable Entity` | `invalid_json` | Request body is not valid JSON |
| `422 Unprocessable Entity` | `missing_field` | Required field is missing from request |
| `422 Unprocessable Entity` | `invalid_type` | Field has wrong type (e.g., string instead of integer) |
| `422 Unprocessable Entity` | `malformed_request` | Request structure doesn't match expected schema |

**Rate Limiting:**

| HTTP Status | Error Code | Description |
|-------------|------------|-------------|
| `429 Too Many Requests` | `rate_limit_exceeded` | Rate limit exceeded for API key or client IP |

**Resource Errors:**

| HTTP Status | Error Code | Description |
|-------------|------------|-------------|
| `404 Not Found` | `not_found` | Requested job ID does not exist or has expired |

**Server Errors:**

| HTTP Status | Error Code | Description |
|-------------|------------|-------------|
| `500 Internal Server Error` | `internal_error` | Unexpected server error occurred |
| `500 Internal Server Error` | `planner_error` | Planning service encountered an error |
| `500 Internal Server Error` | `timeout_error` | LLM request timed out after retries |

#### Error Examples

**401 Unauthorized - Missing Authentication:**

```bash
curl -X POST http://localhost:8000/api/v1/plans \
  -H "Content-Type: application/json" \
  -d '{"description": "Build a REST API"}'
```

Response:
```json
{
  "error": {
    "code": "missing_authentication",
    "message": "Missing X-API-Key header",
    "request_id": "req-a1b2c3d4e5f6"
  }
}
```

**403 Forbidden - Invalid API Key:**

```bash
curl -X POST http://localhost:8000/api/v1/plans \
  -H "Content-Type: application/json" \
  -H "X-API-Key: invalid-key" \
  -d '{"description": "Build a REST API"}'
```

Response:
```json
{
  "error": {
    "code": "invalid_authentication",
    "message": "Invalid API key",
    "request_id": "req-a1b2c3d4e5f6"
  }
}
```

**429 Too Many Requests - Rate Limit Exceeded:**

```bash
# After exceeding rate limit
curl -X POST http://localhost:8000/api/v1/plans \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{"description": "Build a REST API"}'
```

Response:
```http
HTTP/1.1 429 Too Many Requests
Retry-After: 5
X-Request-ID: req-a1b2c3d4e5f6

{
  "error": {
    "code": "rate_limit_exceeded",
    "message": "Rate limit exceeded. Please retry after 5 seconds.",
    "details": {
      "retry_after_seconds": 5,
      "window_seconds": 60,
      "max_requests": 10
    },
    "request_id": "req-a1b2c3d4e5f6"
  }
}
```

**400 Bad Request - Validation Error:**

```bash
curl -X POST http://localhost:8000/api/v1/plans \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{"description": ""}'
```

Response:
```json
{
  "error": {
    "code": "validation_error",
    "message": "Description cannot be empty or whitespace-only",
    "details": {
      "field": "description"
    },
    "request_id": "req-a1b2c3d4e5f6"
  }
}
```

**400 Bad Request - Invalid Model:**

```bash
curl -X POST http://localhost:8000/api/v1/plans \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{"description": "Build a REST API", "model": "nonexistent-model"}'
```

Response:
```json
{
  "error": {
    "code": "invalid_model",
    "message": "Unknown model 'nonexistent-model'. Available models: my-gpt-model, my-claude-model",
    "details": {
      "field": "model",
      "available_models": ["my-gpt-model", "my-claude-model"]
    },
    "request_id": "req-a1b2c3d4e5f6"
  }
}
```

**422 Unprocessable Entity - Malformed JSON:**

```bash
curl -X POST http://localhost:8000/api/v1/plans \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{"description": "Build a REST API"'  # Missing closing brace
```

Response:
```json
{
  "error": {
    "code": "invalid_json",
    "message": "Request body is not valid JSON",
    "details": {
      "validation_errors": [
        {
          "loc": ["body"],
          "msg": "JSON decode error",
          "type": "json_invalid"
        }
      ]
    },
    "request_id": "req-a1b2c3d4e5f6"
  }
}
```

**404 Not Found - Job Not Found:**

```bash
curl http://localhost:8000/api/v1/plans/nonexistent-job-id \
  -H "X-API-Key: your-api-key"
```

Response:
```json
{
  "error": {
    "code": "not_found",
    "message": "Job not found",
    "request_id": "req-a1b2c3d4e5f6"
  }
}
```

#### Using Request IDs for Debugging

**What Are Request IDs?**

Every API request is assigned a unique identifier (UUID v4 format) that:
- Appears in the `request_id` field of all error responses
- Is returned in the `X-Request-ID` response header
- Is logged with all related log entries for the request
- Enables tracing a request through the entire system

**How to Use Request IDs:**

1. **Client-Side Error Handling:**
   ```javascript
   try {
     const response = await fetch('/api/v1/plans', {
       method: 'POST',
       headers: {
         'Content-Type': 'application/json',
         'X-API-Key': apiKey
       },
       body: JSON.stringify({description: 'Build a REST API'})
     });
     
     if (!response.ok) {
       const error = await response.json();
       console.error('API Error:', error.error.code);
       console.error('Request ID:', error.error.request_id);
       // Include request_id when contacting support
     }
   } catch (err) {
     console.error('Network error:', err);
   }
   ```

2. **Support Requests:**
   When reporting issues, include the `request_id` from error responses:
   ```
   Issue: Getting 429 errors unexpectedly
   Request ID: req-a1b2c3d4e5f6
   Timestamp: 2025-01-15T10:30:00Z
   ```

3. **Log Searching:**
   Search application logs for the request ID to see the full request lifecycle:
   ```bash
   # Find all log entries for a specific request
   cat application.log | grep "req-a1b2c3d4e5f6"
   
   # Or with jq for structured JSON logs
   cat application.log | jq 'select(.request_id == "req-a1b2c3d4e5f6")'
   ```

#### Error Response Security

**What Is NOT Included in Errors:**

- Internal file paths or system architecture details
- Full stack traces or exception details
- API key values (only hashed identifiers in logs)
- Database connection strings or credentials
- LLM prompts or responses containing user data
- Internal service names or IP addresses

**What IS Included:**

- User-actionable error messages
- Field names that failed validation
- Available options (e.g., list of valid models)
- Retry guidance (e.g., `retry_after_seconds`)
- Request IDs for correlation and support

**Example of Sanitized Error:**

Internal error:
```
File "/app/services/planner.py", line 123, in generate_specs
  raise ConnectionError("Failed to connect to llm-internal.svc.cluster.local:8080")
```

Sanitized API response:
```json
{
  "error": {
    "code": "planner_error",
    "message": "Planning service temporarily unavailable. Please try again later.",
    "request_id": "req-a1b2c3d4e5f6"
  }
}
```

The full error details are logged server-side with the request ID for debugging by operators.

### CORS Configuration

Cross-Origin Resource Sharing (CORS) configuration controls which browser-based clients can access the API. Proper CORS setup is essential for web applications consuming the API from different domains.

#### Default Configuration (Development Only)

**⚠️ Warning**: The default CORS configuration allows all origins and is **ONLY suitable for development**:

```bash
# Default settings in .env.example (insecure for production)
ALLOWED_ORIGINS=["*"]
CORS_WILDCARD_ENABLED=true
ALLOWED_CREDENTIALS=false
ALLOWED_METHODS=["*"]
ALLOWED_HEADERS=["*"]
```

**Security Risk**: Wildcard origins (`*`) allow any website to make requests to your API, potentially enabling:
- Unauthorized access if API keys are leaked
- Cross-site request forgery (CSRF) attacks
- Data exfiltration to malicious domains

#### Production Configuration

**Recommended Production Settings:**

```bash
# Allow only specific trusted domains
ALLOWED_ORIGINS=["https://app.example.com","https://admin.example.com"]
CORS_WILDCARD_ENABLED=false

# Enable credentials if using cookies or authorization headers
ALLOWED_CREDENTIALS=true

# Restrict methods to those actually used
ALLOWED_METHODS=["GET","POST","OPTIONS"]

# Restrict headers to required ones
ALLOWED_HEADERS=["Content-Type","X-API-Key","X-Request-ID"]
```

**Configuration Notes:**

1. **Multiple Origins**: Provide array of allowed domains (include protocol and port if non-standard)
2. **Credentials**: Only set `ALLOWED_CREDENTIALS=true` if using cookies or HTTP auth (not needed for `X-API-Key` header alone)
3. **Wildcard Prevention**: Set `CORS_WILDCARD_ENABLED=false` to explicitly reject wildcard configurations
4. **Methods**: Limit to `GET`, `POST`, `OPTIONS` unless you add other HTTP methods
5. **Headers**: Always include `Content-Type`, `X-API-Key`, and optionally `X-Request-ID`

#### CORS Response Headers

**Exposed Headers:**

The API exposes the following response headers to browser clients:

```
Access-Control-Expose-Headers: X-Request-ID
```

This allows JavaScript clients to read the `X-Request-ID` header for debugging:

```javascript
const response = await fetch('/api/v1/plans/job-123', {
  headers: {'X-API-Key': apiKey}
});
const requestId = response.headers.get('X-Request-ID');
console.log('Request ID:', requestId);
```

#### Testing CORS Configuration

**1. Preflight Request (OPTIONS):**

Browsers send preflight requests for cross-origin requests with custom headers:

```bash
curl -X OPTIONS http://localhost:8000/api/v1/plans \
  -H "Origin: https://app.example.com" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: X-API-Key,Content-Type" \
  -v
```

Expected response headers:
```
HTTP/1.1 200 OK
Access-Control-Allow-Origin: https://app.example.com
Access-Control-Allow-Methods: GET, POST, OPTIONS
Access-Control-Allow-Headers: X-API-Key, Content-Type
Access-Control-Max-Age: 600
```

**2. Actual Request:**

After preflight succeeds, browser makes the actual request:

```javascript
fetch('http://localhost:8000/api/v1/plans', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-API-Key': 'your-api-key'
  },
  body: JSON.stringify({description: 'Build a REST API'})
})
.then(response => response.json())
.then(data => console.log('Job ID:', data.job_id));
```

**3. Verify Origin Blocking:**

Test that disallowed origins are rejected:

```bash
# Should be blocked if not in ALLOWED_ORIGINS
curl -X POST http://localhost:8000/api/v1/plans \
  -H "Origin: https://malicious-site.com" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{"description": "Test"}' \
  -v
```

Browser will not allow the response to be read by JavaScript if origin is blocked.

#### Common CORS Issues

**Issue 1: "CORS policy: No 'Access-Control-Allow-Origin' header"**

**Cause**: Request origin is not in `ALLOWED_ORIGINS`

**Solution**: Add the origin to `ALLOWED_ORIGINS` in `.env`:
```bash
ALLOWED_ORIGINS=["https://your-frontend-domain.com"]
```

**Issue 2: "Credential is not supported if the CORS header 'Access-Control-Allow-Origin' is '*'"**

**Cause**: Cannot use `ALLOWED_CREDENTIALS=true` with wildcard origins

**Solution**: Use specific origins instead of wildcard:
```bash
ALLOWED_ORIGINS=["https://app.example.com"]
ALLOWED_CREDENTIALS=true
CORS_WILDCARD_ENABLED=false
```

**Issue 3: "Request header X-API-Key is not allowed"**

**Cause**: `X-API-Key` not in `ALLOWED_HEADERS`

**Solution**: Add header to allowed list:
```bash
ALLOWED_HEADERS=["Content-Type","X-API-Key","X-Request-ID"]
```

**Issue 4: "Method POST is not allowed"**

**Cause**: `POST` not in `ALLOWED_METHODS`

**Solution**: Add method to allowed list:
```bash
ALLOWED_METHODS=["GET","POST","OPTIONS"]
```

#### Browser Security Considerations

**Same-Origin Policy:**
- CORS is a browser security feature enforced by the browser
- Server-to-server requests (curl, Postman, backend services) are NOT affected by CORS
- API responds to requests from any origin, but browser blocks reading responses from disallowed origins

**CORS vs Authentication:**
- CORS controls which origins can access the API
- Authentication (X-API-Key) controls which clients can use the API
- Both are necessary for complete security:
  - CORS prevents unauthorized **origins** (websites)
  - API keys prevent unauthorized **clients** (users/applications)

**Development vs Production:**
- Development: Use wildcard CORS for convenience (localhost, local IPs)
- Production: Always restrict to specific trusted domains
- Staging: Use staging domain origins for testing

### Database Setup

The Software Planner API uses PostgreSQL for persistent job storage. Jobs are stored in a database table and survive server restarts. This section describes database prerequisites, connection configuration, migration management, and operational considerations.

#### Prerequisites

- **PostgreSQL 12 or higher** (PostgreSQL 17 recommended for production)
- Database user with appropriate permissions (see "Required Permissions" below)
- Network connectivity from application server to PostgreSQL instance

#### Quick Start with Docker (Development)

The easiest way to get started is using Docker:

```bash
# Start PostgreSQL container
docker run -d \
  --name software-planner-db \
  -p 5432:5432 \
  -e POSTGRES_USER=planner \
  -e POSTGRES_PASSWORD=planner_dev_password \
  -e POSTGRES_DB=software_planner \
  postgres:17

# Wait a few seconds for PostgreSQL to start
sleep 5
```

#### Database Configuration

Configure the database connection using environment variables. You have two options:

**Option 1: Complete Database URL (Recommended for Production)**

Set a single `DATABASE_URL` environment variable:

```bash
# IMPORTANT: Replace with actual credentials - never commit real passwords
export DATABASE_URL="postgresql+asyncpg://user:password@localhost:5432/software_planner"
```

**Option 2: Individual Settings (Easier for Development)**

Set individual database settings:

```bash
export DATABASE_HOST=localhost
export DATABASE_PORT=5432
export DATABASE_NAME=software_planner
export DATABASE_USER=planner
# IMPORTANT: Use strong passwords even in development
export DATABASE_PASSWORD=planner_dev_password
```

Or add these to your `.env` file:

```bash
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_NAME=software_planner
DATABASE_USER=planner
# IMPORTANT: Never commit .env file with real passwords to version control
DATABASE_PASSWORD=planner_dev_password
```

#### Running Migrations

After configuring the database connection, run migrations to create the required tables:

```bash
# Upgrade to the latest schema
alembic upgrade head

# Check current migration version
alembic current

# View migration history
alembic history
```

The migrations will create:
- `jobs` table with columns: job_id, status, description, model, system_prompt, result, error, created_at, updated_at, started_at, finished_at
- Indexes on `status` and `created_at` for efficient queries
- `alembic_version` table to track applied migrations

**Important**: Migrations are **idempotent** - running `alembic upgrade head` multiple times is safe. Alembic tracks which migrations have been applied and only runs new ones.

#### Production Database Setup

For production deployments:

1. **Create the Database and User:**

```sql
-- Connect to PostgreSQL as superuser
psql -U postgres

-- Create database
CREATE DATABASE software_planner;

-- Create user with password
-- IMPORTANT: Replace 'YOUR_SECURE_PASSWORD' with a strong password
CREATE USER planner_app WITH PASSWORD 'YOUR_SECURE_PASSWORD';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE software_planner TO planner_app;

-- Connect to the new database
\c software_planner

-- Grant schema privileges (PostgreSQL 15+)
GRANT ALL ON SCHEMA public TO planner_app;
```

2. **Set Environment Variables:**

```bash
# IMPORTANT: Replace with actual credentials from your secrets management system
# Example format shown below - never use these values in production
export DATABASE_URL="postgresql+asyncpg://planner_app:YOUR_SECURE_PASSWORD@db.example.com:5432/software_planner"
```

3. **Run Migrations:**

```bash
alembic upgrade head
```

4. **Verify Connection:**

The application will test the database connection on startup and log any errors. If the connection fails, the application will exit with a clear error message.

#### Required Permissions

The database user needs the following permissions:

**For Running the Application:**
- `SELECT` on `jobs` table - retrieve job status and results
- `INSERT` on `jobs` table - create new planning jobs
- `UPDATE` on `jobs` table - update job status and results
- `SELECT` on `alembic_version` table - verify schema version on startup

**For Running Migrations (can be a separate admin user):**
- `CREATE TABLE` - create new tables during schema upgrades
- `CREATE INDEX` - create performance indexes
- `ALTER TABLE` - modify existing table structure
- `DROP TABLE` - remove tables during rollbacks
- `DROP INDEX` - remove indexes during rollbacks
- `INSERT/UPDATE/DELETE` on `alembic_version` table - track applied migrations

**Best Practice for Production:**
Create two database users:
1. **Migration user** (`planner_admin`) with full DDL permissions - used only for running `alembic upgrade`
2. **Application user** (`planner_app`) with limited DML permissions - used by the running application

Example setup:
```sql
-- Create migration admin user
-- IMPORTANT: Replace 'YOUR_SECURE_ADMIN_PASSWORD' with a strong password
CREATE USER planner_admin WITH PASSWORD 'YOUR_SECURE_ADMIN_PASSWORD';
GRANT ALL PRIVILEGES ON DATABASE software_planner TO planner_admin;

-- Create application user with limited permissions
-- IMPORTANT: Replace 'YOUR_SECURE_APP_PASSWORD' with a strong password
CREATE USER planner_app WITH PASSWORD 'YOUR_SECURE_APP_PASSWORD';
GRANT CONNECT ON DATABASE software_planner TO planner_app;
GRANT USAGE ON SCHEMA public TO planner_app;
GRANT SELECT, INSERT, UPDATE ON TABLE jobs TO planner_app;
GRANT SELECT ON TABLE alembic_version TO planner_app;
```

**Security Best Practices:**
- Use strong, randomly generated passwords (minimum 16 characters)
- Store credentials in a secrets management system (e.g., HashiCorp Vault, AWS Secrets Manager, Kubernetes Secrets)
- Never commit credentials to version control
- Rotate passwords regularly (at least every 90 days)
- Use different passwords for admin and application users

#### Troubleshooting Database Connection

**Connection Refused:**
- Verify PostgreSQL is running: `pg_isready -h localhost -p 5432`
- Check firewall rules allow connections on port 5432
- Verify host and port in DATABASE_URL or individual settings

**Authentication Failed:**
- Verify username and password are correct
- Check PostgreSQL `pg_hba.conf` allows password authentication
- Ensure user has been created: `psql -U postgres -c "\du"`

**Database Does Not Exist:**
- Create the database: `createdb -U postgres software_planner`
- Or use SQL: `CREATE DATABASE software_planner;`

**Permission Denied:**
- Grant necessary privileges (see Production Database Setup above)
- Verify user ownership: `psql -U postgres -d software_planner -c "\l"`

**Migration Errors:**
- Check alembic can connect: `alembic current`
- View migration history: `alembic history`
- If migrations are out of sync, downgrade and re-upgrade: `alembic downgrade base && alembic upgrade head`

The application logs detailed error messages on startup if database connection fails, including the specific error type and actionable troubleshooting steps.

### LLM Integration

The Software Planner API uses OpenAI's GPT models to generate structured software specifications from project descriptions. The background planning service calls the LLM API and transforms responses into actionable specs with must-have requirements, things to avoid, and nice-to-have features.

**JSON Mode Enforcement:** All LLM providers are configured with provider-level JSON mode enforcement to guarantee structured output regardless of custom system prompts. This ensures reliable plan storage and async job polling even when callers override the system prompt.

#### How It Works

When you submit a planning request via the asynchronous API (`POST /api/v1/plans`), the system:

1. **Creates a Job**: Immediately returns a job ID and sets status to `pending`
2. **Queues the Request**: A background worker picks up the job and sets status to `running`
3. **Calls the LLM**: The planner service sends your description to the configured LLM model along with a system prompt that defines the expected JSON structure
4. **Enforces JSON Mode**: Provider-level JSON enforcement (OpenAI json_schema, Claude response_format) guarantees valid JSON output
5. **Retries on Failure**: Implements automatic retry logic with exponential backoff for transient errors (timeouts, rate limits, 5xx server errors)
6. **Validates Response**: Parses and validates the LLM's JSON response against the expected schema
7. **Normalizes Data**: Handles edge cases like single-spec objects, oversized fields, and whitespace
8. **Updates Job**: Sets status to `succeeded` with results, or `failed` with error details

#### LLM Configuration

**Required Environment Variables:**

- `LLM_API_KEY`: Your OpenAI API key (starts with "sk-...")
  - **Required** for LLM-based planning to function
  - Obtain from: https://platform.openai.com/api-keys
  - **Security**: Never commit this to version control

**Optional Environment Variables:**

- `LLM_MODEL`: Model identifier (default: "gpt-4")
  - Recommended: "gpt-5.1" for improved quality and performance
  - Other options: "gpt-4", "gpt-4-turbo"
- `LLM_BASE_URL`: Custom base URL for OpenAI-compatible endpoints or proxies
  - Omit this setting to use the default OpenAI endpoint
  - Use for: Azure OpenAI, custom proxies, or other OpenAI-compatible services
- `LLM_TIMEOUT`: Request timeout in seconds (default: 60)
  - Increase for slower models or complex requests
  - Recommended range: 30-120 seconds
- `LLM_SYSTEM_PROMPT`: Custom system prompt to override the default
  - Default prompt enforces JSON-only output with specific structure
  - **Important:** JSON mode is enforced at provider level regardless of prompt content
  - Custom prompts cannot disable JSON formatting - output will always be valid JSON
  - Advanced users only - test thoroughly before deploying custom prompts

**Example `.env` Configuration:**

```bash
# Required: Your OpenAI API key
LLM_API_KEY=sk-your-actual-api-key-here

# Optional: Specify model (defaults to gpt-4 if not set)
# Recommended: Use gpt-5.1 for better results
LLM_MODEL=gpt-5.1

# Optional: Increase timeout for complex projects
LLM_TIMEOUT=90

# Optional: Custom system prompt (advanced)
# LLM_SYSTEM_PROMPT=Your custom prompt here...
```

**Getting Your OpenAI API Key**

1. Sign up or log in to OpenAI Platform: https://platform.openai.com/
2. Navigate to API Keys: https://platform.openai.com/api-keys
3. Click "Create new secret key"
4. Copy the key immediately (you won't see it again)
5. Add it to your `.env` file as `LLM_API_KEY=sk-...`

**Security Best Practices:**
- **Never commit API keys to Git** - Add `.env` to `.gitignore` and use `.env.example` as a template
- **Keep your API key secure** - Treat it like a password; never share it publicly or in logs
- **Use environment-specific keys** - Separate keys for development, staging, and production
- **Rotate keys regularly** - Create new keys and revoke old ones periodically
- **Monitor usage** - Set up billing alerts and monitor API usage in the OpenAI dashboard
- **Set usage limits** - Configure spending limits on your OpenAI account to prevent unexpected charges
- **Use secrets management** - Store keys in secure vaults (HashiCorp Vault, AWS Secrets Manager, etc.) for production

#### Dependencies

The LLM integration requires the official provider SDKs:

```bash
pip install openai==2.14.0      # For OpenAI GPT models
pip install anthropic==0.75.0   # For Anthropic Claude models
pip install google-genai==1.56.0  # For Google Gemini models
```

These are included in `requirements.txt` and will be installed automatically. The implementation uses:
- **OpenAI Responses API** (recommended for GPT-5+ models, replacing Chat Completions API)
- **Anthropic Messages API** with JSON mode enforcement (beta feature)
- **Google Gemini API** with JSON mime type enforcement
- **Provider-level JSON schema validation** to guarantee structured output
- **Automatic retry logic** for transient failures
- **Structured logging** without exposing API keys

#### JSON Mode Enforcement

**Why JSON Mode Matters:**

Custom system prompts could potentially instruct the LLM to return non-JSON output (e.g., "ignore all formatting and return plain text"). Without provider-level JSON enforcement, this would break plan storage and async job polling.

**How It Works:**

Each LLM provider implementation configures JSON mode at the API level:

- **OpenAI (GPT-5+)**: Uses `response_format` with `json_schema` type and `strict: true`
  - Defines complete JSON schema matching expected output structure
  - OpenAI validates and rejects responses that don't match schema before returning
  - Custom system prompts cannot override this enforcement
  
- **Anthropic (Claude 4+)**: Uses `response_format` with `{"type": "json_object"}` (beta)
  - Ensures Claude always returns valid JSON object structure
  - Custom system prompts cannot disable JSON formatting
  
- **Google (Gemini 3+)**: Uses `generationConfig` with `response_mime_type="application/json"`
  - Enforces JSON output format at generation time
  - Can optionally provide JSON schema for stricter validation

**Model Compatibility:**

Only models supporting JSON mode enforcement are compatible with this API:
- ✅ OpenAI GPT-5.1, GPT-4, GPT-4-turbo (with Responses API or Chat Completions API)
- ✅ Anthropic Claude Sonnet 4.5, Claude Opus 4 (with Messages API)
- ✅ Google Gemini 3.0 Pro (with generationConfig)
- ❌ Legacy models without JSON mode support will fail at configuration time

**Testing JSON Enforcement:**

The test suite includes specific tests (`TestOpenAIJSONModeEnforcement`, `TestClaudeJSONModeEnforcement`) that verify:
- JSON mode is configured in API calls
- Custom prompts attempting to disable JSON still return structured data
- Schema violations are detected and reported with actionable errors

#### Retry and Timeout Behavior

The planner implements robust retry logic for reliability:

- **Retryable Errors**: Timeouts, rate limits (429), network errors, 5xx server errors
- **Non-Retryable Errors**: Authentication failures (401), invalid requests (400), not found (404)
- **Retry Strategy**: Exponential backoff (1s, 2s, 4s...) up to 10s between attempts
- **Max Retries**: 3 attempts by default
- **Total Timeout**: `LLM_TIMEOUT` applies per request attempt, not total time

**Example Retry Sequence:**
1. Initial request times out after 60s → Wait 1s → Retry
2. Second request hits rate limit → Wait 2s → Retry
3. Third request succeeds → Job marked as `succeeded`

If all retries are exhausted, the job is marked as `failed` with error details.

#### Customizing the System Prompt

The default system prompt instructs the LLM to generate specs in a specific JSON format. You can override it via `LLM_SYSTEM_PROMPT` for custom behavior:

**Default Prompt Behavior:**
- Enforces JSON-only output (no markdown, no extra text)
- Requires specific structure: `{"specs": [{"purpose": "...", "vision": "...", "must": [], "dont": [], "nice": []}]}`
- Ensures arrays are never missing (can be empty)

**When to Customize:**
- You need different spec fields or structure
- You want to emphasize certain types of requirements
- You're experimenting with prompt engineering

**Important:** Custom prompts cannot disable JSON formatting. Provider-level JSON mode enforcement guarantees valid JSON output regardless of prompt content. Even prompts explicitly requesting plain text will result in structured JSON output.

### Troubleshooting LLM Issues

#### Common Failure Modes

**1. Authentication Errors (401)**

**Symptom**: Job fails immediately with error message about authentication.

**Cause**: Invalid or missing API key.

**Solution**:
- Verify `LLM_API_KEY` is set in your `.env` file
- Ensure the key starts with "sk-" and is copied correctly
- Check your API key is still valid in the OpenAI dashboard
- Verify you haven't exceeded your OpenAI account limits

**2. Timeout Errors**

**Symptom**: Job fails after `LLM_TIMEOUT` seconds with timeout error.

**Cause**: LLM request took too long (complex project, slow model, network issues).

**Solution**:
- Increase `LLM_TIMEOUT` in your `.env` (try 90 or 120 seconds)
- Simplify the project description if it's very long
- Check your network connection to OpenAI
- Try again later (OpenAI API may be experiencing issues)

**3. Rate Limit Errors (429)**

**Symptom**: Job fails after retries with rate limit error.

**Cause**: Too many requests to OpenAI API (exceeded quota or rate limit).

**Solution**:
- Wait a few minutes before retrying
- Check your OpenAI account limits and usage
- Upgrade your OpenAI plan if needed
- Implement request throttling in your application

**4. Schema Validation Errors**

**Symptom**: Job fails with error about missing fields or invalid JSON structure.

**Cause**: LLM returned response that doesn't match expected schema (usually due to custom system prompt).

**Solution**:
- If using a custom `LLM_SYSTEM_PROMPT`, verify it enforces the required JSON structure
- Try removing the custom prompt to use the default
- Check logs for details about which field is missing or invalid
- File an issue if this happens with the default prompt (LLM regression)

**5. Model Not Found (404)**

**Symptom**: Job fails with error about model not being found.

**Cause**: Invalid `LLM_MODEL` name or model not available to your API key.

**Solution**:
- Verify `LLM_MODEL` is spelled correctly (e.g., "gpt-4", "gpt-5.1")
- Check the model is available in your OpenAI account
- Use the default model by omitting `LLM_MODEL` from your `.env`

**6. Base URL Configuration Issues**

**Symptom**: Connection errors or authentication failures when using `LLM_BASE_URL`.

**Cause**: Invalid base URL or incompatible proxy/service.

**Solution**:
- Verify the base URL is correct and includes the full path (e.g., `https://api.openai.com/v1`)
- Ensure the service is OpenAI-compatible
- Try removing `LLM_BASE_URL` to use the default OpenAI endpoint
- Check proxy or custom service documentation for proper configuration

**How Errors Surface**

**Via Job Status API (GET /api/v1/plans/{job_id})**:

When a planning job fails, the response includes error details:

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "failed",
  "created_at": "2025-01-01T12:00:00Z",
  "updated_at": "2025-01-01T12:00:05Z",
  "result": null,
  "error": {
    "error": "LLM configuration error: OpenAI authentication failed: Invalid API key. Please check your API key.",
    "type": "LLMConfigurationError"
  }
}
```

**Error Types:**
- `LLMConfigurationError`: Configuration issues (missing API key, invalid model, bad timeout)
- `LLMRequestError`: API request failures (timeout, rate limit, network error, 5xx error)
- `LLMResponseError`: Invalid response (JSON parse error, schema validation failure)

**Security Note:** Error messages are sanitized to prevent information leakage:
- API keys are never included in error responses or logs
- Full stack traces are not exposed to API clients
- Internal system paths and configurations are redacted
- Only error types and user-actionable messages are returned

**Via Application Logs**:

The planner logs detailed information at various levels:

- **INFO**: Request metadata (model, description length, retry attempts, latency)
- **WARNING**: Non-fatal issues (empty `must` fields, oversized responses being truncated)
- **ERROR**: Failures (authentication, timeout, validation errors) with sanitized error messages

**Logging Security:**
- API keys and secrets are never logged
- Sensitive data is redacted from logs (passwords, tokens, PII)
- Logs contain only metadata and error types
- Full request/response bodies are not logged to prevent data leaks

**Example Log Output:**
```
INFO: Generating specs via LLM - model=gpt-5.1, description_length=245
INFO: OpenAI API call succeeded - retry_count=0, latency_ms=3421, total_tokens=456
INFO: Successfully generated specs - spec_count=2
```

#### Current Limitations

- **Single Provider**: Only OpenAI is supported currently. Anthropic Claude and Google Gemini support is planned but not yet implemented.
- **No Streaming**: Responses are not streamed; clients must wait for complete generation.
- **In-Memory Jobs**: Job status is lost on server restart (see "Known Limitations" section).

> **Security Note:** The default CORS configuration (`ALLOWED_ORIGINS=["*"]`) is suitable for development only. In production, set `ALLOWED_ORIGINS` to specific domains and configure `ALLOWED_CREDENTIALS` appropriately.

### Observability: Metrics and Structured Logging

The Software Planner API provides comprehensive observability through Prometheus-compatible metrics and structured logging. This enables monitoring of system health, performance tracking, and debugging.

#### Metrics Collection

**Configuration:**

Metrics collection is disabled by default. Enable it via environment variable:

```bash
PLANNER_METRICS_ENABLED=true
```

Or in `.env`:

```bash
PLANNER_METRICS_ENABLED=true
```

**Accessing Metrics:**

When enabled, metrics are exposed at the `/api/v1/metrics` endpoint in Prometheus text format:

```bash
curl http://localhost:8000/api/v1/metrics
```

**⚠️ Security Warning - Metrics Endpoint Protection:**

The `/api/v1/metrics` endpoint is **NOT protected by API key authentication** by default. This endpoint exposes operational metrics including:
- Request rates and patterns
- Job processing statistics
- LLM provider usage and latency
- Error rates and types

**Production Recommendations:**

1. **Network-Level Protection**: Deploy metrics endpoint on a separate internal port or restrict access at the network level
   - Use firewall rules to allow access only from monitoring systems (e.g., Prometheus)
   - Place behind a VPN or internal network segment
   - Use network policies in Kubernetes to restrict access

2. **Reverse Proxy Authentication**: Use a reverse proxy (nginx, Caddy) to add authentication
   ```nginx
   location /api/v1/metrics {
       auth_basic "Metrics Access";
       auth_basic_user_file /etc/nginx/.htpasswd;
       proxy_pass http://localhost:8000;
   }
   ```

3. **IP Allowlisting**: Configure your reverse proxy or API gateway to allow metrics access only from known monitoring IPs
   ```nginx
   location /api/v1/metrics {
       allow 10.0.0.0/8;      # Internal network
       allow 192.168.1.100;   # Prometheus server
       deny all;
       proxy_pass http://localhost:8000;
   }
   ```

4. **Separate Admin Port** (Future Enhancement): Consider running metrics on a separate port (e.g., 9090) that is not exposed externally

**What Metrics Expose:**

Metrics do NOT contain:
- API key values or credentials
- User prompts or generated content
- Personal identifiable information (PII)
- Internal system paths or configuration

Metrics DO contain:
- Aggregate request counts and latencies
- Job success/failure rates
- Model usage patterns
- Error type distributions

Even without sensitive data, metrics can reveal:
- API usage patterns and peak times
- Which models are most popular
- Error rates that may indicate system health issues
- Information useful for capacity planning or competitive analysis

**Available Metrics:**

1. **HTTP Request Metrics**
   - `planner_http_requests_total{endpoint, method, status}` - Total HTTP requests by endpoint and status code
   - `planner_http_request_duration_seconds{endpoint, method}` - Request duration histogram

2. **Job Lifecycle Metrics**
   - `planner_job_status_total{status}` - Total jobs by status (QUEUED, RUNNING, SUCCEEDED, FAILED)
   - `planner_job_duration_seconds{status}` - Job processing duration histogram
   - `planner_jobs_in_progress` - Current number of jobs being processed

3. **LLM Client Metrics**
   - `planner_llm_requests_total{provider, model, status}` - Total LLM API requests
   - `planner_llm_request_duration_seconds{provider, model}` - LLM request latency histogram
   - `planner_llm_tokens_total{provider, model, token_type}` - Total tokens consumed (prompt/completion)

**Example Prometheus Queries:**

```promql
# HTTP request rate by endpoint
rate(planner_http_requests_total[5m])

# 95th percentile job duration
histogram_quantile(0.95, rate(planner_job_duration_seconds_bucket[5m]))

# LLM error rate
rate(planner_llm_requests_total{status="error"}[5m])

# Current jobs in progress
planner_jobs_in_progress
```

#### Structured Logging

The application emits structured logs with consistent fields for correlation and filtering:

**Common Log Fields:**

- `request_id` - Unique identifier for each HTTP request (also in X-Request-ID header)
- `job_id` - Job identifier for async planning operations
- `api_key_hash` - Hashed API key for rate limiting context (never logs actual keys)
- `model` - LLM model name
- `status` - Job or request status
- `error_type` - Exception class name for errors
- `duration_seconds` - Operation duration

**Log Examples:**

```json
{
  "level": "INFO",
  "message": "Job job-123 transitioned: QUEUED -> RUNNING",
  "request_id": "req-456",
  "job_id": "job-123",
  "from_status": "QUEUED",
  "to_status": "RUNNING"
}

{
  "level": "INFO",
  "message": "LLM request completed: openai/gpt-4 (success)",
  "provider": "openai",
  "model": "gpt-4",
  "duration_seconds": 2.5,
  "status": "success",
  "prompt_tokens": 100,
  "completion_tokens": 150
}

{
  "level": "INFO",
  "message": "POST /api/v1/plans 202",
  "method": "POST",
  "endpoint": "/api/v1/plans",
  "status": 202,
  "duration_seconds": 0.05,
  "api_key_hash": "a1b2c3d4e5f6a7b8"
}
```

**Security Considerations:**

- **API Keys**: Never logged in plain text. Only hashed identifiers (first 16 chars of SHA-256) are logged
- **Prompts**: Project descriptions and system prompts are never logged to prevent data leakage
- **Secrets**: Database passwords, LLM API keys, and other secrets are never included in logs
- **Token Counts**: Only aggregate counts are logged, not actual token content

#### Logging Redaction Policies

The application implements strict logging policies to prevent accidental exposure of sensitive data:

**What Is NEVER Logged:**

1. **API Keys and Secrets**
   - LLM provider API keys (OpenAI, Anthropic, Google)
   - Database passwords and connection strings
   - Planner API keys (only hashed identifiers are logged)
   - Any environment variables containing credentials

2. **User Content and PII**
   - Planning request descriptions (prompts)
   - Custom system prompts
   - LLM-generated specifications and responses
   - Job result payloads
   - Personally identifiable information (PII)

3. **Internal System Details**
   - Full file system paths
   - Internal service hostnames and IP addresses
   - Complete stack traces (sanitized versions in logs, full traces in monitoring only)
   - Database schema or query details containing sensitive data

**What IS Logged:**

1. **Request Metadata**
   - Request IDs for correlation
   - HTTP method, endpoint, and status code
   - Request duration and timestamp
   - API key hashes (first 16 chars of SHA-256, e.g., `a1b2c3d4e5f6a7b8`)

2. **Job Lifecycle Events**
   - Job ID, status transitions (QUEUED → RUNNING → SUCCEEDED/FAILED)
   - Processing duration and timestamps
   - Model name used (logical name, not API key)
   - Error types (exception class names, sanitized messages)

3. **LLM API Interactions**
   - Provider name (openai, anthropic, google) and model ID
   - Request duration and retry attempts
   - Token counts (prompt tokens, completion tokens, total tokens)
   - HTTP status codes and error types (without sensitive details)

4. **Authentication and Rate Limiting**
   - Authentication success/failure (with request ID, without key values)
   - Rate limit decisions (allowed/denied, retry-after seconds)
   - Hashed API key identifiers for correlation

**Debug Logging:**

Even when `DEBUG=true`, the redaction policies remain in effect:
- Debug logs include more verbose operation details
- Sensitive data is still redacted (keys, prompts, secrets)
- May include additional metadata like request headers (but not Authorization/X-API-Key values)

**Enabling Debug Logging:**

```bash
# In .env file
DEBUG=true
```

**⚠️ Warning**: Debug logging increases log volume significantly and may impact performance. Only enable for troubleshooting specific issues, and disable after debugging is complete.

**Log Formats:**

The application uses structured logging (JSON format) for machine readability:
- Consistent field names across all log entries
- Easy filtering and searching in log aggregation systems
- Automatic inclusion of context (request_id, job_id, timestamps)

**Example Redacted Error Log:**

Instead of logging:
```json
{
  "error": "LLM API request failed",
  "api_key": "sk-actual-openai-key-here",
  "prompt": "User's confidential project description",
  "url": "https://api.openai.com/v1/responses"
}
```

Actual redacted log:
```json
{
  "level": "ERROR",
  "message": "LLM API request failed: authentication error",
  "provider": "openai",
  "model": "gpt-5.1",
  "error_type": "AuthenticationError",
  "request_id": "req-a1b2c3d4",
  "duration_seconds": 0.5
}
```

**Compliance Considerations:**

These redaction policies help maintain compliance with:
- **GDPR**: Personal data not logged unnecessarily
- **SOC 2**: Logging controls prevent sensitive data exposure
- **PCI DSS**: Credentials and secrets never logged
- **HIPAA**: Healthcare data (if in prompts) not logged

**Audit Logging:**

For compliance and security auditing, consider:
1. **Centralized Log Collection**: Send logs to SIEM (Splunk, ELK, Datadog)
2. **Log Retention**: Define retention policies (30-90 days for operational, longer for audit)
3. **Access Controls**: Restrict log access to authorized personnel only
4. **Tamper Protection**: Use write-once storage or log signing for audit trails

**Log Filtering Examples:**

Using structured logging tools (e.g., jq, Loki, ELK):

```bash
# Filter logs by job_id
cat logs.json | jq 'select(.job_id == "job-123")'

# Find all failed LLM requests
cat logs.json | jq 'select(.provider and .status == "error")'

# Track a request across its lifecycle
cat logs.json | jq 'select(.request_id == "req-456")'
```

#### Integration with Monitoring Systems

**Prometheus Setup:**

Add the Software Planner as a scrape target:

```yaml
scrape_configs:
  - job_name: 'software-planner'
    scrape_interval: 15s
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/api/v1/metrics'
```

**Grafana Dashboard:**

Create visualizations for:
- Request rate and latency by endpoint
- Job success/failure rates over time
- LLM provider performance comparison
- Token usage trends

**Alerting Examples:**

```yaml
# Alert on high error rate
- alert: HighJobFailureRate
  expr: rate(planner_job_status_total{status="FAILED"}[5m]) > 0.1
  for: 5m
  annotations:
    summary: "High job failure rate detected"

# Alert on slow LLM responses
- alert: SlowLLMResponses
  expr: histogram_quantile(0.95, rate(planner_llm_request_duration_seconds_bucket[5m])) > 30
  for: 10m
  annotations:
    summary: "LLM response times degraded"
```

### Testing

The project includes comprehensive tests for all endpoints and functionality.

**Run all tests:**
```bash
pytest
```

**Run tests with verbose output:**
```bash
pytest -v
```

**Run specific test file:**
```bash
pytest tests/test_health_endpoint.py
pytest tests/test_plan_endpoint.py
```

**Run with coverage report:**
```bash
pytest --cov=app tests/
```

**Test Coverage:**
- `tests/test_health_endpoint.py` - Health check endpoint tests
- `tests/test_plan_endpoint.py` - Synchronous planning endpoint tests (happy path, validation, edge cases)
- `tests/test_plans_async_endpoint.py` - Asynchronous planning endpoint tests
- `tests/test_plans_polling_endpoints.py` - Job polling and listing endpoint tests
- `tests/test_planner_integration.py` - Planner service integration tests
- `tests/test_job_store.py` - Job storage service tests
- `tests/test_job_model.py` - Job model tests
- `tests/test_main.py` - Application setup and general endpoint tests
- `tests/test_config.py` - Configuration and settings tests
- `tests/test_llm_client.py` - LLM client abstraction tests
- `tests/test_llm_openai.py` - OpenAI client implementation tests
- `tests/test_store_singleton.py` - Service singleton factory tests

All tests should pass. If you encounter any failures, ensure:
1. All dependencies are installed (`pip install -r requirements.txt`)
2. You're using Python 3.10 or higher
3. Your virtual environment is activated (if using one)

## Project Structure

```
.
├── app/
│   ├── __init__.py
│   ├── main.py              # Application factory and entrypoint
│   ├── api/                 # API routes
│   │   ├── __init__.py
│   │   └── routes.py        # Planning API endpoints
│   ├── core/                # Core configuration and utilities
│   │   ├── __init__.py
│   │   └── config.py        # Typed settings with Pydantic
│   ├── models/              # Data models
│   │   ├── __init__.py
│   │   ├── request.py       # Request models with validation
│   │   └── response.py      # Response models
│   └── services/            # Business logic services
│       ├── __init__.py
│       └── planner.py       # Planning service with LLM integration
├── tests/                   # Test suite
│   ├── __init__.py
│   ├── test_config.py       # Configuration tests
│   ├── test_main.py         # Application and general endpoint tests
│   ├── test_health_endpoint.py  # Health endpoint tests
│   └── test_plan_endpoint.py    # Comprehensive /plan endpoint tests
├── .env.example             # Example environment configuration
├── requirements.txt         # Python dependencies
└── pytest.ini              # Pytest configuration
```

## Development

### Adding New Routes

API routes can be added by creating routers in `app/api/` and registering them in `app/main.py`:

```python
from app.api.your_module import router as your_router

app.include_router(your_router.router, prefix=settings.api_prefix)
```

### Adding New Models

Data models should be added to the `app/models/` directory using Pydantic for validation.



# Permanents (License, Contributing, Author)

Do not change any of the below sections

## License

This Agent Foundry Project is licensed under the Apache 2.0 License - see the LICENSE file for details.

## Contributing

Feel free to submit issues and enhancement requests!

## Author

Created by Agent Foundry and John Brosnihan
