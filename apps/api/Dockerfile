FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN pip install uv
WORKDIR /app
COPY pyproject.toml ./
RUN uv pip install --system --no-cache .
COPY src ./src
EXPOSE 8000
CMD ["uvicorn", "prism_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
