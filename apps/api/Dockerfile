# --- Build libgenalyzer (the genalyzer pip wrapper ctypes-loads it at runtime) ---
FROM python:3.12-slim AS genalyzer-builder
# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
      git cmake make g++ pkg-config libfftw3-dev ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /src
RUN git clone --depth 1 --branch v0.1.4 https://github.com/analogdevicesinc/genalyzer.git \
    && cmake -B build -S genalyzer -DBUILD_TESTS_EXAMPLES=OFF -DCMAKE_BUILD_TYPE=Release \
    && cmake --build build -j

FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
# Runtime dep of libgenalyzer (FFTW double-precision; it links only libfftw3.so.3).
# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends libfftw3-double3 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=genalyzer-builder /src/build/bindings/c/src/libgenalyzer.so* /usr/local/lib/
# ldconfig so the genalyzer python package's find_library("genalyzer") resolves the
# copied .so; uv bootstraps the rest of the install.
# hadolint ignore=DL3013
RUN ldconfig && pip install uv
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
