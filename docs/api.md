# API Notes

## Authentication Model

- `x-api-key` is used for message uploads.
- `secret-key` is used by firmware to read or acknowledge messages.
- Secret keys are normalized server-side by trimming whitespace, removing dashes, and uppercasing.
- Upload tokens expire and are rotated by `POST /api/v1/box/validate`.
- Uploads are accepted only for configured MIME types.

## Endpoints

### `POST /api/v1/box/register`

Creates a new box.

Request:

```json
{
  "email": "device@lovepod.app",
  "name": "LovePod"
}
```

Response:

```json
{
  "secret_key": "AB12CD34"
}
```

### `POST /api/v1/box/validate`

Validates a box secret and returns a token used for uploads.

Request:

```json
{
  "secret_key": "AB12-CD34"
}
```

Response:

```json
{
  "token": "c957495c-2d74-4e06-9ef4-1aa211e87b5d",
  "expiresAt": "2030-01-01T00:00:00+00:00"
}
```

### `POST /api/v1/message/upload`

Multipart upload endpoint.

Headers:

- `x-api-key: <token>`

Form fields:

- `file`: binary payload

### `POST /api/v1/message/upload_base64`

JSON upload for binary payloads encoded as base64.

### `POST /api/v1/message/upload_text`

JSON upload for plain UTF-8 text messages.

### `GET /api/v1/message/read`

Returns the next pending FIFO message as raw bytes with a best-effort `Content-Type`.

### `GET /api/v1/message/read_text`

Returns the next pending FIFO message only when it is stored as `text/*`.

### `GET /api/v1/message/read_base64`

Returns the next pending FIFO message as base64 plus metadata and records delivery metadata.

### `GET /api/v1/message/consume_base64`

Returns the next pending FIFO message as base64 and marks it consumed immediately after a successful read.

### `POST /api/v1/message/ack`

Marks a specific message UUID acknowledged for the authenticated box.

### `GET /api/v1/monitoring/heartbeat`

Returns a heartbeat string for health probing.

### `GET /api/v1/monitoring/live`

Returns a lightweight liveness payload.

### `GET /api/v1/monitoring/ready`

Checks database connectivity and returns `200` or `503`.

### `GET /api/v1/monitoring/metrics`

Returns in-memory request counters and average duration.

## Error Shape

Domain errors are returned as:

```json
{
  "detail": "Human-readable error message"
}
```

Common statuses:

- `400` bad request
- `401` invalid or expired upload token
- `404` unknown box or no message
- `413` payload too large
- `415` unsupported content type
- `429` rate limit exceeded
- `500` internal decode/decompress failures
- `503` secret generation exhaustion
