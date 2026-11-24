"""Celery tasks."""

from __future__ import annotations

import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from prism_api.config import get_settings
from prism_api.ingest import IngestInputs, ingest_run
from prism_api.models.run import RunStatus
from prism_api.repos.runs import RunRepo
from prism_api.storage import ObjectStorage, build_storage
from prism_api.worker.celery_app import celery_app

logger = logging.getLogger(__name__)


def ingest_or_mark_error(
    *,
    session_factory: sessionmaker[Session],
    storage: ObjectStorage,
    run_id: str,
    junit_xml_key: str,
    archive_key: str | None,
    kernel_pattern: str,
    hdl_pattern: str,
    findings_cap: int,
) -> None:
    """Ingest a run; on any failure mark it ERROR so it is never stranded as PENDING.

    The ingest runs in one transaction, so a failure rolls back everything it wrote;
    the ERROR status is then recorded in a fresh session. The original exception is
    re-raised so Celery still reports the task as failed.
    """
    try:
        junit_xml = storage.get_bytes(junit_xml_key)
        archive = storage.get_bytes(archive_key) if archive_key else None
        with session_factory() as session:
            ingest_run(
                IngestInputs(run_id=run_id, junit_xml=junit_xml, archive=archive),
                session=session,
                storage=storage,
                kernel_pattern=kernel_pattern,
                hdl_pattern=hdl_pattern,
                findings_cap=findings_cap,
            )
            session.commit()
    except Exception:
        logger.exception("ingest failed for run %s; marking it error", run_id)
        try:
            with session_factory() as session:
                RunRepo(session).set_status(run_id, RunStatus.ERROR)
                session.commit()
        except Exception:
            logger.exception("could not mark run %s as error", run_id)
        raise


@celery_app.task(name="prism.ingest_run")  # type: ignore[untyped-decorator]
def run_ingest(run_id: str, junit_xml_key: str, archive_key: str | None) -> None:
    settings = get_settings()
    engine = create_engine(settings.database_url)
    try:
        ingest_or_mark_error(
            session_factory=sessionmaker(bind=engine),
            storage=build_storage(settings),
            run_id=run_id,
            junit_xml_key=junit_xml_key,
            archive_key=archive_key,
            kernel_pattern=settings.log_kernel_commit_pattern,
            hdl_pattern=settings.log_hdl_commit_pattern,
            findings_cap=settings.log_findings_cap,
        )
    finally:
        engine.dispose()
