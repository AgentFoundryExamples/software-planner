# Software Planner API

A FastAPI-based software planning service with a modular, extensible architecture.

## Quick Start

### Prerequisites

- Python 3.10 or higher

### Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

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

### Configuration

Configuration is managed through environment variables or a `.env` file. Available settings:

- `APP_NAME`: Application name (default: "Software Planner API")
- `APP_VERSION`: Application version (default: "0.1.0")
- `DEBUG`: Debug mode (default: False)
- `HOST`: Server host (default: "0.0.0.0")
- `PORT`: Server port (default: 8000)
- `API_PREFIX`: API prefix for routes (default: "/api/v1")

### Testing

Run tests with pytest:
```bash
pytest
```

Run with coverage:
```bash
pytest --cov=app tests/
```

## Project Structure

```
.
├── app/
│   ├── __init__.py
│   ├── main.py              # Application factory and entrypoint
│   ├── api/                 # API routes (future endpoints)
│   │   └── __init__.py
│   ├── core/                # Core configuration and utilities
│   │   ├── __init__.py
│   │   └── config.py        # Typed settings with Pydantic
│   └── models/              # Data models (future implementations)
│       └── __init__.py
├── tests/                   # Test suite
│   ├── __init__.py
│   ├── test_config.py
│   └── test_main.py
├── requirements.txt         # Python dependencies
└── pytest.ini              # Pytest configuration
```

## Development

### Adding New Routes

Future API routes can be added by creating routers in `app/api/` and registering them in `app/main.py`:

```python
from app.api import your_router

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
