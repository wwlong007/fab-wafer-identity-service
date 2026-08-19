# Fab Wafer Identity Service

`fab-wafer-identity-service` is an internal-style backend for registering wafer
layouts, equipment coordinate frames, reticle address profiles, and wafer-test
observations. It exposes a JSON API used by sort, inspection, and retest tools.

The service treats layout geometry as master data. Incoming records retain their
equipment address for audit while the application also records a normalized die
coordinate used by operations and export APIs. A returned observation address
uses the same grid or shot/site contract accepted by ingest; together with its
batch frame and reticle profile, it is replayable to the linked physical Die.
The public schema also records catalog provenance for each batch and source Die.
Historical replay must use the effective catalog captured when the data was
created, even when the live frame or reticle catalog later evolves.

Coordinate frames may optionally form an acyclic same-layout parent chain.
Each frame exposes an ordered integer calibration program containing
translations, axis mirrors, and quarter-turn rotations. Parent transforms run
before child transforms, and export/re-ingest uses the exact inverse program.
The legacy scalar frame fields remain supported for existing clients.

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

