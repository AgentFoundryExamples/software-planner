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

#### POST /api/v1/plans

Create an asynchronous planning job that executes in the background.

**Example using curl:**
```bash
curl -X POST http://localhost:8000/api/v1/plans \
  -H "Content-Type: application/json" \
  -d '{"description": "Build a REST API for managing tasks"}'
```

**Request Body:**
```json
{
  "description": "Build a REST API for managing tasks"
}
```

**Success Response (202 Accepted):**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending"
}
```

Use the returned `job_id` to poll for results using the GET endpoints below.

**Error Responses:**
- `400 Bad Request`: Empty, whitespace-only, or oversized description
- `422 Unprocessable Entity`: Malformed JSON or missing required fields

#### GET /api/v1/plans/{job_id}

Get the status and result of a specific planning job.

**Example using curl:**
```bash
curl http://localhost:8000/api/v1/plans/550e8400-e29b-41d4-a716-446655440000
```

**Success Response (200 OK) - Pending Job:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "created_at": "2025-01-01T12:00:00Z",
  "updated_at": "2025-01-01T12:00:00Z",
  "result": null
}
```

**Success Response (200 OK) - Succeeded Job:**
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

**Success Response (200 OK) - Failed Job:**
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

**Error Responses:**
- `404 Not Found`: Job not found or expired

#### GET /api/v1/plans

List recent planning jobs sorted by most recently updated.

**Example using curl:**
```bash
# List with default limit
curl http://localhost:8000/api/v1/plans

# List with custom limit
curl "http://localhost:8000/api/v1/plans?limit=10"
```

**Query Parameters:**
- `limit` (optional): Maximum number of jobs to return (default: 100, max: 1000)

**Success Response (200 OK):**
```json
{
  "jobs": [
    {
      "job_id": "550e8400-e29b-41d4-a716-446655440000",
      "status": "succeeded",
      "created_at": "2025-01-01T12:00:00Z",
      "updated_at": "2025-01-01T12:00:05Z",
      "result": {
        "specs": [{"purpose": "Example"}]
      }
    },
    {
      "job_id": "660e8400-e29b-41d4-a716-446655440001",
      "status": "pending",
      "created_at": "2025-01-01T11:55:00Z",
      "updated_at": "2025-01-01T11:55:00Z",
      "result": null
    }
  ],
  "total": 2,
  "limit": 100
}
```

**Error Responses:**
- `422 Unprocessable Entity`: Invalid limit parameter (must be >= 1)

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
│       └── planner.py       # Planning service with hard-coded logic
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
