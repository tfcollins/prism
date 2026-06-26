"""Ingest orchestration — pure function that the worker task wraps."""

from __future__ import annotations

import io
import json
import logging
import zipfile
from dataclasses import dataclass

from sqlalchemy.orm import Session

from prism_api.models import ArtifactKind, CaseStatus, RunStatus, TestCase, TestSuite
from prism_api.parsers.detect import detect_kind
from prism_api.parsers.filename import ArtifactOwner, parse_artifact_filename
from prism_api.parsers.junit import ParsedSuite, parse_junit_xml
from prism_api.parsers.logs import (
    DEFAULT_FINDINGS_CAP,
    DEFAULT_HDL_PATTERN,
    DEFAULT_KERNEL_PATTERN,
    parse_log,
)
from prism_api.parsers.waveform import load_waveform
from prism_api.repos.artifacts import ArtifactRepo
from prism_api.repos.logs import LogRepo
from prism_api.repos.projects import ProjectRepo
from prism_api.repos.runs import RunRepo
from prism_api.repos.suites import CaseRepo, MeasurementRepo, SuiteRepo
from prism_api.storage import ObjectStorage

logger = logging.getLogger(__name__)

_WAVEFORM_KINDS = {
    ArtifactKind.WAVEFORM_CSV,
    ArtifactKind.WAVEFORM_NPY,
    ArtifactKind.WAVEFORM_HDF5,
}
# genalyzer result attribute -> measurement (name suffix, unit)
_GENALYZER_METRICS = (
    ("snr", "dB"),
    ("sfdr", "dB"),
    ("sinad", "dB"),
    ("thd", "dBc"),
    ("enob", "bits"),
)
_GENALYZER_TRUE = {"true", "1", "yes", "on"}
_GENALYZER_FALSE = {"false", "0", "no", "off"}


def _genalyzer_enabled(project: object, tags: dict[str, str]) -> bool:
    """A run's `genalyzer` tag (true/false) overrides the project default."""
    raw = tags.get("genalyzer")
    if raw is not None:
        v = raw.strip().lower()
        if v in _GENALYZER_TRUE:
            return True
        if v in _GENALYZER_FALSE:
            return False
    return bool(getattr(project, "genalyzer_auto", False))


def _record_genalyzer(
    measurements_repo: MeasurementRepo, case_id: str, data: bytes, kind: ArtifactKind, filename: str
) -> None:
    """Analyze a waveform with genalyzer and store its metrics as measurements."""
    from prism_api.dsp.genalyzer_markers import analyze as genalyzer_analyze

    wf = load_waveform(kind, data, filename=filename)
    if wf.sample_rate is None:
        return
    result = genalyzer_analyze(wf.samples, float(wf.sample_rate))
    for attr, unit in _GENALYZER_METRICS:
        value = getattr(result, attr)
        if value is not None:
            measurements_repo.create(
                case_id=case_id,
                name=f"genalyzer.{attr}",
                value=float(value),
                unit=unit,
                spec_min=None,
                spec_max=None,
            )


_STATUS_MAP = {
    "pass": CaseStatus.PASS,
    "fail": CaseStatus.FAIL,
    "error": CaseStatus.ERROR,
    "skip": CaseStatus.SKIP,
}


@dataclass
class IngestInputs:
    run_id: str
    junit_xml: bytes
    archive: bytes | None = None


def _parse_manifest_kind_map(archive_bytes: bytes) -> dict[str, str]:
    """Return {basename: manifest_kind} from manifest.json in the archive.

    Empty dict for legacy archives (no manifest.json or schema_version != 2).
    The basename used here is the bare filename inside the archive — pytest-prism
    builds it as ``{suite}__{case}__{kind}__{label}.ext`` for case artifacts, but
    the manifest's ``filename`` field is just the label part.  We map the
    manifest's filename to its kind; the caller looks up the artifact by its
    bare-archive name and matches the trailing label.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as zf:
            if "manifest.json" not in zf.namelist():
                return {}
            manifest = json.loads(zf.read("manifest.json"))
    except (zipfile.BadZipFile, json.JSONDecodeError, KeyError):
        return {}
    if manifest.get("schema_version") != 2:
        return {}
    kinds: dict[str, str] = {}
    for case in manifest.get("cases", []):
        for art in case.get("artifacts", []):
            fn = art.get("filename")
            kind = art.get("kind")
            if fn and kind:
                kinds[fn] = kind
    for art in manifest.get("run_artifacts", []):
        fn = art.get("filename")
        kind = art.get("kind")
        if fn and kind:
            kinds[fn] = kind
    return kinds


def _derive_run_status(suites: list[ParsedSuite]) -> RunStatus:
    fail = sum(s.fail_count for s in suites)
    err = sum(s.error_count for s in suites)
    passed = sum(s.pass_count for s in suites)
    if err > 0:
        return RunStatus.ERROR
    if fail == 0 and passed > 0:
        return RunStatus.PASS
    if fail > 0 and passed == 0:
        return RunStatus.FAIL
    return RunStatus.MIXED


def ingest_run(
    inputs: IngestInputs,
    *,
    session: Session,
    storage: ObjectStorage,
    kernel_pattern: str = DEFAULT_KERNEL_PATTERN,
    hdl_pattern: str = DEFAULT_HDL_PATTERN,
    findings_cap: int = DEFAULT_FINDINGS_CAP,
) -> None:
    runs = RunRepo(session)
    suites_repo = SuiteRepo(session)
    cases_repo = CaseRepo(session)
    measurements_repo = MeasurementRepo(session)
    artifacts = ArtifactRepo(session)
    log_repo = LogRepo(session)

    # 1) Store the JUnit XML as a run-level artifact
    junit_key = storage.put_raw(inputs.junit_xml, filename="junit.xml")
    junit_artifact = artifacts.create(
        owner_type="run",
        owner_id=inputs.run_id,
        kind=ArtifactKind.JUNIT_XML,
        filename="junit.xml",
        size_bytes=len(inputs.junit_xml),
        content_hash=junit_key.rsplit("/", 1)[-1],
        storage_key=junit_key,
    )
    runs.set_junit_artifact(inputs.run_id, junit_artifact.id)

    # 2) Parse JUnit
    try:
        parsed_suites = parse_junit_xml(inputs.junit_xml)
    except Exception as exc:
        logger.exception("failed to parse JUnit XML for run %s: %s", inputs.run_id, exc)
        runs.set_status(inputs.run_id, RunStatus.ERROR)
        return

    # 3) Create suites + cases; build lookup maps for artifact attachment
    suite_by_name: dict[str, TestSuite] = {}
    case_by_key: dict[tuple[str, str], TestCase] = {}
    for ps in parsed_suites:
        suite = suites_repo.create(
            run_id=inputs.run_id,
            name=ps.name,
            pass_count=ps.pass_count,
            fail_count=ps.fail_count,
            error_count=ps.error_count,
            skip_count=ps.skip_count,
            duration_ms=ps.duration_ms,
        )
        suite_by_name[ps.name] = suite
        for pc in ps.cases:
            case = cases_repo.create(
                suite_id=suite.id,
                classname=pc.classname,
                name=pc.name,
                status=_STATUS_MAP[pc.status],
                duration_ms=pc.duration_ms,
                failure_message=pc.failure_message,
                failure_trace=pc.failure_trace,
            )
            case_by_key[(ps.name, pc.name)] = case
            for pm in pc.measurements:
                measurements_repo.create(
                    case_id=case.id,
                    name=pm.name,
                    value=pm.value,
                    unit=pm.unit,
                    spec_min=pm.spec_min,
                    spec_max=pm.spec_max,
                )

    # Resolve whether to record genalyzer metrics for this run's waveform cases.
    run = runs.get_by_id(inputs.run_id)
    project = ProjectRepo(session).get_by_id(run.project_id) if run else None
    run_tags = {t.key: t.value for t in runs.tags_for(inputs.run_id)}
    genalyzer_on = _genalyzer_enabled(project, run_tags)
    genalyzer_done: set[str] = set()

    # 4) Extract archive and attach artifacts
    if inputs.archive:
        kind_map = _parse_manifest_kind_map(inputs.archive)
        with zipfile.ZipFile(io.BytesIO(inputs.archive)) as zf:
            for name in zf.namelist():
                if name.endswith("/") or name == "manifest.json":
                    continue
                data = zf.read(name)
                bare = name.rsplit("/", 1)[-1]
                owner = parse_artifact_filename(bare)
                kind = detect_kind(name, data[:512])
                key = storage.put_raw(data, filename=name)
                owner_type, owner_id = _resolve_owner(
                    owner, inputs.run_id, suite_by_name, case_by_key
                )
                # Map archive name → manifest filename (trailing __-split label)
                parts = bare.rsplit("__", 1)
                label = parts[-1] if len(parts) > 1 else bare
                manifest_kind = kind_map.get(label)
                created = artifacts.create(
                    owner_type=owner_type,
                    owner_id=owner_id,
                    kind=kind,
                    filename=name,
                    size_bytes=len(data),
                    content_hash=key.rsplit("/", 1)[-1],
                    storage_key=key,
                    manifest_kind=manifest_kind,
                )
                if kind == ArtifactKind.LOG_TEXT:
                    try:
                        parsed = parse_log(
                            data,
                            kernel_pattern=kernel_pattern,
                            hdl_pattern=hdl_pattern,
                            findings_cap=findings_cap,
                        )
                        log_repo.create_report(
                            run_id=inputs.run_id,
                            artifact_id=created.id,
                            source=bare,
                            parsed=parsed,
                        )
                    except Exception as exc:  # best-effort; never fail ingest
                        logger.warning("log parse failed for %s: %s", name, exc)

                if (
                    genalyzer_on
                    and owner_type == "case"
                    and kind in _WAVEFORM_KINDS
                    and owner_id not in genalyzer_done
                ):
                    # One genalyzer analysis per case (first waveform wins).
                    genalyzer_done.add(owner_id)
                    try:
                        _record_genalyzer(measurements_repo, owner_id, data, kind, name)
                    except Exception as exc:  # best-effort; never fail ingest
                        logger.warning("genalyzer analysis failed for %s: %s", name, exc)

    # 5) Set final run status
    runs.set_status(inputs.run_id, _derive_run_status(parsed_suites))


def _resolve_owner(
    owner: ArtifactOwner,
    run_id: str,
    suite_by_name: dict[str, TestSuite],
    case_by_key: dict[tuple[str, str], TestCase],
) -> tuple[str, str]:
    if owner.scope == "case" and owner.suite and owner.case:
        case = case_by_key.get((owner.suite, owner.case))
        if case is not None:
            return "case", case.id
    if owner.scope in ("case", "suite") and owner.suite:
        suite = suite_by_name.get(owner.suite)
        if suite is not None:
            return "suite", suite.id
    return "run", run_id
