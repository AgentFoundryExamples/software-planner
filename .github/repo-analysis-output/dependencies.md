# Dependency Graph

Multi-language intra-repository dependency analysis.

Supports Python, JavaScript/TypeScript, C/C++, Rust, Go, Java, C#, Swift, HTML/CSS, and SQL.

Includes classification of external dependencies as stdlib vs third-party.

## Statistics

- **Total files**: 57
- **Intra-repo dependencies**: 115
- **External stdlib dependencies**: 34
- **External third-party dependencies**: 45

## External Dependencies

### Standard Library / Core Modules

Total: 34 unique modules

- `abc.ABC`
- `abc.abstractmethod`
- `asyncio`
- `concurrent.futures.ThreadPoolExecutor`
- `datetime.datetime`
- `datetime.timezone`
- `functools.cached_property`
- `hashlib`
- `json`
- `logging`
- `logging.config.fileConfig`
- `math`
- `os`
- `pathlib.Path`
- `random`
- `re`
- `secrets`
- `subprocess`
- `threading`
- `threading.Lock`
- ... and 14 more (see JSON for full list)

### Third-Party Packages

Total: 45 unique packages

- `alembic.context`
- `alembic.op`
- `anthropic`
- `anthropic.Anthropic`
- `fastapi.APIRouter`
- `fastapi.BackgroundTasks`
- `fastapi.Depends`
- `fastapi.FastAPI`
- `fastapi.HTTPException`
- `fastapi.Header`
- `fastapi.Query`
- `fastapi.Request`
- `fastapi.exceptions.RequestValidationError`
- `fastapi.middleware.cors.CORSMiddleware`
- `fastapi.responses.JSONResponse`
- `fastapi.status`
- `fastapi.testclient.TestClient`
- `google.genai`
- `google.genai.types`
- `openai`
- ... and 25 more (see JSON for full list)

## Most Depended Upon Files (Intra-Repo)

- `app/core/config.py` (21 dependents)
- `app/services/llm_client.py` (12 dependents)
- `app/main.py` (11 dependents)
- `app/services/store_singleton.py` (8 dependents)
- `app/models/job.py` (7 dependents)
- `app/services/job_store.py` (7 dependents)
- `app/services/job_repository.py` (6 dependents)
- `app/services/model_registry.py` (6 dependents)
- `app/services/rate_limiter.py` (6 dependents)
- `app/services/llm_openai.py` (5 dependents)

## Files with Most Dependencies (Intra-Repo)

- `app/api/routes.py` (11 dependencies)
- `app/services/planner.py` (6 dependencies)
- `app/services/store_singleton.py` (6 dependencies)
- `tests/test_plans_async_endpoint.py` (6 dependencies)
- `app/main.py` (5 dependencies)
- `app/services/llm_client.py` (5 dependencies)
- `tests/test_rate_limiting_security.py` (5 dependencies)
- `tests/test_authentication.py` (4 dependencies)
- `tests/test_models_endpoint.py` (4 dependencies)
- `tests/test_plans_polling_endpoints.py` (4 dependencies)
