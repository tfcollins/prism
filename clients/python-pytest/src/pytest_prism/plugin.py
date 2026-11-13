"""pytest-prism plugin entry. Wires pytest hooks to the registry."""

import base64
import datetime as _dt
import hashlib
import io
import json
import logging
import re
import sys
import tempfile
import traceback
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TextIO, cast

import pytest

from pytest_prism import __version__ as _PLUGIN_VERSION
from pytest_prism.api import (
    _PRISM_PAYLOADS_STASH,
    RenderContext,
    RenderResult,
    SessionContext,
    SessionHook,
)
from pytest_prism.client import detect_ci
from pytest_prism.config import Config, ConfigError
from pytest_prism.manifest import OutputDir
from pytest_prism.registry import Registry, RegistryError, load_registry
from pytest_prism.upload import UploadError
from pytest_prism.upload import upload as _upload

_LOG = logging.getLogger("pytest_prism.plugin")


@dataclass
class _State:
    cfg: Config
    out_dir: OutputDir
    registry: Registry
    started_at: str = ""
    hook_pre_results: dict[str, dict[str, Any]] = None  # type: ignore[assignment]
    hook_post_results: dict[str, dict[str, Any]] = None  # type: ignore[assignment]
    terminal_buffer: io.StringIO | None = None
    exitstatus: int | None = None
    worker_temp: Any = None
    original_streams: tuple[TextIO, TextIO] | None = None
    tee_streams: tuple[TextIO, TextIO] | None = None
    interrupted: dict[str, list[tuple[str, str, str]]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.hook_pre_results is None:
            self.hook_pre_results = {}
        if self.hook_post_results is None:
            self.hook_post_results = {}


class _TerminalTee:
    def __init__(self, stream: TextIO, buffer: io.StringIO) -> None:
        self.stream = stream
        self.buffer = buffer

    def write(self, text: str) -> int:
        self.buffer.write(text)
        return self.stream.write(text)

    def flush(self) -> None:
        self.stream.flush()

    def __getattr__(self, name: str) -> Any:
        return getattr(self.stream, name)


class _CaptureReports:
    """Capture serialized reports on the controller, including xdist workers."""

    def __init__(self, state: _State) -> None:
        self.state = state

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        for artifact in getattr(report, "prism_artifacts", []):
            self.state.out_dir.write_case_artifact(
                case_nodeid=report.nodeid,
                filename=artifact["filename"],
                content=base64.b64decode(artifact["content"]),
                kind=artifact["kind"],
            )
        for label, content in report.sections:
            parts = label.split()
            if len(parts) != 3 or parts[0] != "Captured":
                continue
            if parts[2] != report.when and report.when in {"setup", "call", "teardown"}:
                continue
            stream = parts[1]
            if stream in {"stdout", "stderr", "log"} and content:
                self.state.out_dir.write_case_artifact(
                    case_nodeid=report.nodeid,
                    filename=f"pytest_{stream}_{parts[2]}.log",
                    content=content.encode("utf-8"),
                    kind="pytest_capture",
                )

    def pytest_collectreport(self, report: pytest.CollectReport) -> None:
        if report.failed:
            digest = hashlib.sha256(report.nodeid.encode()).hexdigest()[:16]
            self.state.out_dir.write_run_artifact(
                f"collection_error_{digest}.log",
                str(report.longrepr).encode("utf-8"),
                kind="pytest_collection_error",
            )

    @pytest.hookimpl(optionalhook=True)
    def pytest_testnodedown(self, node: Any) -> None:
        self.state.interrupted.update(
            getattr(node, "workeroutput", {}).pop("prism_interrupted", {})
        )

    @pytest.hookimpl(optionalhook=True)
    def pytest_handlecrashitem(self, crashitem: str, report: pytest.TestReport) -> None:
        for phase, stream, content in self.state.interrupted.pop(crashitem, []):
            report.sections.append((f"Captured {stream} {phase}", content))


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_protocol(item: pytest.Item) -> Generator[None, None, None]:
    outcome = yield
    st: _State | None = getattr(item.config, "_prism_state", None)
    if st is None or outcome is None or outcome.excinfo is None:
        return
    # An interrupted call never produces a TestReport. CaptureManager still
    # saves its output on the item as it unwinds the test protocol.
    sections = list(item._report_sections)
    if st.worker_temp is not None:
        st.interrupted[item.nodeid] = sections
        return
    report = pytest.TestReport(
        nodeid=item.nodeid,
        location=item.location,
        keywords={},
        outcome="failed",
        longrepr=f"{outcome.excinfo[0].__name__}: {outcome.excinfo[1]}",
        when="call",
        sections=[(f"Captured {stream} {phase}", content) for phase, stream, content in sections],
        user_properties=item.user_properties,
    )
    item.config.hook.pytest_runtest_logreport(report=report)


def pytest_addoption(parser: pytest.Parser) -> None:
    g = parser.getgroup("prism_report", "Prism test-report plugin")
    g.addoption("--prism-report", action="store_true", default=False)
    g.addoption("--prism-out", default=None)
    g.addoption("--prism-out-overwrite", action="store_true", default=False)
    g.addoption("--prism-url", default=None)
    g.addoption("--prism-email", default=None)
    g.addoption("--prism-password", default=None)
    g.addoption("--prism-token", default=None)
    g.addoption("--prism-project", default=None)
    g.addoption("--prism-run-name", default=None)
    g.addoption("--prism-tag", action="append", default=[])
    g.addoption("--prism-labgrid-place", default=None)
    g.addoption("--prism-no-labgrid", action="store_true", default=False)
    g.addoption("--prism-dmesg-via", default=None, choices=["auto", "ssh", "console", "none"])
    g.addoption("--prism-dmesg-ssh-user", default=None)
    g.addoption("--prism-dmesg-ssh-key", default=None)
    g.addoption("--prism-fail-on-upload-error", action="store_true", default=False)
    g.addoption("--prism-strict-registry", action="store_true", default=False)
    g.addoption("--prism-fail-on-hook-error", action="store_true", default=False)


def _setup_terminal_capture(config: pytest.Config, st: _State) -> None:
    if st.terminal_buffer is None:
        st.terminal_buffer = io.StringIO()
    if config.getoption("capture") in {"no", "tee-sys"} and st.original_streams is None:
        st.original_streams = (sys.stdout, sys.stderr)
        stdout = cast(TextIO, _TerminalTee(sys.stdout, st.terminal_buffer))
        stderr = cast(TextIO, _TerminalTee(sys.stderr, st.terminal_buffer))
        st.tee_streams = (stdout, stderr)
        sys.stdout, sys.stderr = stdout, stderr
    tr = config.pluginmanager.get_plugin("terminalreporter")
    if tr is not None and hasattr(tr, "_tw") and not hasattr(tr._tw.write, "__prism_wrapped__"):
        orig_write = tr._tw.write

        def new_write(s: str, *args: Any, **kwargs: Any) -> Any:
            if st.terminal_buffer is not None and not isinstance(tr._tw._file, _TerminalTee):
                st.terminal_buffer.write(s)
            return orig_write(s, *args, **kwargs)

        new_write.__prism_wrapped__ = True  # type: ignore[attr-defined]
        tr._tw.write = new_write


def pytest_configure(config: pytest.Config) -> None:
    if not config.getoption("--prism-report"):
        return
    try:
        cfg = Config.from_pytest(config)
    except ConfigError as exc:
        raise pytest.UsageError(f"prism-report: {exc}") from exc

    if cfg.out_dir is None:
        raise pytest.UsageError("prism-report: could not resolve output directory")
    resolved_out_dir = cfg.out_dir
    worker_temp = None
    if hasattr(config, "workerinput"):
        worker_temp = tempfile.TemporaryDirectory(prefix="pytest-prism-worker-")
        resolved_out_dir = Path(worker_temp.name) / "out"
    out_dir = OutputDir(resolved_out_dir)
    overwrite = config.getoption("--prism-out-overwrite")
    if overwrite and resolved_out_dir.exists():
        import shutil

        shutil.rmtree(resolved_out_dir)
    try:
        out_dir.initialize()
    except SystemExit as exc:
        raise pytest.UsageError(
            f"prism-report: output dir {resolved_out_dir} is not empty; "
            "pass --prism-out-overwrite or pick another path"
        ) from exc

    try:
        registry = load_registry(strict=config.getoption("--prism-strict-registry"))
    except RegistryError as exc:
        raise pytest.UsageError(f"prism-report: {exc}") from exc

    st = _State(cfg=cfg, out_dir=out_dir, registry=registry, worker_temp=worker_temp)
    config._prism_state = st  # type: ignore[attr-defined]
    if worker_temp is not None:
        return
    config.pluginmanager.register(_CaptureReports(st), "prism-captured-output")
    _setup_terminal_capture(config, st)

    junit_path = resolved_out_dir / "junit.xml"
    config.option.xmlpath = str(junit_path)
    config._inicache["junit_logging"] = "all"
    config._inicache["junit_log_passing_tests"] = True
    for topic, msg in cfg.warnings.items():
        config.issue_config_time_warning(
            pytest.PytestConfigWarning(f"prism-report: {topic}: {msg}"),
            stacklevel=1,
        )


def pytest_sessionstart(session: pytest.Session) -> None:
    st: _State | None = getattr(session.config, "_prism_state", None)
    if st is None or st.worker_temp is not None:
        return
    _setup_terminal_capture(session.config, st)
    st.started_at = _dt.datetime.now(_dt.timezone.utc).isoformat()

    fail_on_err = session.config.getoption("--prism-fail-on-hook-error")

    if not st.registry.session_hooks:
        return

    def _run_pre(name: str, hook: SessionHook) -> dict[str, Any]:
        ctx = SessionContext(
            run_dir=st.out_dir.root,
            hook_dir=st.out_dir.session_dir(name),
            config=st.cfg,
            logger=logging.getLogger(f"pytest_prism.session.{name}"),
        )
        try:
            return dict(hook.session_pre(ctx))
        except Exception as exc:
            (ctx.hook_dir / "error.log").write_text(
                f"session_pre raised: {exc}\n\n{traceback.format_exc()}"
            )
            if fail_on_err:
                raise
            sys.stderr.write(f"pytest-prism: session_pre {name!r} raised: {exc}; continuing\n")
            return {"error": str(exc)}

    with ThreadPoolExecutor(max_workers=max(1, len(st.registry.session_hooks))) as ex:
        futs = {
            ex.submit(_run_pre, name, hook): name
            for name, hook in st.registry.session_hooks.items()
        }
        for fut in as_completed(futs):
            name = futs[fut]
            try:
                st.hook_pre_results[name] = dict(fut.result() or {})
            except Exception:
                if fail_on_err:
                    raise


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(
    item: pytest.Item, call: pytest.CallInfo[Any]
) -> Generator[None, None, None]:
    st: _State | None = getattr(item.config, "_prism_state", None)
    if st is not None and not any(key == "prism_nodeid" for key, _ in item.user_properties):
        item.user_properties.append(("prism_nodeid", item.nodeid))
    outcome = yield
    report = outcome.get_result() if outcome is not None else None
    if call.when != "call":
        return
    if st is None:
        return
    payloads = item.stash.get(_PRISM_PAYLOADS_STASH, [])
    if not payloads:
        return
    item.stash[_PRISM_PAYLOADS_STASH] = []  # consume

    for kind, payload in payloads:
        renderer = st.registry.renderers.get(kind)
        if renderer is None:
            sys.stderr.write(
                f"pytest-prism: case {item.nodeid}: no renderer for kind "
                f"{kind!r}; saving raw payload\n"
            )
            try:
                raw = json.dumps(payload, default=str, indent=2).encode("utf-8")
            except Exception as exc:
                raw = f"unserialisable payload: {exc}".encode()
            st.out_dir.write_case_artifact(
                case_nodeid=item.nodeid,
                filename="raw.json",
                content=raw,
                kind=kind,
            )

            continue

        case_dir = st.out_dir.case_kind_dir(case_nodeid=item.nodeid, kind=kind)
        ctx = RenderContext(
            case_dir=case_dir,
            case_id=item.nodeid,
            logger=logging.getLogger(f"pytest_prism.render.{kind}"),
        )
        try:
            result: RenderResult = renderer.render(payload, ctx)
        except Exception as exc:
            err = (f"renderer {kind!r} raised: {exc}\n\n{traceback.format_exc()}").encode()
            st.out_dir.write_case_artifact(
                case_nodeid=item.nodeid,
                filename="error.log",
                content=err,
                kind=kind,
            )
            sys.stderr.write(
                f"pytest-prism: case {item.nodeid}: renderer {kind!r} raised: {exc}; continuing\n"
            )
            continue

        # Renderer wrote files directly to case_dir; just register them in
        # the manifest (no double-write).
        for f in result.files:
            st.out_dir.record_case_artifact(
                case_nodeid=item.nodeid,
                filename=str(f),
                kind=kind,
            )
        if result.metrics:
            metrics_bytes = json.dumps(dict(result.metrics), indent=2, default=str).encode("utf-8")
            st.out_dir.write_case_artifact(
                case_nodeid=item.nodeid,
                filename="metrics.json",
                content=metrics_bytes,
                kind=kind,
            )

    if st.worker_temp is not None and report is not None:
        case_dir = st.out_dir.case_kind_dir(case_nodeid=item.nodeid, kind=".")
        report.prism_artifacts = [
            {
                "filename": path.name,
                "kind": path.parent.name,
                "content": base64.b64encode(path.read_bytes()).decode("ascii"),
            }
            for path in case_dir.rglob("*")
            if path.is_file()
        ]


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    st: _State | None = getattr(session.config, "_prism_state", None)
    if st is None:
        return
    if st.worker_temp is not None:
        session.config.workeroutput["prism_interrupted"] = st.interrupted  # type: ignore[attr-defined]
        return
    st.exitstatus = exitstatus
    fail_on_err = session.config.getoption("--prism-fail-on-hook-error")

    hook_post_results: dict[str, dict[str, Any]] = {}
    for name, hook in st.registry.session_hooks.items():
        ctx = SessionContext(
            run_dir=st.out_dir.root,
            hook_dir=st.out_dir.session_dir(name),
            config=st.cfg,
            logger=logging.getLogger(f"pytest_prism.session.{name}"),
        )
        try:
            hook_post_results[name] = dict(hook.session_post(ctx) or {})
        except Exception as exc:
            (ctx.hook_dir / "error.log").write_text(
                f"session_post raised: {exc}\n\n{traceback.format_exc()}"
            )
            if fail_on_err:
                raise
            sys.stderr.write(f"pytest-prism: session_post {name!r} raised: {exc}; continuing\n")
            hook_post_results[name] = {"error": str(exc)}

    st.hook_post_results = hook_post_results


def pytest_unconfigure(config: pytest.Config) -> None:
    st: _State | None = getattr(config, "_prism_state", None)
    if st is None:
        return
    if st.worker_temp is not None:
        st.worker_temp.cleanup()
        return
    if st.original_streams is not None and st.tee_streams is not None:
        if sys.stdout is st.tee_streams[0]:
            sys.stdout = st.original_streams[0]
        if sys.stderr is st.tee_streams[1]:
            sys.stderr = st.original_streams[1]

    # Capture terminal log
    if st.terminal_buffer is not None:
        raw_text = st.terminal_buffer.getvalue()
        ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        clean_text = ansi_escape.sub("", raw_text)
        st.out_dir.write_run_artifact(
            "terminal.log", clean_text.encode("utf-8"), kind="terminal_log"
        )

    hardware = {**st.hook_pre_results.get("labgrid", {}), **st.hook_post_results.get("labgrid", {})}
    if hardware:
        tags = hardware.get("tags", {})
        for field, tag in (("board", "daughter-board"), ("carrier", "carrier")):
            if tag in tags:
                hardware.setdefault(field, tags[tag])
        errors = [
            str(value)
            for key, value in hardware.items()
            if value and (key.endswith("_error") or key == "error")
        ]
        hardware["collection_errors"] = list(
            dict.fromkeys([*hardware.get("collection_errors", []), *errors])
        )
    run_meta = {
        "started_at": st.started_at,
        "ended_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "tags": dict(st.cfg.user_tags),
        "plugin_version": _PLUGIN_VERSION,
        "session_pre": st.hook_pre_results,
        "session_post": st.hook_post_results,
        "exitstatus": st.exitstatus,
        "ci": detect_ci(),
        "hardware": hardware or None,
    }
    st.out_dir.finalize(run_meta=run_meta)
    sys.stderr.write(f"pytest-prism: wrote run to {st.out_dir.root}\n")

    if not st.cfg.upload_url:
        return
    try:
        result = _upload(st.out_dir, st.cfg)
    except UploadError as exc:
        sys.stderr.write(f"pytest-prism: upload failed: {exc}; preserved at {st.out_dir.root}\n")
        if st.cfg.fail_on_upload_error:
            sys.exit(5)
        return
    sys.stderr.write(
        f"pytest-prism: uploaded run {result.run_id} (status={result.status}) "
        f"-> {st.cfg.upload_url}{result.url}\n"
    )
