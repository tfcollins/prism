# --- Build libgenalyzer (the genalyzer pip wrapper ctypes-loads it at runtime) ---
FROM python:3.12-slim AS genalyzer-builder
# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
      git cmake g++ libfftw3-dev ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /src
RUN git clone --depth 1 --branch v0.1.4 https://github.com/analogdevicesinc/genalyzer.git
RUN cmake -B build -S genalyzer -DBUILD_TESTS_EXAMPLES=OFF -DCMAKE_BUILD_TYPE=Release \
    && cmake --build build -j

FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
# Runtime dep of libgenalyzer (FFTW), plus the built shared lib + ldconfig so the
# genalyzer python package's find_library("genalyzer") resolves it.
# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends libfftw3-3 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=genalyzer-builder /src/build/bindings/c/src/libgenalyzer.so* /usr/local/lib/
RUN ldconfig
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
