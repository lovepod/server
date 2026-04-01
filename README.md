# LovePod Backend

FastAPI backend for LovePod boxes. The API registers boxes, validates them to obtain upload tokens, accepts media or text messages, and serves a FIFO inbox back to firmware.

## Structure

- `app/main.py` boots the FastAPI application and wires middleware, routers, and exception handling.
- `app/routers/` contains HTTP endpoints.
- `app/services/` contains business logic for box registration/validation and message queue operations.
- `app/models.py` defines the SQLAlchemy ORM models.
- `app/config.py` centralizes runtime configuration from environment variables or `api/.env`.
- `alembic/` contains schema migration code.
- `tests/` contains the backend test suite.
- `docs/` contains architecture, API, testing, and production-readiness notes.

## Quick Start

1. Create and activate a virtual environment.
2. Install runtime dependencies:

```bash
pip install -r requirements.txt
```

3. Copy `.env.example` to `.env` and update `DATABASE_URL`.
4. Apply database migrations:

```bash
alembic upgrade head
```

5. Run the API from the `api/` directory:

```bash
python -m app
```

The default local address is `http://0.0.0.0:9017` and the OpenAPI UI is enabled unless `DOCS_ENABLED=false`.

## Production Hardening Included

- Alembic-based schema migrations
- expiring upload tokens with rotation on validation
- FIFO message queue semantics with delivery/ack/consume audit fields
- request IDs, request logging, readiness, liveness, process info, and in-memory metrics
- in-process rate limiting and upload MIME allowlisting
- basic security headers on all responses

## Running Tests

Install the test-only dependencies:

```bash
pip install -r requirements-dev.txt
```

Then run:

```bash
python -m pytest
```

The test suite uses mocks and dependency overrides, so it does not require a live Postgres instance.

## API Summary

- `POST /api/v1/box/register`
- `POST /api/v1/box/validate`
- `POST /api/v1/message/upload`
- `POST /api/v1/message/upload_base64`
- `POST /api/v1/message/upload_text`
- `GET /api/v1/message/lease`
- `GET /api/v1/message/read`
- `GET /api/v1/message/read_text`
- `GET /api/v1/message/read_base64`
- `GET /api/v1/message/consume_base64`
- `POST /api/v1/message/ack`
- `GET /api/v1/monitoring/heartbeat`
- `GET /api/v1/monitoring/live`
- `GET /api/v1/monitoring/ready`
- `GET /api/v1/monitoring/metrics`
- `GET /api/v1/monitoring/info`

More detail lives in [docs/api.md](/Users/jaksatomovic/Workspace/LovePod/api/docs/api.md).
