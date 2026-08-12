FROM python:3.12.11-slim-bookworm

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml README.md LICENSE alembic.ini ./
COPY alembic ./alembic
COPY src ./src
RUN python -m pip install --no-cache-dir .
CMD ["uvicorn", "fab_identity.main:app", "--host", "0.0.0.0", "--port", "8080"]

