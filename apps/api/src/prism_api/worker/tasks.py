"""Celery tasks."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from prism_api.config import get_settings
from prism_api.ingest import IngestInputs, ingest_run
from prism_api.storage import build_storage
from prism_api.worker.celery_app import celery_app


@celery_app.task(name="prism.ingest_run")  # type: ignore[untyped-decorator]
def run_ingest(run_id: str, junit_xml_key: str, archive_key: str | None) -> None:
    settings = get_settings()
    storage = build_storage(settings)
    engine = create_engine(settings.database_url)
    junit_xml = storage.get_bytes(junit_xml_key)
    archive = storage.get_bytes(archive_key) if archive_key else None
    with sessionmaker(bind=engine)() as session:
        ingest_run(
            IngestInputs(run_id=run_id, junit_xml=junit_xml, archive=archive),
            session=session,
            storage=storage,
            kernel_pattern=settings.log_kernel_commit_pattern,
            hdl_pattern=settings.log_hdl_commit_pattern,
            findings_cap=settings.log_findings_cap,
        )
        session.commit()
