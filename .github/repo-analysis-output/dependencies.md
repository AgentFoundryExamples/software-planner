# Dependency Graph

Multi-language intra-repository dependency analysis.

Supports Python, JavaScript/TypeScript, C/C++, Rust, Go, Java, C#, Swift, HTML/CSS, and SQL.

Includes classification of external dependencies as stdlib vs third-party.

## Statistics

- **Total files**: 63
- **Intra-repo dependencies**: 133
- **External stdlib dependencies**: 35
- **External third-party dependencies**: 52

## External Dependencies

### Standard Library / Core Modules

Total: 35 unique modules

- `abc.ABC`
- `abc.abstractmethod`
- `asyncio`
- `concurrent.futures.ThreadPoolExecutor`
- `datetime.datetime`
- `datetime.timezone`
- `functools.cached_property`
- `hashlib`
- `importlib.reload`
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
- ... and 15 more (see JSON for full list)

### Third-Party Packages

Total: 52 unique packages

- `alembic.context`
- `alembic.op`
- `anthropic`
- `anthropic.Anthropic`
- `fastapi.`
- `fastapi.APIRouter`
- `fastapi.BackgroundTasks`
- `fastapi.Depends`
- `fastapi.FastAPI`
- `fastapi.HTTPException`
- `fastapi.Header`
- `fastapi.Query`
- `fastapi.Request`
- `fastapi.Response`
- `fastapi.exceptions.RequestValidationError`
- `fastapi.middleware.cors.CORSMiddleware`
- `fastapi.responses.JSONResponse`
- `fastapi.status`
- `fastapi.testclient.TestClient`
- `google.genai`
- ... and 32 more (see JSON for full list)

## Most Depended Upon Files (Intra-Repo)

- `app/core/config.py` (23 dependents)
- `app/services/llm_client.py` (12 dependents)
- `app/main.py` (12 dependents)
- `app/services/store_singleton.py` (8 dependents)
- `app/services/metrics.py` (8 dependents)
- `app/models/job.py` (7 dependents)
- `app/services/job_store.py` (7 dependents)
- `app/services/rate_limiter.py` (7 dependents)
- `app/services/job_repository.py` (6 dependents)
- `app/services/model_registry.py` (6 dependents)

## Files with Most Dependencies (Intra-Repo)

- `app/api/routes.py` (12 dependencies)
- `app/main.py` (6 dependencies)
- `app/services/planner.py` (6 dependencies)
- `app/services/store_singleton.py` (6 dependencies)
- `app/services/llm_client.py` (5 dependencies)
- `tests/test_authentication.py` (5 dependencies)
- `tests/test_plans_async_endpoint.py` (5 dependencies)
- `tests/test_rate_limiting_security.py` (5 dependencies)
- `app/services/job_repository.py` (4 dependencies)
- `tests/test_models_endpoint.py` (4 dependencies)
