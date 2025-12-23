# Dependency Graph

Multi-language intra-repository dependency analysis.

Supports Python, JavaScript/TypeScript, C/C++, Rust, Go, Java, C#, Swift, HTML/CSS, and SQL.

Includes classification of external dependencies as stdlib vs third-party.

## Statistics

- **Total files**: 29
- **Intra-repo dependencies**: 48
- **External stdlib dependencies**: 22
- **External third-party dependencies**: 24

## External Dependencies

### Standard Library / Core Modules

Total: 22 unique modules

- `abc.ABC`
- `abc.abstractmethod`
- `concurrent.futures.ThreadPoolExecutor`
- `datetime.datetime`
- `datetime.timezone`
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
- `unittest.mock.Mock`
- ... and 2 more (see JSON for full list)

### Third-Party Packages

Total: 24 unique packages

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
- `openai`
- `openai.OpenAI`
- `pydantic.BaseModel`
- `pydantic.Field`
- `pydantic.ValidationError`
- `pydantic.field_validator`
- `pydantic.model_validator`
- `pydantic_settings.BaseSettings`
- ... and 4 more (see JSON for full list)

## Most Depended Upon Files (Intra-Repo)

- `app/core/config.py` (9 dependents)
- `app/services/job_store.py` (8 dependents)
- `app/services/llm_client.py` (6 dependents)
- `app/services/store_singleton.py` (5 dependents)
- `app/main.py` (5 dependents)
- `app/services/planner.py` (4 dependents)
- `app/models/job.py` (3 dependents)
- `app/models/response.py` (3 dependents)
- `app/services/llm_openai.py` (3 dependents)
- `app/models/request.py` (1 dependents)

## Files with Most Dependencies (Intra-Repo)

- `app/api/routes.py` (7 dependencies)
- `tests/test_plans_async_endpoint.py` (5 dependencies)
- `app/services/store_singleton.py` (4 dependencies)
- `tests/test_plans_polling_endpoints.py` (4 dependencies)
- `app/main.py` (3 dependencies)
- `app/services/__init__.py` (3 dependencies)
- `tests/test_store_singleton.py` (3 dependencies)
- `app/services/planner.py` (2 dependencies)
- `tests/test_llm_openai.py` (2 dependencies)
- `tests/test_plan_endpoint.py` (2 dependencies)
