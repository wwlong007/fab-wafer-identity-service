#!/usr/bin/env bash
set -euo pipefail

alembic upgrade head
python -m compileall -q src
pytest

