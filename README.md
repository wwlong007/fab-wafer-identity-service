# Fab Wafer Identity Service

`fab-wafer-identity-service` is an internal-style backend for registering wafer
layouts, equipment coordinate frames, reticle address profiles, and wafer-test
observations. It exposes a JSON API used by sort, inspection, and retest tools.

The service treats layout geometry as master data. Incoming records retain their
equipment address for audit while the application also records a normalized die
coordinate used by operations and export APIs.

## Development

```bash
docker compose up -d postgres
python -m venv .venv
.venv/Scripts/pip install -e ".[test]"
alembic upgrade head
uvicorn fab_identity.main:app --reload
```

Set `FAB_DATABASE_URL` to override the default local PostgreSQL connection.
The API documentation is available at `/docs`; health checks use `/healthz`.

## Core resources

- layouts and their valid die masks
- coordinate frames declared by manufacturing equipment
- reticle profiles and named sites
- wafer instances, physical dies, ingest batches, and observations

Amounts, yield disposition, equipment file parsing, and message delivery are
owned by other services and intentionally remain outside this repository.

