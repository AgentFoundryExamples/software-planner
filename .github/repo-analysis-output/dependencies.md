# Dependency Graph

Multi-language intra-repository dependency analysis.

Supports Python, JavaScript/TypeScript, C/C++, Rust, Go, Java, C#, Swift, HTML/CSS, and SQL.

Includes classification of external dependencies as stdlib vs third-party.

## Statistics

- **Total files**: 23
- **Intra-repo dependencies**: 30
- **External stdlib dependencies**: 14
- **External third-party dependencies**: 21

## External Dependencies

### Standard Library / Core Modules

Total: 14 unique modules

- `concurrent.futures.ThreadPoolExecutor`
- `datetime.datetime`
- `datetime.timezone`
- `json`
- `logging`
- `os`
- `threading.Lock`
- `time`
- `typing.Dict`
- `typing.List`
- `typing.Literal`
- `typing.Optional`
- `unittest.mock.Mock`
- `uuid`

### Third-Party Packages

Total: 21 unique packages

- `fastapi.APIRouter`
- `fastapi.BackgroundTasks`
- `fastapi.Depends`
- `fastapi.FastAPI`
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
- `starlette.exceptions.HTTPException`
- ... and 1 more (see JSON for full list)

## Most Depended Upon Files (Intra-Repo)

- `app/services/job_store.py` (7 dependents)
- `app/core/config.py` (6 dependents)
- `app/services/planner.py` (4 dependents)
- `app/main.py` (4 dependents)
- `app/services/store_singleton.py` (3 dependents)
- `app/models/response.py` (2 dependents)
- `app/models/job.py` (2 dependents)
- `app/models/request.py` (1 dependents)
- `app/api/routes.py` (1 dependents)

## Files with Most Dependencies (Intra-Repo)

- `app/api/routes.py` (5 dependencies)
- `tests/test_plans_async_endpoint.py` (5 dependencies)
- `app/main.py` (3 dependencies)
- `app/services/__init__.py` (2 dependencies)
- `app/services/planner.py` (2 dependencies)
- `tests/test_plan_endpoint.py` (2 dependencies)
- `tests/test_planner_integration.py` (2 dependencies)
- `app/core/__init__.py` (1 dependencies)
- `app/models/request.py` (1 dependencies)
- `app/services/job_store.py` (1 dependencies)
