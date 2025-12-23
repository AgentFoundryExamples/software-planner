# Dependency Graph

Multi-language intra-repository dependency analysis.

Supports Python, JavaScript/TypeScript, C/C++, Rust, Go, Java, C#, Swift, HTML/CSS, and SQL.

Includes classification of external dependencies as stdlib vs third-party.

## Statistics

- **Total files**: 9
- **Intra-repo dependencies**: 4
- **External stdlib dependencies**: 1
- **External third-party dependencies**: 15

## External Dependencies

### Standard Library / Core Modules

Total: 1 unique modules

- `os`

### Third-Party Packages

Total: 15 unique packages

- `fastapi.FastAPI`
- `fastapi.Query`
- `fastapi.Request`
- `fastapi.exceptions.RequestValidationError`
- `fastapi.middleware.cors.CORSMiddleware`
- `fastapi.responses.JSONResponse`
- `fastapi.status`
- `fastapi.testclient.TestClient`
- `pydantic.ValidationError`
- `pydantic.model_validator`
- `pydantic_settings.BaseSettings`
- `pydantic_settings.SettingsConfigDict`
- `pytest`
- `starlette.exceptions.HTTPException`
- `uvicorn`

## Most Depended Upon Files (Intra-Repo)

- `app/core/config.py` (3 dependents)
- `app/main.py` (1 dependents)

## Files with Most Dependencies (Intra-Repo)

- `app/core/__init__.py` (1 dependencies)
- `app/main.py` (1 dependencies)
- `tests/test_config.py` (1 dependencies)
- `tests/test_main.py` (1 dependencies)
