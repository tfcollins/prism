FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
# uv is the bootstrap package manager for the rest of the install; pinning here
# while python:3.12-slim itself floats buys no real reproducibility. Switch to
# `COPY --from=ghcr.io/astral-sh/uv:<ver>` if/when we want a pinned uv.
# hadolint ignore=DL3013
RUN pip install uv
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN uv pip install --system --no-cache .
COPY alembic.ini ./
COPY docker-entrypoint.sh ./
RUN chmod +x docker-entrypoint.sh
EXPOSE 8000
ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["uvicorn", "prism_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
