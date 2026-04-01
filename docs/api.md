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

### `GET /api/v1/message/lease`

Primary firmware endpoint.

Returns the next pending FIFO message plus a temporary lease:

```json
{
  "messageUuid": "msg-123",
  "leaseId": "lease-abc",
  "leaseExpiresAt": "2030-01-01T00:00:00+00:00",
  "fileType": "text/plain",
  "fileName": "message.txt",
  "text": "Volim te"
}
```

For binary payloads the same response shape is used, but `data_base64` is returned instead of `text`.

The firmware should acknowledge the message with the same `leaseId`. If the device disappears and the lease expires, the message becomes visible again for re-delivery.

### `GET /api/v1/message/read`

Returns the next pending FIFO message as raw bytes with a best-effort `Content-Type`.

### `GET /api/v1/message/read_text`

Returns the next pending FIFO message only when it is stored as `text/*`.

### `GET /api/v1/message/read_base64`

Returns the next pending FIFO message as base64 plus metadata and records delivery metadata.

### `GET /api/v1/message/consume_base64`

Returns the next pending FIFO message as base64 and marks it consumed immediately after a successful read.

### `POST /api/v1/message/ack`

Marks a specific message UUID acknowledged for the authenticated box. When the message was leased, the caller should also send `leaseId`.

### `GET /api/v1/monitoring/heartbeat`

Returns a heartbeat string for health probing.

### `GET /api/v1/monitoring/live`

Returns a lightweight liveness payload.

### `GET /api/v1/monitoring/ready`

Checks database connectivity and returns `200` or `503`.

### `GET /api/v1/monitoring/metrics`

Returns in-memory request counters, average duration, in-flight request counts, and process uptime.

### `GET /api/v1/monitoring/info`

Returns a lightweight operational summary for the running app, including environment and process uptime.

## Legacy Read Endpoints

`/read`, `/read_text`, `/read_base64`, and `/consume_base64` are still present for compatibility and diagnostics.

The preferred embedded integration path is now `/lease` + `/ack`.

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
