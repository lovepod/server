# Testing Strategy

## Scope

The current suite focuses on deterministic backend behavior without requiring a live database or external services.

It covers:

- settings validation and normalization
- helper and utility functions
- `BoxService`
- `MessageService`
- route-to-service wiring for all HTTP endpoints
- custom exception handling via the FastAPI app

## Philosophy

- Service tests use mocked SQLAlchemy sessions
- Route tests use FastAPI dependency overrides
- No tests rely on a running Postgres instance
- No tests rely on firmware or external HTTP services

## Running

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
python -m pytest
```

## Useful Future Additions

- real integration tests against a temporary Postgres container
- migration smoke tests once Alembic is added
- upload/read round-trip tests against a real DB session
- contract tests for firmware-facing JSON payloads
- performance tests for larger payloads and queue depth
