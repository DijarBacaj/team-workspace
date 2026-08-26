# Performance

## Database Design

The schema indexes authentication lookups, organization membership checks, project
status lists, task dashboard filters, assignee queues, and chronological comments.
List endpoints always enforce a maximum page size of 100.

## Reproducible Health Benchmark

Start the API and run:

```powershell
cd backend
uv run python scripts/benchmark_health.py --requests 500 --concurrency 20
```

The script reports throughput and p50, p95, and p99 latency. Results are intended as
a local regression baseline, not a production capacity claim. Database endpoint
capacity must be measured against production-like PostgreSQL data and deployment
infrastructure.

## Current Local Baseline

Measured on 2026-08-26 with Uvicorn, Python 3.13.7, 500 requests, and concurrency 20:

| Metric | Result |
| --- | ---: |
| Throughput | 888.73 requests/second |
| Mean latency | 19.56 ms |
| p50 latency | 16.73 ms |
| p95 latency | 30.34 ms |
| p99 latency | 139.87 ms |

This measures the in-process liveness endpoint on the development machine. It is a
repeatable regression signal, not a database or production load test.

## Query Review Workflow

For a slow PostgreSQL query:

1. Capture the generated SQL and parameter shape.
2. Run `EXPLAIN (ANALYZE, BUFFERS)` against production-like data.
3. Confirm row estimates, scan types, sort memory, and buffer reads.
4. Add or change an index only when the plan and workload justify it.
5. Repeat the measurement and record the before/after plan.
