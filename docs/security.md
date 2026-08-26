# Security Considerations

## Implemented Controls

- Passwords are hashed with the current recommended Argon2 configuration from
  `pwdlib`; plaintext passwords are never stored or returned.
- Access tokens are short-lived. Refresh tokens are rotated, tracked by JTI, and
  revocable on logout.
- Bearer tokens distinguish access and refresh token types.
- Every organization-scoped lookup verifies membership to prevent cross-tenant
  data access.
- Role checks enforce owner, admin, member, and viewer capabilities.
- Request models reject unknown fields and validate lengths, enums, emails, UUIDs,
  colors, and password strength.
- Database constraints provide a second validation layer for uniqueness and
  relationships.
- CORS allows only configured origins.
- `.env` files, local environments, caches, and secrets are excluded from Git.
- Production startup rejects the documented placeholder JWT secret.

## Deployment Requirements

- Generate `JWT_SECRET_KEY` with a cryptographically secure random generator and
  store it in a secret manager.
- Terminate TLS at the load balancer or reverse proxy and redirect HTTP to HTTPS.
- Use a dedicated PostgreSQL role with only the permissions required by the API.
- Restrict database network access to the application network.
- Rate-limit login, registration, and refresh endpoints at the gateway.
- Rotate secrets through a planned procedure; rotating the JWT key invalidates
  existing tokens.
- Send logs to centralized storage and alert on repeated authentication failures and
  unexpected 5xx responses.
- Run dependency and container vulnerability scanning in the deployment platform.

## Known Trade-off

Refresh-token JTIs are stored in plaintext because they are random identifiers, not
the bearer token itself. A database leak does not reveal usable refresh tokens. For
larger deployments, expired rows should be removed by a scheduled maintenance job.
