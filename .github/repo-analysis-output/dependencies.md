# Dependency Graph

Multi-language intra-repository dependency analysis.

Supports Python, JavaScript/TypeScript, C/C++, Rust, Go, Java, C#, Swift, HTML/CSS, and SQL.

Includes classification of external dependencies as stdlib vs third-party.

## Statistics

- **Total files**: 36
- **Intra-repo dependencies**: 73
- **External stdlib dependencies**: 23
- **External third-party dependencies**: 28

## External Dependencies

### Standard Library / Core Modules

Total: 23 unique modules

- `abc.ABC`
- `abc.abstractmethod`
- `concurrent.futures.ThreadPoolExecutor`
- `datetime.datetime`
- `datetime.timezone`
- `hashlib`
- `json`
- `logging`
- `os`
- `random`
- `re`
- `threading`
- `threading.Lock`
- `time`
- `typing.Any`
- `typing.Dict`
- `typing.List`
- `typing.Literal`
- `typing.Optional`
- `unittest.mock.MagicMock`
- ... and 3 more (see JSON for full list)

### Third-Party Packages

Total: 28 unique packages

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
- `pydantic.BaseModel`
- `pydantic.Field`
- ... and 8 more (see JSON for full list)

## Most Depended Upon Files (Intra-Repo)

- `app/core/config.py` (13 dependents)
- `app/services/llm_client.py` (12 dependents)
- `app/services/job_store.py` (8 dependents)
- `app/services/store_singleton.py` (6 dependents)
- `app/services/model_registry.py` (6 dependents)
- `app/main.py` (6 dependents)
- `app/services/llm_openai.py` (5 dependents)
- `app/services/planner.py` (4 dependents)
- `app/models/job.py` (3 dependents)
- `app/models/response.py` (3 dependents)

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
