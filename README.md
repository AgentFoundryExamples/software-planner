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

> **Note:** Jobs are stored in-memory only and will be lost on server restart. See the "Known Limitations" section below for details.

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

1. **In-Memory Storage Only**: Jobs are stored in memory and will be **lost on server restart**. Do not rely on job persistence across deployments.

2. **Process Lifetime**: Jobs exist only for the lifetime of the current server process. There is no database or persistent storage.

3. **No Cancellation**: Once a job is created, it cannot be cancelled. It will run to completion (succeeded or failed state).

4. **No Durability Guarantees**: The system does not provide durability guarantees beyond the current process.

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

- `LLM_MODEL`: Model identifier (default: "gpt-4", recommended: "gpt-5.1")
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

# Optional: Use GPT-5.1 for better results
LLM_MODEL=gpt-5.1

# Optional: Increase timeout for complex projects
LLM_TIMEOUT=90

# Optional: Custom system prompt (advanced)
# LLM_SYSTEM_PROMPT=Your custom prompt here...
```

#### Getting Your OpenAI API Key

1. Sign up or log in to OpenAI Platform: https://platform.openai.com/
2. Navigate to API Keys: https://platform.openai.com/api-keys
3. Click "Create new secret key"
4. Copy the key immediately (you won't see it again)
5. Add it to your `.env` file as `LLM_API_KEY=sk-...`

**Important**: 
- Keep your API key secure - never share it or commit it to Git
- Set usage limits on your OpenAI account to prevent unexpected charges
- Monitor your API usage in the OpenAI dashboard

#### Dependencies

The LLM integration requires the official OpenAI Python SDK:

```bash
pip install openai==2.14.0
```

This is included in `requirements.txt` and will be installed automatically. The implementation uses:
- **OpenAI Chat Completions API** (recommended, not deprecated Completions API)
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

#### How Errors Surface

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

**Via Application Logs**:

The planner logs detailed information at various levels:

- **INFO**: Request metadata (model, description length, retry attempts, latency)
- **WARNING**: Non-fatal issues (empty `must` fields, oversized responses being truncated)
- **ERROR**: Failures (authentication, timeout, validation errors) with sanitized error messages

**Security Note**: API keys are never logged. Logs contain only metadata and error types, not sensitive credentials or full response content.

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
