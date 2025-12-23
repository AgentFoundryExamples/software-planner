# Dependency Graph

Multi-language intra-repository dependency analysis.

Supports Python, JavaScript/TypeScript, C/C++, Rust, Go, Java, C#, Swift, HTML/CSS, and SQL.

Includes classification of external dependencies as stdlib vs third-party.

## Statistics

- **Total files**: 26
- **Intra-repo dependencies**: 39
- **External stdlib dependencies**: 19
- **External third-party dependencies**: 22

## External Dependencies

### Standard Library / Core Modules

Total: 19 unique modules

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
- `threading.Lock`
- `time`
- `typing.Any`
- `typing.Dict`
- `typing.List`
- `typing.Literal`
- `typing.Optional`
- `unittest.mock.Mock`
- `uuid`

### Third-Party Packages

Total: 22 unique packages

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
- `pydantic.BaseModel`
- `pydantic.Field`
- `pydantic.ValidationError`
- `pydantic.field_validator`
- `pydantic.model_validator`
- `pydantic_settings.BaseSettings`
- `pydantic_settings.SettingsConfigDict`
- `pytest`
- ... and 2 more (see JSON for full list)

## Most Depended Upon Files (Intra-Repo)

- `app/core/config.py` (8 dependents)
- `app/services/job_store.py` (8 dependents)
- `app/main.py` (5 dependents)
- `app/services/planner.py` (4 dependents)
- `app/services/store_singleton.py` (4 dependents)
- `app/models/job.py` (3 dependents)
- `app/models/response.py` (3 dependents)
- `app/services/llm_client.py` (2 dependents)
- `app/models/request.py` (1 dependents)
- `app/api/routes.py` (1 dependents)

## Files with Most Dependencies (Intra-Repo)

- `app/api/routes.py` (7 dependencies)
- `tests/test_plans_async_endpoint.py` (5 dependencies)
- `tests/test_plans_polling_endpoints.py` (4 dependencies)
- `app/main.py` (3 dependencies)
- `app/services/__init__.py` (3 dependencies)
- `app/services/planner.py` (2 dependencies)
- `tests/test_plan_endpoint.py` (2 dependencies)
- `tests/test_planner_integration.py` (2 dependencies)
- `app/core/__init__.py` (1 dependencies)
- `app/models/request.py` (1 dependencies)
