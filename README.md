# Software Planner API

A FastAPI-based software planning service with a modular, extensible architecture.

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

**Validation:**
- If you specify an unknown model name, you'll get a 400 Bad Request error listing available models
- If you specify a disabled model, you'll get a 400 Bad Request error
- System prompts must not exceed 32768 bytes

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
      ]
    }
  ]
}
```

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
        "nice": ["Add rate limiting"]
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

#### How It Works

When you submit a planning request via the asynchronous API (`POST /api/v1/plans`), the system:

1. **Creates a Job**: Immediately returns a job ID and sets status to `pending`
2. **Queues the Request**: A background worker picks up the job and sets status to `running`
3. **Calls the LLM**: The planner service sends your description to the configured LLM model along with a system prompt that defines the expected JSON structure
4. **Retries on Failure**: Implements automatic retry logic with exponential backoff for transient errors (timeouts, rate limits, 5xx server errors)
5. **Validates Response**: Parses and validates the LLM's JSON response against the expected schema
6. **Normalizes Data**: Handles edge cases like single-spec objects, oversized fields, and whitespace
7. **Updates Job**: Sets status to `succeeded` with results, or `failed` with error details

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
  - Advanced users only - improper prompts may break response parsing

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

The LLM integration requires the official OpenAI Python SDK:

```bash
pip install openai==2.14.0
```

This is included in `requirements.txt` and will be installed automatically. The implementation uses:
- **OpenAI Responses API** (recommended for GPT-5+ models, replacing Chat Completions API)
- **Automatic retry logic** for transient failures
- **Structured logging** without exposing API keys

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

**Warning**: Custom prompts may break response parsing if they don't enforce valid JSON output matching the expected schema. Test thoroughly before deploying custom prompts.

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
  "api_key_hash": "a1b2c3d4e5f6g7h8"
}
```

**Security Considerations:**

- **API Keys**: Never logged in plain text. Only hashed identifiers (first 16 chars of SHA-256) are logged
- **Prompts**: Project descriptions and system prompts are never logged to prevent data leakage
- **Secrets**: Database passwords, LLM API keys, and other secrets are never included in logs
- **Token Counts**: Only aggregate counts are logged, not actual token content

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
