# Backend Architecture

## Overview

The backend is a small FastAPI service that acts as the server-side queue for LovePod devices:

1. A box is registered and receives a `secret_key`.
2. The box validates that secret and receives an upload token.
3. A client uploads text or binary content using the upload token.
4. Firmware polls for the next FIFO inbox item using the box secret.
5. The firmware either peeks the message, acknowledges it, or consumes it.

## Main Components

- `app/main.py`
  Builds the FastAPI app, enables CORS and trusted hosts, registers routers, adds request logging, request IDs, security headers, metrics, and rate limiting, and maps `AppError` exceptions to JSON API responses.

- `app/config.py`
  Loads environment-based configuration with `pydantic-settings`. This is the single source of truth for runtime settings such as DB URL, upload size, logging, docs exposure, and Uvicorn host/port.

- `app/db.py`
  Owns the SQLAlchemy engine, declarative base, per-request session factory, and readiness DB probe.

- `app/models.py`
  Defines:
  - `Box`: device identity and `secret_key`
  - `Token`: upload token associated with a box, including expiry, revocation, and last-use tracking
  - `Message`: FIFO inbox item with delivery, acknowledgement, and consume audit fields

- `app/services/box_service.py`
  Handles box registration and validation logic, including token expiry and rotation.

- `app/services/message_service.py`
  Handles upload validation, content normalization, FIFO queue reads, base64 conversion, and acknowledgement/consume semantics.

- `alembic/`
  Owns schema migrations so production rollout no longer depends on `create_all()`.

## Current Data Flow

### Registration

- `POST /api/v1/box/register`
- Creates a new `Box`
- Generates a unique alphanumeric secret

### Validation

- `POST /api/v1/box/validate`
- Looks up the box by secret
- Reuses the latest active token if it is still valid
- Revokes expired tokens
- Issues a new expiring token when needed

### Message Upload

- Uploads require `x-api-key`
- Payloads are stored compressed with raw deflate
- MIME type is normalized before persistence
- MIME type is checked against an allowlist
- Filenames are sanitized to avoid path traversal or absolute path leakage

### Message Read

- Firmware authenticates with `secret-key`
- Preferred embedded path is unified `/lease`
- Lease responses carry either `text` or `data_base64` in one envelope
- A leased message is hidden from other polls until acknowledged or until its lease expires
- Queue selection is FIFO by `created_at`
- `read` returns raw bytes for the next pending inbox item
- `read_text` returns decoded UTF-8 text only when the next pending item is `text/*`
- `read_base64` peeks the next pending payload as base64 and records delivery metadata
- `consume_base64` returns the next pending payload and marks it consumed
- `ack` marks a specific message UUID acknowledged without deleting history

## Design Strengths

- Clean separation between routers and services
- Centralized configuration
- Alembic migrations replace schema drift-prone startup DDL
- Small and understandable API surface
- Custom API-safe exception model
- Firmware-oriented endpoints with predictable payload shapes
- Basic operational visibility via readiness, metrics, request IDs, and request logs
- Basic edge protection via rate limiting and upload policy enforcement

## Current Limits

- No background jobs
- In-memory rate limiting and metrics are single-process only
- Queue semantics are FIFO and audited, but still single-consumer and not lease-based
- No object storage for larger media payloads
- No auth scopes or user model beyond token/secret pairs
