# ADR 0001: Use a Modular Monolith

- Status: Accepted
- Date: 2026-08-26

## Context

Team Workspace needs transactional operations across organizations, memberships,
projects, tasks, labels, and comments. The first milestone must be easy to run,
test, explain, and deploy.

## Decision

Build one FastAPI application backed by one PostgreSQL database. Keep HTTP routes,
validation, persistence, security, and reusable domain services in separate modules.

## Consequences

### Benefits

- Cross-domain writes use straightforward ACID transactions.
- Local development, migrations, tests, and deployment stay simple.
- Module boundaries can later become service boundaries if scaling evidence requires
  it.

### Costs

- All modules deploy together.
- A poorly structured module could create coupling inside the process.
- Horizontal scaling applies to the entire application rather than one domain.

## Rejected Alternative

Microservices were rejected for this milestone because they would add network
failure modes, distributed transactions, message contracts, and operational overhead
without a demonstrated scaling need.
