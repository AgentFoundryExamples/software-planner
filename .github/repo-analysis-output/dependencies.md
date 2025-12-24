# Dependency Graph

Multi-language intra-repository dependency analysis.

Supports Python, JavaScript/TypeScript, C/C++, Rust, Go, Java, C#, Swift, HTML/CSS, and SQL.

Includes classification of external dependencies as stdlib vs third-party.

## Statistics

- **Total files**: 44
- **Intra-repo dependencies**: 82
- **External stdlib dependencies**: 30
- **External third-party dependencies**: 41

## External Dependencies

### Standard Library / Core Modules

Total: 30 unique modules

- `abc.ABC`
- `abc.abstractmethod`
- `asyncio`
- `concurrent.futures.ThreadPoolExecutor`
- `datetime.datetime`
- `datetime.timezone`
- `hashlib`
- `json`
- `logging`
- `logging.config.fileConfig`
- `os`
- `pathlib.Path`
- `random`
- `re`
- `subprocess`
- `threading`
- `threading.Lock`
- `time`
- `typing.Any`
- `typing.Dict`
- ... and 10 more (see JSON for full list)

### Third-Party Packages

Total: 41 unique packages

- `alembic.context`
- `alembic.op`
- `anthropic`
- `anthropic.Anthropic`
- `fastapi.APIRouter`
- `fastapi.BackgroundTasks`
- `fastapi.Depends`
- `fastapi.FastAPI`
- `fastapi.HTTPException`
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
- `openai.OpenAI`
- ... and 21 more (see JSON for full list)

## Most Depended Upon Files (Intra-Repo)

- `app/core/config.py` (16 dependents)
- `app/services/llm_client.py` (12 dependents)
- `app/services/store_singleton.py` (6 dependents)
- `app/services/model_registry.py` (6 dependents)
- `app/main.py` (6 dependents)
- `app/models/job.py` (5 dependents)
- `app/services/job_store.py` (5 dependents)
- `app/services/llm_openai.py` (5 dependents)
- `app/services/planner.py` (4 dependents)
- `app/services/job_repository.py` (4 dependents)

## Files with Most Dependencies (Intra-Repo)

- `app/api/routes.py` (8 dependencies)
- `app/services/llm_client.py` (5 dependencies)
- `app/services/planner.py` (5 dependencies)
- `app/services/store_singleton.py` (5 dependencies)
- `tests/test_plans_async_endpoint.py` (5 dependencies)
- `tests/test_models_endpoint.py` (4 dependencies)
- `tests/test_plans_polling_endpoints.py` (4 dependencies)
- `app/main.py` (3 dependencies)
- `app/services/__init__.py` (3 dependencies)
- `tests/test_llm_client.py` (3 dependencies)
