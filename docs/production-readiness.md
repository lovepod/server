# Production Readiness Roadmap

## Completed In This Iteration

### 1. Add schema migrations

Alembic scaffolding and a baseline migration were added so schema rollout can move away from startup-driven `create_all()`.

### 2. Tighten authentication and secrets

- Upload tokens now expire
- Validation rotates or reissues tokens as needed
- Expiry and revocation metadata are stored

Still recommended later:

- hash or otherwise protect long-lived secrets at rest
- consider distinct device and sender identities instead of one flat upload token

### 3. Improve queue semantics

The backend now behaves as an ordered FIFO inbox rather than "latest message wins". Messages keep delivery, acknowledgement, and consume timestamps instead of being immediately deleted by every flow.

### 4. Add observability

- request IDs added
- request logging added
- readiness and liveness endpoints added
- in-memory request metrics added
- rate-limited and unhandled-exception counters added
- process uptime and in-flight request tracking added
- monitoring info endpoint added for quick deploy/runtime inspection

Still recommended later:

- external metrics backend and dashboards
- alerting on repeated 5xx and DB connectivity issues
- queue-depth and business KPIs in a real monitoring stack

### 5. Protect the API edge

- basic in-process rate limiting added
- file-type policy enforcement added
- trusted hosts and CORS remain configurable
- security hardening headers added

Still recommended later:

- tighten production CORS and trusted hosts to exact values
- enforce rate limiting in shared infrastructure, not only in-process
- document reverse-proxy timeouts and TLS termination in deployment docs

## Next Priority

### 6. Move large payloads out of the relational DB

For bigger media or higher traffic, store blobs in object storage and keep metadata in Postgres.

### 7. Add async/background processing where needed

If uploads later trigger transcoding, thumbnailing, or notifications, move that work to background jobs instead of request time.

## Lower Priority But Valuable

### 8. Add a formal domain model

- sender accounts
- box ownership
- pairing or activation flow
- audit history

### 9. Add OpenAPI examples and SDK notes

This will help mobile/web sender clients and future firmware iterations.

### 10. Add deployment and recovery docs

- environment matrix
- backup/restore
- rollback plan
- incident runbooks
