#!/bin/sh
set -e
alembic upgrade head
python -m prism_api.cli bootstrap-admin || true
exec "$@"
