#!/usr/bin/env bash
set -euo pipefail

alembic upgrade head
exec uvicorn fab_identity.main:app --host 0.0.0.0 --port "${PORT:-8080}"

