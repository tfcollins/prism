"""Celery application factory."""

import os

from celery import Celery

from prism_api.config import Settings, get_settings


def build_celery(settings: Settings | None = None) -> Celery:
    s = settings or get_settings()
    app = Celery("prism", broker=s.redis_url, backend=s.redis_url)
    app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_acks_late=True,
        worker_prefetch_multiplier=1,
    )
    # Ensure tasks module is imported
    app.autodiscover_tasks(["prism_api.worker"])
    return app


# Only instantiate at module level if we have the required env vars.
# Tests build their own instance via build_celery(_s()) and don't need this.
# The stub branch lets `from prism_api.worker.celery_app import celery_app`
# succeed in test environments. The .task() decorator still works on a plain
# Celery object; it just won't connect to a broker.
celery_app = (
    build_celery() if os.getenv("PRISM_DATABASE_URL") else Celery("prism-uninitialized")
)
