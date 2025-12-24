# Deployment Guide

This guide provides comprehensive instructions for deploying the Software Planner API to various environments, from local development to production container platforms.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Environment Variables Reference](#environment-variables-reference)
- [Deployment Methods](#deployment-methods)
  - [Docker Deployment](#docker-deployment)
  - [Docker Compose Deployment](#docker-compose-deployment)
  - [Container Platform Deployment](#container-platform-deployment)
- [Scaling Considerations](#scaling-considerations)
- [Operational Procedures](#operational-procedures)
- [CI/CD Integration](#cicd-integration)
- [Troubleshooting](#troubleshooting)

## Prerequisites

Before deploying the Software Planner API, ensure you have:

### Required

- **Container Runtime**: Docker 20.10+ or equivalent OCI-compatible runtime
- **PostgreSQL Database**: Version 12 or higher (17 recommended for production)
- **LLM API Key**: OpenAI API key for planning functionality (obtain from [platform.openai.com](https://platform.openai.com/api-keys))
- **Network Connectivity**: Access to OpenAI API endpoints (api.openai.com) and your PostgreSQL database

### Recommended for Production

- **Container Orchestration**: Kubernetes, Docker Swarm, ECS, or similar
- **Secrets Management**: HashiCorp Vault, AWS Secrets Manager, or Kubernetes Secrets
- **Load Balancer**: For distributing traffic across multiple instances
- **Monitoring**: Prometheus + Grafana for metrics collection
- **Log Aggregation**: ELK Stack, Loki, or similar for centralized logging
- **Managed PostgreSQL**: AWS RDS, Azure Database, or Google Cloud SQL

## Environment Variables Reference

The Software Planner API is configured entirely through environment variables. No secrets are hardcoded in the application.

### Required Variables

These variables MUST be set in production:

| Variable | Purpose | Example | Default | Context |
|----------|---------|---------|---------|---------|
| `LLM_API_KEY` | OpenAI API key for generating specifications | `sk-proj-abc...xyz` | None | Required for all |
| `DATABASE_URL` | Complete PostgreSQL connection string | `postgresql+asyncpg://user:pass@host:5432/db` | None | Required for all |
| `PLANNER_API_KEYS` | API keys for authenticating client requests | `["key1","key2"]` | `[]` | Required for production |

**Security Note**: Never commit these values to version control. Use secrets management systems in production.

### Server Configuration

| Variable | Purpose | Example | Default | Context |
|----------|---------|---------|---------|---------|
| `HOST` | Server bind address | `0.0.0.0` | `0.0.0.0` | All |
| `PORT` | Server port | `8080` | `8000` | All |
| `WORKERS` | Number of uvicorn worker processes | `4` | `1` | Production: set to CPU cores |
| `LOG_LEVEL` | Logging verbosity | `info` | `info` | All; use `debug` for troubleshooting |
| `DEBUG` | Enable debug mode | `false` | `false` | **Never** enable in production |

### Database Configuration (Alternative to DATABASE_URL)

If `DATABASE_URL` is not set, provide these individual settings:

| Variable | Purpose | Example | Default | Context |
|----------|---------|---------|---------|---------|
| `DATABASE_HOST` | PostgreSQL host | `db.example.com` | `localhost` | All |
| `DATABASE_PORT` | PostgreSQL port | `5433` | `5432` | All |
| `DATABASE_NAME` | Database name | `planner_prod` | `software_planner` | All |
| `DATABASE_USER` | Database username | `planner_app` | None | Required |
| `DATABASE_PASSWORD` | Database password | `secure_password` | None | Required |

### LLM Configuration

| Variable | Purpose | Example | Default | Context |
|----------|---------|---------|---------|---------|
| `LLM_MODEL` | OpenAI model identifier | `gpt-5.1` | `gpt-4` | Optional; affects quality/speed |
| `LLM_TIMEOUT` | LLM request timeout (seconds) | `90` | `60` | Increase for complex projects |
| `LLM_BASE_URL` | Custom OpenAI endpoint | `https://api.proxy.com/v1` | None | For Azure OpenAI or proxies |

### Authentication and Rate Limiting

| Variable | Purpose | Example | Default | Context |
|----------|---------|---------|---------|---------|
| `PLANNER_API_KEYS_REQUIRED` | Enforce API key configuration | `true` | `false` | Production: set to `true` |
| `PLANNER_API_KEY_MIN_LENGTH` | Minimum key length | `32` | `16` | Production: increase to 32+ |
| `PLANNER_RATE_LIMIT_MAX_REQUESTS` | Max requests per window | `100` | `10` | Tune per workload |
| `PLANNER_RATE_LIMIT_WINDOW_SECONDS` | Rate limit window | `60` | `60` | Usually keep at 60s |
| `PLANNER_TRUST_PROXY_HEADERS` | Trust X-Forwarded-For headers | `true` | `false` | Enable behind load balancer |

**⚠️ Rate Limiting in Multi-Instance Deployments**: The current implementation uses in-memory rate limiting, meaning each instance maintains independent rate limit state. This is by design for simplicity and performance.

**Impact**: Total effective limit is `configured_limit × number_of_instances`. 

**Example**: With `PLANNER_RATE_LIMIT_MAX_REQUESTS=10` and 3 instances, the system allows approximately 30 requests/minute total (10 per instance).

**Important**: If exact per-key rate limiting across instances is required, consider implementing distributed rate limiting using Redis or deploying a centralized API gateway. See the "Scaling Considerations" section for detailed strategies.

### CORS Configuration

| Variable | Purpose | Example | Default | Context |
|----------|---------|---------|---------|---------|
| `ALLOWED_ORIGINS` | Allowed cross-origin domains | `["https://app.example.com"]` | `["*"]` | Production: set specific domains |
| `CORS_WILDCARD_ENABLED` | Allow wildcard origins | `false` | `true` | Production: set to `false` |
| `ALLOWED_CREDENTIALS` | Allow credentials in CORS | `true` | `false` | Enable if using cookies |

### Observability

| Variable | Purpose | Example | Default | Context |
|----------|---------|---------|---------|---------|
| `PLANNER_METRICS_ENABLED` | Enable Prometheus metrics | `true` | `false` | Production: enable for monitoring |

**⚠️ Critical Security Warning**: The metrics endpoint (`/api/v1/metrics`) is **NOT protected by API key authentication**. This endpoint exposes operational metrics including request patterns, job statistics, and LLM usage.

**Required Security Controls**:
- **Network-level restrictions** (firewall rules, security groups, VPN)
- **IP allowlisting** (only monitoring systems like Prometheus)
- **Reverse proxy authentication** (nginx basic auth, OAuth proxy)
- **Separate admin port** (not exposed to public internet)

**Never** expose the metrics endpoint directly to the public internet without authentication.

### Configuration Contexts Explained

- **All**: Applies to all environments (local, Docker, CI, production)
- **Required for all**: Must be set in every environment for the application to function
- **Required for production**: Must be set in production; optional for development
- **Production**: Best practice for production; optional elsewhere
- **Optional**: Can be omitted; application will use sensible defaults

## Deployment Methods

### Docker Deployment

The Software Planner includes a production-ready multi-stage Dockerfile optimized for security and minimal image size (~150MB).

#### Building the Image

```bash
# Basic build
docker build -t software-planner:latest .

# Build with version tag
docker build -t software-planner:v1.0.0 .

# Build for multiple platforms
docker buildx build --platform linux/amd64,linux/arm64 \
  -t software-planner:latest .

# Build with SSL certificate bypass (⚠️ CI ENVIRONMENTS ONLY ⚠️)
# SECURITY WARNING: This disables SSL certificate verification for PyPI
# ONLY use in CI/CD pipelines with corporate SSL interception proxies
# NEVER use in production or for building production images
docker build --build-arg TRUST_PYPI=true -t software-planner:latest .
```

**⚠️ Security Note on TRUST_PYPI**: The `TRUST_PYPI=true` build argument bypasses SSL certificate verification when installing Python packages. This is **ONLY** for CI environments with SSL-intercepting corporate proxies. Using this flag:
- Disables SSL verification for PyPI.org and files.pythonhosted.org
- Increases risk of man-in-the-middle attacks
- Should **NEVER** be used for production image builds
- Should only be temporary until proper CA certificates are configured

#### Running the Container

**Basic Usage** (development):

```bash
docker run -p 8000:8000 \
  -e LLM_API_KEY=sk-your-api-key \
  -e DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db \
  software-planner:latest
```

**Production Configuration**:

```bash
docker run -d \
  --name software-planner \
  -p 8000:8000 \
  --restart unless-stopped \
  --memory=512m \
  --cpus=2.0 \
  -e PORT=8000 \
  -e WORKERS=4 \
  -e HOST=0.0.0.0 \
  -e LOG_LEVEL=info \
  -e LLM_API_KEY=sk-your-openai-api-key \
  -e LLM_MODEL=gpt-5.1 \
  -e LLM_TIMEOUT=90 \
  -e DATABASE_URL=postgresql+asyncpg://user:password@db.example.com:5432/software_planner \
  -e PLANNER_API_KEYS='["secure-key-1","secure-key-2"]' \
  -e PLANNER_API_KEYS_REQUIRED=true \
  -e PLANNER_RATE_LIMIT_MAX_REQUESTS=100 \
  -e PLANNER_RATE_LIMIT_WINDOW_SECONDS=60 \
  -e PLANNER_TRUST_PROXY_HEADERS=true \
  -e ALLOWED_ORIGINS='["https://app.example.com"]' \
  -e CORS_WILDCARD_ENABLED=false \
  -e PLANNER_METRICS_ENABLED=true \
  software-planner:latest
```

**Using Environment File**:

Create `.env.production` file (see Environment Variables Reference above), then:

```bash
docker run -d \
  --name software-planner \
  -p 8000:8000 \
  --env-file .env.production \
  software-planner:latest
```

**⚠️ Security**: Never commit `.env.production` with real secrets to version control.

#### Container Health Checks

The container includes a built-in health check that verifies the `/health` endpoint:

```bash
# Check container health
docker ps --filter name=software-planner

# Expected STATUS column:
# Up 5 minutes (healthy)

# Manually test health endpoint
curl http://localhost:8000/health
# Expected: {"status":"ok"}
```

#### Running Database Migrations

Before starting the application for the first time, run database migrations:

```bash
# Run migrations using the container
docker run --rm \
  -e DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db \
  software-planner:latest \
  sh -c "alembic upgrade head"

# Or connect to a running container
docker exec software-planner alembic upgrade head
```

**Best Practice**: Run migrations as a separate deployment step before starting/updating application containers.

### Docker Compose Deployment

Docker Compose provides an integrated environment with PostgreSQL database and automatic migrations.

#### Quick Start

1. **Copy environment template**:
```bash
cp .env.example .env
```

2. **Configure required variables** in `.env`:
```bash
# Minimum required configuration
LLM_API_KEY=sk-your-openai-api-key

# Optional: Override defaults
PORT=8000
WORKERS=2
DATABASE_PASSWORD=strong_password_here
PLANNER_API_KEYS='["dev-key-1"]'
```

3. **Start services**:
```bash
# Using Makefile (recommended)
make compose-up

# Or using docker compose directly
docker compose up -d
```

4. **Verify deployment**:
```bash
# Check service health
docker compose ps

# View logs
make compose-logs

# Test API
curl http://localhost:8000/health
```

#### Docker Compose Management

The `Makefile` provides convenient commands:

```bash
# Start services (builds if needed, runs migrations)
make compose-up

# View logs (follows output)
make compose-logs

# Stop services (preserves data)
make compose-down

# Restart services (no rebuild)
make compose-restart

# Rebuild containers from scratch
make compose-build

# Run migrations manually
make compose-migrate

# Clean up (⚠️ deletes all data!)
make compose-clean
```

#### Production Considerations for Docker Compose

While Docker Compose is excellent for development and small-scale production deployments, consider these limitations:

- **Single Host**: Docker Compose runs on a single host; no built-in cluster support
- **No Auto-Scaling**: Cannot automatically scale based on load
- **Manual Updates**: Requires manual intervention for rolling updates
- **Limited Redundancy**: Database and application run on same host

For high-availability production deployments, consider container orchestration platforms (see next section).

### Container Platform Deployment

The Software Planner can be deployed to any container orchestration platform. This section provides guidance for common platforms.

#### Amazon ECS (Elastic Container Service)

**Task Definition Example**:

```json
{
  "family": "software-planner",
  "containerDefinitions": [
    {
      "name": "app",
      "image": "your-registry/software-planner:v1.0.0",
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {"name": "PORT", "value": "8000"},
        {"name": "WORKERS", "value": "4"},
        {"name": "LOG_LEVEL", "value": "info"}
      ],
      "secrets": [
        {
          "name": "LLM_API_KEY",
          "valueFrom": "arn:aws:secretsmanager:region:account:secret:openai-api-key"
        },
        {
          "name": "DATABASE_URL",
          "valueFrom": "arn:aws:secretsmanager:region:account:secret:db-connection"
        },
        {
          "name": "PLANNER_API_KEYS",
          "valueFrom": "arn:aws:secretsmanager:region:account:secret:api-keys"
        }
      ],
      "healthCheck": {
        "command": ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://localhost:8000/health').read()\""],
        "interval": 30,
        "timeout": 5,
        "retries": 3,
        "startPeriod": 40
      },
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/software-planner",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "app"
        }
      }
    }
  ],
  "requiresCompatibilities": ["FARGATE"],
  "networkMode": "awsvpc",
  "cpu": "1024",
  "memory": "2048"
}
```

**Service Configuration**:
- Use Application Load Balancer for health checks and routing
- Configure target group with `/health` endpoint
- Set up CloudWatch for logs and metrics
- Use RDS PostgreSQL for managed database
- Store secrets in Secrets Manager

**Deployment Steps**:
1. Push image to ECR: `docker push <ecr-url>/software-planner:v1.0.0`
2. Run migrations: One-off ECS task with `alembic upgrade head`
3. Create/update ECS service with new task definition
4. Monitor deployment in ECS console

#### Heroku

**Deployment Steps**:

1. **Create Heroku app**:
```bash
heroku create software-planner-prod
```

2. **Add PostgreSQL database**:
```bash
heroku addons:create heroku-postgresql:standard-0
```

3. **Set environment variables**:
```bash
heroku config:set \
  LLM_API_KEY=sk-your-api-key \
  WORKERS=4 \
  PLANNER_API_KEYS='["key1","key2"]' \
  PLANNER_API_KEYS_REQUIRED=true \
  ALLOWED_ORIGINS='["https://your-frontend.com"]' \
  CORS_WILDCARD_ENABLED=false
```

4. **Deploy**:
```bash
git push heroku main
```

5. **Run migrations**:
```bash
heroku run alembic upgrade head
```

6. **Scale workers**:
```bash
heroku ps:scale web=2
```

**Procfile** (create in repository root):
```
web: uvicorn app.main:app --host=0.0.0.0 --port=$PORT --workers=${WORKERS:-4}
release: alembic upgrade head
```

**Notes**:
- Heroku automatically sets `PORT` environment variable
- `DATABASE_URL` is automatically configured by Heroku Postgres addon
- Use release phase for automatic migrations on deployment

#### Fly.io

**fly.toml** (create in repository root):

```toml
app = "software-planner"
primary_region = "iad"

[build]
  image = "your-registry/software-planner:latest"

[env]
  PORT = "8000"
  WORKERS = "2"
  LOG_LEVEL = "info"
  PLANNER_METRICS_ENABLED = "true"

[[services]]
  internal_port = 8000
  protocol = "tcp"

  [[services.ports]]
    port = 80
    handlers = ["http"]
    force_https = true

  [[services.ports]]
    port = 443
    handlers = ["tls", "http"]

  [services.concurrency]
    type = "connections"
    hard_limit = 250
    soft_limit = 200

  [[services.tcp_checks]]
    interval = "15s"
    timeout = "2s"
    grace_period = "10s"

  [[services.http_checks]]
    interval = "30s"
    timeout = "5s"
    grace_period = "10s"
    method = "get"
    path = "/health"
    protocol = "http"

[deploy]
  release_command = "alembic upgrade head"
```

**Deployment Steps**:

1. **Install Fly CLI**: https://fly.io/docs/hands-on/install-flyctl/

2. **Create Fly app**:
```bash
fly launch --no-deploy
```

3. **Create PostgreSQL database**:
```bash
fly postgres create --name software-planner-db
fly postgres attach software-planner-db
```

4. **Set secrets**:
```bash
fly secrets set \
  LLM_API_KEY=sk-your-api-key \
  PLANNER_API_KEYS='["key1","key2"]'
```

5. **Deploy**:
```bash
fly deploy
```

6. **Scale instances**:
```bash
fly scale count 2 --region iad,ord
```

**Notes**:
- Fly automatically injects `DATABASE_URL` when attaching Postgres
- Use regions close to your users for better latency
- Fly provides automatic TLS certificates

#### Kubernetes

**Deployment Manifest Example**:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: software-planner
  labels:
    app: software-planner
spec:
  replicas: 3
  selector:
    matchLabels:
      app: software-planner
  template:
    metadata:
      labels:
        app: software-planner
    spec:
      containers:
      - name: app
        image: your-registry/software-planner:v1.0.0
        ports:
        - containerPort: 8000
          name: http
        env:
        - name: PORT
          value: "8000"
        - name: WORKERS
          value: "4"
        - name: LOG_LEVEL
          value: "info"
        - name: PLANNER_TRUST_PROXY_HEADERS
          value: "true"
        - name: LLM_API_KEY
          valueFrom:
            secretKeyRef:
              name: software-planner-secrets
              key: llm-api-key
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: software-planner-secrets
              key: database-url
        - name: PLANNER_API_KEYS
          valueFrom:
            secretKeyRef:
              name: software-planner-secrets
              key: api-keys
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "1000m"
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
        lifecycle:
          preStop:
            exec:
              command: ["sh", "-c", "sleep 15"]
      terminationGracePeriodSeconds: 30
---
apiVersion: v1
kind: Service
metadata:
  name: software-planner
spec:
  selector:
    app: software-planner
  ports:
  - port: 80
    targetPort: 8000
    protocol: TCP
  type: ClusterIP
---
apiVersion: batch/v1
kind: Job
metadata:
  name: software-planner-migrate
spec:
  template:
    spec:
      containers:
      - name: migrate
        image: your-registry/software-planner:v1.0.0
        command: ["alembic", "upgrade", "head"]
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: software-planner-secrets
              key: database-url
      restartPolicy: Never
  backoffLimit: 4
```

**Secret Creation**:

```bash
kubectl create secret generic software-planner-secrets \
  --from-literal=llm-api-key='sk-your-api-key' \
  --from-literal=database-url='postgresql+asyncpg://user:pass@host:5432/db' \
  --from-literal=api-keys='["key1","key2"]'
```

**Deployment Workflow**:

1. Run migration job: `kubectl apply -f migration-job.yaml`
2. Wait for migration completion: `kubectl wait --for=condition=complete job/software-planner-migrate`
3. Deploy application: `kubectl apply -f deployment.yaml`
4. Monitor rollout: `kubectl rollout status deployment/software-planner`

**Ingress Example (with TLS)**:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: software-planner
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
spec:
  tls:
  - hosts:
    - api.example.com
    secretName: software-planner-tls
  rules:
  - host: api.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: software-planner
            port:
              number: 80
```

## Scaling Considerations

### Worker Configuration

The `WORKERS` environment variable controls the number of uvicorn worker processes. Proper configuration is critical for performance.

**CPU-Bound Workloads**:
```bash
WORKERS=<number_of_cpu_cores>
```

**I/O-Bound Workloads** (typical for this API):
```bash
WORKERS=<2_to_4_times_cpu_cores>
```

**Determining Worker Count**:

1. **Start Conservative**: Begin with `WORKERS=1` and monitor performance
2. **Load Test**: Use tools like `wrk` or `locust` to simulate real traffic
3. **Monitor Metrics**: Watch CPU usage, memory, and response times
4. **Increase Gradually**: Add workers until response time stops improving
5. **Watch Memory**: Each worker increases memory usage (~100-200MB per worker)

**Example Resource Calculations**:

| Instance Size | CPU Cores | RAM | Recommended Workers | Expected Memory |
|---------------|-----------|-----|---------------------|-----------------|
| Small | 1 core | 1GB | 1-2 | 200-400MB |
| Medium | 2 cores | 2GB | 2-4 | 400-800MB |
| Large | 4 cores | 4GB | 4-8 | 800MB-1.6GB |
| XLarge | 8 cores | 8GB | 8-16 | 1.6-3.2GB |

**Container Resource Limits**:

```bash
# Docker
docker run --memory=1g --cpus=2.0 \
  -e WORKERS=4 \
  software-planner:latest

# Kubernetes
resources:
  requests:
    memory: "512Mi"
    cpu: "500m"
  limits:
    memory: "1Gi"
    cpu: "2000m"
```

### Rate Limiter Tuning

The rate limiter uses a token bucket algorithm with per-API-key and per-IP tracking.

**Single Instance Configuration**:

```bash
# Allow 100 requests per minute per API key
PLANNER_RATE_LIMIT_MAX_REQUESTS=100
PLANNER_RATE_LIMIT_WINDOW_SECONDS=60
```

**Multi-Instance Configuration** (Important!):

In load-balanced deployments, each instance maintains independent rate limit state. This means:

```
Total Effective Limit = PLANNER_RATE_LIMIT_MAX_REQUESTS × Number of Instances
```

**Example**: With 3 instances and `PLANNER_RATE_LIMIT_MAX_REQUESTS=100`:
- Each instance allows 100 req/min
- Total system allows ~300 req/min (distributed by load balancer)

**Strategies for Multi-Instance Rate Limiting**:

1. **Divide Per-Instance Limit**:
```bash
# Target: 300 req/min total with 3 instances
PLANNER_RATE_LIMIT_MAX_REQUESTS=100  # 100 × 3 = 300 total
```

2. **Use Sticky Sessions** (Session Affinity):
- Configure load balancer to route same API key to same instance
- More accurate per-key limiting
- Uneven load distribution

3. **Implement Distributed Rate Limiting** (Future Enhancement):
- Use Redis or similar shared storage for rate limit state
- Synchronize token buckets across instances
- Requires code changes (not currently implemented)

**Recommendation**: For production with multiple instances, use strategy #1 (divide per-instance limit) or deploy a dedicated API gateway with centralized rate limiting.

### Database Connection Pooling

The application uses asyncpg with connection pooling for efficient database access.

**Default Pool Settings**:
- Min connections: 2
- Max connections: 10
- Pool timeout: 30 seconds

**Tuning for Scale**:

Calculate required connections:
```
Total Connections = Instances × Workers × Pool Size
```

**Example**: 3 instances × 4 workers × 10 pool size = 120 connections

Ensure your PostgreSQL `max_connections` setting accommodates this:

```sql
-- Check current setting
SHOW max_connections;

-- Adjust if needed (requires restart)
ALTER SYSTEM SET max_connections = 200;
```

**Best Practices**:
- Monitor connection pool utilization
- Keep `max_connections` higher than total expected connections
- Consider using PgBouncer for connection pooling at database level
- Each connection consumes ~10MB RAM on PostgreSQL server

### Health and Metrics Endpoints

**Health Check Endpoint**: `/health`

```bash
curl http://localhost:8000/health
# Response: {"status":"ok"}
```

**Use Cases**:
- Load balancer health checks
- Kubernetes liveness/readiness probes
- Monitoring system uptime checks
- Docker container health checks

**Metrics Endpoint**: `/api/v1/metrics`

Enable metrics collection:
```bash
PLANNER_METRICS_ENABLED=true
```

**Available Metrics**:
- `planner_http_requests_total` - Total HTTP requests by endpoint and status
- `planner_http_request_duration_seconds` - Request latency histogram
- `planner_job_status_total` - Total jobs by status (QUEUED, RUNNING, SUCCEEDED, FAILED)
- `planner_job_duration_seconds` - Job processing duration
- `planner_llm_requests_total` - LLM API requests by provider and status
- `planner_llm_request_duration_seconds` - LLM request latency
- `planner_llm_tokens_total` - Token consumption by provider and type

**Prometheus Configuration**:

```yaml
scrape_configs:
  - job_name: 'software-planner'
    scrape_interval: 15s
    static_configs:
      - targets: ['api.example.com:8000']
    metrics_path: '/api/v1/metrics'
```

**⚠️ Security**: Metrics endpoint is NOT protected by API keys. Use network-level restrictions:

```nginx
# Nginx example - restrict to monitoring network
location /api/v1/metrics {
    allow 10.0.0.0/8;      # Internal network
    deny all;
    proxy_pass http://backend;
}
```

**Alerting Examples**:

```yaml
# High job failure rate
- alert: HighJobFailureRate
  expr: rate(planner_job_status_total{status="FAILED"}[5m]) > 0.1
  for: 5m
  annotations:
    summary: "Job failure rate > 10%"

# Slow LLM responses
- alert: SlowLLMResponses
  expr: histogram_quantile(0.95, rate(planner_llm_request_duration_seconds_bucket[5m])) > 30
  for: 10m
  annotations:
    summary: "95th percentile LLM latency > 30s"
```

## Operational Procedures

### API Key Rotation

Rotate API keys without service interruption using a phased approach:

**Step 1: Add New Keys** (No Downtime)

```bash
# Current keys
PLANNER_API_KEYS='["old-key-1","old-key-2"]'

# Add new keys alongside old
PLANNER_API_KEYS='["old-key-1","old-key-2","new-key-1","new-key-2"]'
```

Deploy with updated configuration. Both old and new keys are now valid.

**Step 2: Migrate Clients** (Gradual)

Update client applications to use new keys. Monitor logs to verify new keys are being used:

```bash
# Check key usage in logs
grep "api_key_hash" application.log | sort | uniq -c
```

**Step 3: Remove Old Keys** (After Migration Complete)

Once all clients use new keys, remove old keys:

```bash
PLANNER_API_KEYS='["new-key-1","new-key-2"]'
```

Deploy with updated configuration.

**Rollback Plan**: If clients start failing with 403 errors, immediately redeploy with old keys re-added.

**Key Generation Best Practices**:

```bash
# Generate cryptographically secure keys
openssl rand -hex 32
# or
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Minimum length: 32 characters recommended
PLANNER_API_KEY_MIN_LENGTH=32
```

**⚠️ Security During Key Rotation**:
- **Avoid logging keys**: Ensure new keys are not logged during configuration updates or rollouts
- **Use secrets management**: Never set keys via command-line arguments (visible in process lists)
- **Audit access**: Track who has access to API keys and when they are updated
- **Monitoring**: Watch for authentication failures that might indicate key mismatches during rotation
- **Secure communication**: Only transmit keys over encrypted channels (HTTPS, SSH, encrypted secrets stores)

### Database Credential Rotation

Rotate database credentials without downtime:

**Step 1: Create New Database User**

```sql
-- Create new user with identical permissions
CREATE USER planner_app_new WITH PASSWORD 'NEW_SECURE_PASSWORD';
GRANT SELECT, INSERT, UPDATE ON TABLE jobs TO planner_app_new;
GRANT SELECT ON TABLE alembic_version TO planner_app_new;
```

**Step 2: Update Application Configuration**

Update `DATABASE_URL` or `DATABASE_PASSWORD` with new credentials:

```bash
# Old
DATABASE_URL=postgresql+asyncpg://planner_app:old_pass@host:5432/db

# New
DATABASE_URL=postgresql+asyncpg://planner_app_new:NEW_SECURE_PASSWORD@host:5432/db
```

**Step 3: Rolling Deployment**

- **Kubernetes**: Rolling update automatically (one pod at a time)
- **Docker Swarm**: `docker service update --force`
- **ECS**: Update task definition, new tasks use new credentials
- **Manual**: Blue-green deployment or rolling restart

**Step 4: Verify New Instances**

Check logs for successful database connections:

```bash
kubectl logs -l app=software-planner --tail=50 | grep "Database"
```

**Step 5: Remove Old User** (After Full Rollout)

```sql
-- Wait 24-48 hours for all old connections to drain
-- Verify no connections using old user:
SELECT COUNT(*) FROM pg_stat_activity WHERE usename = 'planner_app';

-- Drop old user
DROP USER planner_app;
```

**Emergency Rollback**: Revert `DATABASE_URL` and redeploy.

### Handling Database Connectivity Failures

The application will fail to start if the database is unreachable. This fail-fast behavior prevents degraded state.

**Startup Behavior**:

1. Application attempts to initialize database connection pool
2. If connection fails, logs detailed error and exits with non-zero code
3. Container orchestration systems detect failure and restart

**Expected Error Logs**:

```
ERROR: Database connection failed: could not connect to server: Connection refused
ERROR: Please verify database configuration and ensure PostgreSQL is running
ERROR: DATABASE_URL=postgresql+asyncpg://user@localhost:5432/software_planner
```

**Troubleshooting Steps**:

1. **Verify Database is Running**:
```bash
pg_isready -h db.example.com -p 5432
```

2. **Check Connection Settings**:
```bash
# Print current DATABASE_URL (redact password)
echo $DATABASE_URL | sed 's/:\/\/[^:]*:[^@]*@/:\/\/user:***@/'
```

3. **Test Network Connectivity**:
```bash
telnet db.example.com 5432
# or
nc -zv db.example.com 5432
```

4. **Verify Database Exists**:
```bash
psql -h db.example.com -U postgres -l
```

5. **Check User Permissions**:
```sql
-- Connect as superuser
psql -U postgres -d software_planner

-- Check user privileges
\du planner_app

-- Verify table access
SELECT COUNT(*) FROM jobs;
```

**Production Recommendations**:

- **Health Checks**: Configure orchestration to detect startup failures
- **Retry Logic**: Use restart policies with exponential backoff
- **Alerts**: Monitor repeated startup failures
- **Dependencies**: Ensure database starts before application

**Kubernetes Example**:

```yaml
spec:
  template:
    spec:
      initContainers:
      - name: wait-for-db
        image: postgres:17
        command: ['sh', '-c', 'until pg_isready -h db-host -p 5432; do echo waiting for database; sleep 2; done;']
      containers:
      - name: app
        image: software-planner:latest
        # ... rest of configuration
```

### Migration Management

Database migrations must be run before deploying new application versions.

**Migration Workflow** (Recommended):

```mermaid
graph LR
    A[Build New Image] --> B[Run Migration Job]
    B --> C{Success?}
    C -->|Yes| D[Deploy New Version]
    C -->|No| E[Rollback/Fix]
    D --> F[Verify Application]
    F --> G{Healthy?}
    G -->|Yes| H[Complete]
    G -->|No| I[Rollback Deployment]
```

**Running Migrations**:

**Docker**:
```bash
docker run --rm \
  -e DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db \
  software-planner:v1.0.0 \
  sh -c "alembic upgrade head"
```

**Kubernetes Job**:
```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: migrate-v1.0.0
spec:
  template:
    spec:
      containers:
      - name: migrate
        image: software-planner:v1.0.0
        command: ["alembic", "upgrade", "head"]
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: db-credentials
              key: url
      restartPolicy: Never
```

**ECS Task**:
```bash
aws ecs run-task \
  --cluster production \
  --task-definition software-planner-migrate:1 \
  --count 1
```

**Verifying Migrations**:

```bash
# Check current schema version
alembic current

# View migration history
alembic history

# Verify tables exist
psql -d software_planner -c "\dt"
```

**Migration Safety Checklist**:

- [ ] Backup database before running migrations
- [ ] Test migrations in staging environment first
- [ ] Verify migration can run with application user permissions (not superuser)
- [ ] Monitor migration logs for errors
- [ ] Verify schema with `alembic current` after migration
- [ ] Test application functionality after migration
- [ ] Have rollback plan ready (downgrade script)

**Rollback Process**:

```bash
# View current version
alembic current

# Rollback to previous version
alembic downgrade -1

# Or rollback to specific version
alembic downgrade <revision_id>

# Verify rollback
alembic current
```

**Zero-Downtime Migration Strategy**:

1. **Backward Compatible Changes Only**:
   - Add columns with defaults (don't remove columns)
   - Add indexes (use `CONCURRENTLY` in PostgreSQL)
   - Add tables (don't drop tables)

2. **Multi-Phase Deployments**:
   - **Phase 1**: Deploy schema changes (additive only)
   - **Phase 2**: Deploy application using new schema
   - **Phase 3**: Clean up deprecated columns/tables (weeks later)

3. **Blue-Green Database Strategy** (for major changes):
   - Create new database with updated schema
   - Replicate data from old to new database
   - Switch application to new database
   - Keep old database as rollback option

### Zero-Downtime Deployments

Achieve zero-downtime deployments with graceful shutdown and rolling updates.

**Graceful Shutdown Configuration**:

**Kubernetes PreStop Hook**:
```yaml
lifecycle:
  preStop:
    exec:
      # Wait for in-flight requests to complete
      # Adjust duration based on typical request time
      command: ["sh", "-c", "sleep 15"]

# Ensure grace period exceeds preStop sleep
terminationGracePeriodSeconds: 30
```

**Health Checks**:
```yaml
# Liveness: Restart if unhealthy
livenessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 10
  failureThreshold: 3

# Readiness: Stop routing traffic if not ready
readinessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 5
  failureThreshold: 2
```

**Rolling Update Strategy**:
```yaml
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxSurge: 1        # New pods before old ones terminate
    maxUnavailable: 0  # Ensure capacity during rollout
```

**Deployment Process**:

1. **Pre-Deployment**:
   - Run database migrations (if any)
   - Build and tag new image
   - Push image to registry
   - Update secrets if needed

2. **Deploy**:
   ```bash
   # Kubernetes
   kubectl set image deployment/software-planner \
     app=software-planner:v1.0.0
   
   # Monitor rollout
   kubectl rollout status deployment/software-planner
   ```

3. **Verification**:
   - Check pod status: All running and ready
   - Test health endpoint on new pods
   - Monitor error rates in logs/metrics
   - Verify job creation and processing

4. **Rollback** (if needed):
   ```bash
   kubectl rollout undo deployment/software-planner
   ```

**Load Balancer Configuration**:

- **Connection Draining**: 30-60 seconds to allow in-flight requests to complete
- **Health Check**: `/health` endpoint with 5-10 second interval
- **Deregistration Delay**: Match connection draining duration

**Example (AWS ALB)**:
```json
{
  "TargetGroupAttributes": [
    {
      "Key": "deregistration_delay.timeout_seconds",
      "Value": "30"
    },
    {
      "Key": "stickiness.enabled",
      "Value": "false"
    }
  ]
}
```

**Monitoring During Deployment**:

Watch these metrics during rollout:
- Error rate (should remain low)
- Request latency (should not spike)
- Job failure rate (should remain stable)
- Active connections (should drain from old pods)

**Rollback Decision Criteria**:

Rollback immediately if:
- Error rate > 5% for > 2 minutes
- New pods fail health checks repeatedly
- Job processing failures spike
- Database connection errors appear

## CI/CD Integration

The Software Planner uses GitHub Actions for continuous integration and deployment.

### CI Pipeline Overview

The CI pipeline ensures code quality and functionality before deployment:

```mermaid
graph LR
    A[Push/PR] --> B[Lint]
    A --> C[Type Check]
    A --> D[Test]
    B --> E{All Pass?}
    C --> E
    D --> E
    E -->|Yes| F[Build Docker Image]
    E -->|No| G[Block Merge]
    F --> H[Push to Registry]
    H --> I[Deploy to Staging]
    I --> J[Integration Tests]
    J --> K{Tests Pass?}
    K -->|Yes| L[Ready for Production]
    K -->|No| M[Rollback Staging]
```

### CI Workflow Stages

The CI workflow defined in `.github/workflows/ci.yml` includes three parallel jobs:

**1. Lint Job**:
- Runs code quality checks with flake8, black, and isort
- Ensures consistent code style
- Fast feedback (< 2 minutes)
- Blocking: PR cannot merge if linting fails

**2. Type Check Job**:
- Runs mypy type checker
- Informational only (does not block merges)
- Helps catch type-related bugs
- Lenient settings for gradual adoption

**3. Test Job**:
- Runs full test suite with pytest
- Includes database setup (PostgreSQL 17)
- Runs database migrations before tests
- Blocking: PR cannot merge if tests fail
- Typical duration: 5-10 minutes

**CI Environment**:
- Python 3.10
- PostgreSQL 17 (service container)
- Dependencies cached for speed
- Runs on Ubuntu latest

### Build and Tag Strategy

**Image Tagging Convention**:

```bash
# Production tags (use exact semantic versions for deployments)
software-planner:v1.0.0          # Semantic version - USE THIS FOR PRODUCTION

# Development/Reference tags (DO NOT use for production deployments)
software-planner:v1.0            # Minor version alias - reference only
software-planner:v1              # Major version alias - reference only
software-planner:latest          # Latest stable - reference only, can change
software-planner:main-abc123     # Main branch commit SHA
software-planner:pr-456-def789   # PR branch commit SHA
software-planner:staging         # Staging environment
```

**⚠️ Production Deployment Best Practice**: Always use exact semantic version tags (e.g., `v1.0.0`) in production. Never use `latest`, major (`v1`), or minor (`v1.0`) aliases as these can point to different images over time, leading to unexpected updates and breaking zero-downtime deployment practices.

**Building Images in CI**:

```yaml
# Example GitHub Actions workflow (add to .github/workflows/ci.yml)
- name: Build Docker image
  run: |
    docker build -t software-planner:${{ github.sha }} .
    
- name: Tag image
  run: |
    # Tag with semantic version on release (PRODUCTION USE ONLY)
    if [[ "${{ github.ref }}" == refs/tags/v* ]]; then
      VERSION=${GITHUB_REF#refs/tags/}
      docker tag software-planner:${{ github.sha }} software-planner:${VERSION}
      # Note: 'latest' tag is for convenience in development/testing
      # DO NOT USE 'latest' tag in production deployments
      docker tag software-planner:${{ github.sha }} software-planner:latest
    fi
    
    # Tag with branch name (development/staging use)
    if [[ "${{ github.ref }}" == refs/heads/main ]]; then
      docker tag software-planner:${{ github.sha }} software-planner:main
    fi
```

**⚠️ Important**: The `latest` tag shown above is created for development convenience but should **never** be used in production deployments. Always use exact semantic version tags (e.g., `v1.0.0`) in production to ensure predictable, repeatable deployments.

### Artifact Promotion

**Development → Staging → Production**:

```mermaid
graph LR
    A[Dev Build] -->|Pass Tests| B[Tag as Staging]
    B -->|Deploy to Staging| C[Staging Tests]
    C -->|Pass| D[Tag as Production]
    D -->|Manual Approval| E[Deploy to Prod]
    E --> F[Production Monitoring]
```

**Promotion Workflow**:

1. **Development**:
   - Every commit to `main` builds image tagged with commit SHA
   - Automatically deploys to dev environment
   - No manual approval required

2. **Staging**:
   - Tag passing dev builds for staging: `docker tag dev-abc123 staging`
   - Automatically deploy to staging environment
   - Run integration/smoke tests
   - Monitor for 1-4 hours

3. **Production**:
   - Tag stable staging builds: `docker tag staging v1.0.0`
   - Require manual approval (GitHub Environment protection rules)
   - Run database migrations
   - Deploy with rolling update strategy
   - Monitor closely for 24 hours

**GitHub Environment Setup**:

```yaml
# .github/workflows/deploy.yml
jobs:
  deploy-production:
    environment:
      name: production
      url: https://api.example.com
    steps:
      - name: Deploy to production
        run: |
          kubectl set image deployment/software-planner \
            app=software-planner:${{ github.event.inputs.version }}
```

Configure environment protection rules in GitHub:
- Required reviewers: 1-2 team members
- Wait timer: 5 minutes (to prevent accidental deployments)
- Restrict to protected branches: `main` only

### Pre-Deployment Testing Requirements

**Required Tests Before Deployment**:

1. **Unit Tests** (100+ tests):
   - Models, services, utilities
   - Mocked external dependencies (database, LLM)
   - Fast execution (< 30 seconds)

2. **Integration Tests**:
   - Real database connections (PostgreSQL test instance)
   - API endpoint tests (full request/response cycle)
   - Job lifecycle tests (QUEUED → RUNNING → SUCCEEDED/FAILED)

3. **Database Migration Tests**:
   - Apply migrations to empty database
   - Verify schema correctness
   - Test rollback (downgrade) functionality

4. **Container Health Tests**:
   - Build Docker image
   - Start container with test configuration
   - Verify health endpoint responds
   - Check application logs for errors

**Staging Environment Tests**:

```bash
# Health check
curl https://staging-api.example.com/health

# Create test job
curl -X POST https://staging-api.example.com/api/v1/plans \
  -H "Content-Type: application/json" \
  -H "X-API-Key: staging-key" \
  -d '{"description":"test deployment"}'

# Verify job processing
curl https://staging-api.example.com/api/v1/plans/{job_id}

# Check metrics
curl https://staging-api.example.com/api/v1/metrics | grep planner_job
```

**Automated Smoke Tests** (add to CI):

```python
# tests/smoke_test.py
import requests

def test_staging_health():
    response = requests.get("https://staging-api.example.com/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_staging_job_creation():
    response = requests.post(
        "https://staging-api.example.com/api/v1/plans",
        json={"description": "test"},
        headers={"X-API-Key": "staging-key"}
    )
    assert response.status_code == 202
    assert "job_id" in response.json()
```

### CI/CD Best Practices

1. **Fail Fast**:
   - Run quick tests (lint, unit tests) first
   - Run slow tests (integration) only if quick tests pass
   - Parallel execution where possible

2. **Environment Parity**:
   - Use same base image for all environments
   - Identical PostgreSQL versions in CI and production
   - Same Python version across all stages

3. **Secrets Management**:
   - Never commit secrets to repository
   - Use GitHub Secrets for CI/CD credentials
   - Rotate secrets regularly

4. **Monitoring and Rollback**:
   - Monitor error rates during deployment
   - Automated rollback if error rate exceeds threshold
   - Keep previous 3-5 versions in registry for quick rollback

5. **Documentation**:
   - Update CHANGELOG.md with each release
   - Document breaking changes prominently
   - Include migration instructions for major versions

## Troubleshooting

### Common Issues and Solutions

#### Container Fails to Start

**Symptom**: Container exits immediately after starting

**Causes and Solutions**:

1. **Missing Required Environment Variables**:
```bash
# Check logs
docker logs software-planner

# Look for error like:
# ERROR: LLM_API_KEY is required

# Fix: Set missing variable
docker run -e LLM_API_KEY=sk-your-key ...
```

2. **Database Connection Failed**:
```bash
# Error: "Database connection failed"
# Fix: Verify DATABASE_URL is correct and database is accessible
docker run -e DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db ...
```

3. **Port Already in Use**:
```bash
# Error: "Address already in use"
# Fix: Use different host port
docker run -p 8080:8000 ...  # Map to host port 8080
```

#### High Memory Usage

**Symptom**: Container OOM killed or high memory consumption

**Causes and Solutions**:

1. **Too Many Workers**:
```bash
# Each worker uses ~100-200MB
# Reduce workers if memory constrained
WORKERS=2  # Instead of 8
```

2. **Large Job Payloads**:
```bash
# Limit description size
PLANNER_REQUEST_DESCRIPTION_MAX_CHARS=10000  # Reduce from 50000
```

3. **Connection Pool Too Large**:
```bash
# Reduce database connection pool
# (Requires code change - not currently configurable)
# Alternative: Increase container memory limit
docker run --memory=1g ...
```

#### Slow Response Times

**Symptom**: API requests take > 5 seconds

**Causes and Solutions**:

1. **Insufficient Workers**:
```bash
# Increase worker count
WORKERS=4  # Match CPU core count
```

2. **Database Connection Pool Exhausted**:
```bash
# Check logs for "connection pool exhausted"
# Increase pool size (requires code change)
# Alternative: Add more application instances
```

3. **LLM API Timeout/Rate Limiting**:
```bash
# Check logs for "LLM request failed: timeout"
# Increase timeout
LLM_TIMEOUT=120

# Check OpenAI account rate limits
# Upgrade OpenAI plan if needed
```

4. **Network Latency to Database**:
```bash
# Measure latency
psql -h db.example.com -U user -c "SELECT 1" --timing

# Move database closer to application (same region/AZ)
# Use managed database in same cloud provider/region
```

#### Job Processing Failures

**Symptom**: Jobs stuck in QUEUED or fail immediately

**Causes and Solutions**:

1. **Invalid LLM API Key**:
```bash
# Error in logs: "OpenAI authentication failed"
# Fix: Verify API key is valid
# Check at https://platform.openai.com/api-keys
LLM_API_KEY=sk-your-valid-key
```

2. **OpenAI Rate Limits Exceeded**:
```bash
# Error: "Rate limit exceeded"
# Solutions:
# - Wait and retry
# - Upgrade OpenAI plan
# - Reduce request volume
```

3. **Jobs Marked Failed After Restart**:
```bash
# Expected behavior: RUNNING jobs fail on restart
# Solution: Resubmit failed jobs manually
# Future: Implement persistent queue for restart recovery
```

#### Rate Limiting Issues

**Symptom**: Clients receive 429 errors unexpectedly

**Causes and Solutions**:

1. **Multiple Clients Sharing API Key**:
```bash
# Rate limit is per API key
# Solution: Issue separate keys per client
PLANNER_API_KEYS='["client1-key","client2-key","client3-key"]'
```

2. **Multi-Instance Amplification**:
```bash
# With 5 instances and limit=10, effective limit is ~50
# Solution: Divide configured limit by instance count
PLANNER_RATE_LIMIT_MAX_REQUESTS=2  # 2 × 5 instances = 10 total
```

3. **Load Balancer Not Preserving IP**:
```bash
# Rate limiting by IP ineffective without X-Forwarded-For
# Solution: Trust proxy headers
PLANNER_TRUST_PROXY_HEADERS=true
```

### Getting Help

**Before Opening an Issue**:

1. Check application logs:
```bash
docker logs software-planner
# or
kubectl logs -l app=software-planner --tail=100
```

2. Verify configuration:
```bash
# List environment variables (redact secrets!)
docker exec software-planner env | grep -E 'PORT|WORKERS|DATABASE|LLM'
```

3. Test connectivity:
```bash
# Database
docker exec software-planner pg_isready -h db-host -p 5432

# Health endpoint
curl http://localhost:8000/health
```

4. Review this documentation and README.md

**Opening an Issue**:

Include:
- Software Planner version (image tag)
- Deployment platform (Docker, Kubernetes, ECS, etc.)
- Relevant logs (redact secrets!)
- Configuration (redact secrets!)
- Steps to reproduce
- Expected vs actual behavior

**Support Channels**:

- GitHub Issues: Bug reports and feature requests
- Discussions: Questions and community support

---

## Appendix: Quick Reference

### Essential Commands

```bash
# Build image
docker build -t software-planner:latest .

# Run with minimal config
docker run -p 8000:8000 \
  -e LLM_API_KEY=sk-key \
  -e DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db \
  software-planner:latest

# Run migrations
docker run --rm -e DATABASE_URL=... \
  software-planner:latest \
  sh -c "alembic upgrade head"

# Start with Docker Compose
make compose-up

# Check health
curl http://localhost:8000/health

# View metrics
curl http://localhost:8000/api/v1/metrics
```

### Environment Variable Quick Reference

**Minimal Configuration**:
```bash
LLM_API_KEY=sk-your-openai-api-key
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db
```

**Production Configuration**:
```bash
# Required
LLM_API_KEY=sk-your-openai-api-key
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db
PLANNER_API_KEYS='["key1","key2"]'
PLANNER_API_KEYS_REQUIRED=true

# Recommended
WORKERS=4
PLANNER_RATE_LIMIT_MAX_REQUESTS=100
ALLOWED_ORIGINS='["https://app.example.com"]'
CORS_WILDCARD_ENABLED=false
PLANNER_METRICS_ENABLED=true
LOG_LEVEL=info
```

### Resource Requirements

| Environment | CPU | Memory | Disk | Workers |
|-------------|-----|--------|------|---------|
| Development | 1 core | 512MB | 1GB | 1 |
| Staging | 2 cores | 1GB | 5GB | 2-4 |
| Production (Small) | 2 cores | 2GB | 10GB | 4 |
| Production (Medium) | 4 cores | 4GB | 20GB | 8 |
| Production (Large) | 8 cores | 8GB | 50GB | 16 |

**Database**: PostgreSQL 12+ with 2-4x application resources

### Port Reference

| Port | Service | Purpose |
|------|---------|---------|
| 8000 | API Server | HTTP API endpoints (configurable via PORT) |
| 5432 | PostgreSQL | Database connections (standard PostgreSQL) |

### Health Check Endpoints

| Endpoint | Method | Purpose | Auth Required |
|----------|--------|---------|---------------|
| `/health` | GET | Liveness/readiness check | No |
| `/api/v1/metrics` | GET | Prometheus metrics | No (use network restrictions) |
| `/api/v1/docs` | GET | OpenAPI documentation | No |
