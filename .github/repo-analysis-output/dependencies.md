# Dependency Graph

Multi-language intra-repository dependency analysis.

Supports Python, JavaScript/TypeScript, C/C++, Rust, Go, Java, C#, Swift, HTML/CSS, and SQL.

Includes classification of external dependencies as stdlib vs third-party.

## Statistics

- **Total files**: 21
- **Intra-repo dependencies**: 21
- **External stdlib dependencies**: 12
- **External third-party dependencies**: 19

## External Dependencies

### Standard Library / Core Modules

Total: 12 unique modules

- `concurrent.futures.ThreadPoolExecutor`
- `datetime.datetime`
- `datetime.timezone`
- `json`
- `os`
- `threading.Lock`
- `time`
- `typing.Dict`
- `typing.List`
- `typing.Literal`
- `typing.Optional`
- `uuid`

### Third-Party Packages

Total: 19 unique packages

- `fastapi.APIRouter`
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
- `uvicorn`

## Most Depended Upon Files (Intra-Repo)

- `app/core/config.py` (5 dependents)
- `app/services/job_store.py` (4 dependents)
- `app/services/planner.py` (3 dependents)
- `app/main.py` (3 dependents)
- `app/models/response.py` (2 dependents)
- `app/models/job.py` (2 dependents)
- `app/models/request.py` (1 dependents)
- `app/api/routes.py` (1 dependents)

## Files with Most Dependencies (Intra-Repo)

- `app/api/routes.py` (3 dependencies)
- `app/main.py` (2 dependencies)
- `app/services/__init__.py` (2 dependencies)
- `app/services/planner.py` (2 dependencies)
- `tests/test_plan_endpoint.py` (2 dependencies)
- `tests/test_planner_integration.py` (2 dependencies)
- `app/core/__init__.py` (1 dependencies)
- `app/models/request.py` (1 dependencies)
- `app/services/job_store.py` (1 dependencies)
- `tests/test_config.py` (1 dependencies)
