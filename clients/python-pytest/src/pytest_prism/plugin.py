"""pytest-prism plugin entry. Wires pytest hooks to the registry."""

from __future__ import annotations

import datetime as _dt
import json
import logging
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

import pytest

from pytest_prism import __version__ as _PLUGIN_VERSION
from pytest_prism.api import (
    _PRISM_PAYLOADS_STASH,
    RenderContext,
    RenderResult,
    SessionContext,
)
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
    hook_pre_results: dict[str, dict] = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.hook_pre_results is None:
            self.hook_pre_results = {}


def pytest_addoption(parser: pytest.Parser) -> None:
    g = parser.getgroup("prism_report", "Prism test-report plugin")
    g.addoption("--prism-report", action="store_true", default=False)
    g.addoption("--prism-out", default=None)
    g.addoption("--prism-out-overwrite", action="store_true", default=False)
    g.addoption("--prism-url", default=None)
    g.addoption("--prism-email", default=None)
    g.addoption("--prism-password", default=None)
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


def pytest_configure(config: pytest.Config) -> None:
    if not config.getoption("--prism-report"):
        return
    try:
        cfg = Config.from_pytest(config)
    except ConfigError as exc:
        raise pytest.UsageError(f"prism-report: {exc}") from exc

    out_dir = OutputDir(cfg.out_dir)
    overwrite = config.getoption("--prism-out-overwrite")
    if overwrite and cfg.out_dir is not None and cfg.out_dir.exists():
        import shutil

        shutil.rmtree(cfg.out_dir)
    try:
        out_dir.initialize()
    except SystemExit as exc:
        raise pytest.UsageError(
            f"prism-report: output dir {cfg.out_dir} is not empty; "
            "pass --prism-out-overwrite or pick another path"
        ) from exc

    try:
        registry = load_registry(strict=config.getoption("--prism-strict-registry"))
    except RegistryError as exc:
        raise pytest.UsageError(f"prism-report: {exc}") from exc

    config._prism_state = _State(cfg=cfg, out_dir=out_dir, registry=registry)
    junit_path = cfg.out_dir / "junit.xml"
    config.option.xmlpath = str(junit_path)
    for topic, msg in cfg.warnings.items():
        config.issue_config_time_warning(
            pytest.PytestConfigWarning(f"prism-report: {topic}: {msg}"),
            stacklevel=1,
        )


def pytest_sessionstart(session: pytest.Session) -> None:
    st: _State | None = getattr(session.config, "_prism_state", None)
    if st is None:
        return
    st.started_at = _dt.datetime.now(_dt.timezone.utc).isoformat()
    fail_on_err = session.config.getoption("--prism-fail-on-hook-error")

    if not st.registry.session_hooks:
        return

    def _run_pre(name: str, hook):
        ctx = SessionContext(
            run_dir=st.out_dir.root,
            hook_dir=st.out_dir.session_dir(name),
            config=st.cfg,
            logger=logging.getLogger(f"pytest_prism.session.{name}"),
        )
        try:
            return hook.session_pre(ctx)
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
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo):
    outcome = yield
    outcome.get_result()
    if call.when != "call":
        return
    st: _State | None = getattr(item.config, "_prism_state", None)
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


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    st: _State | None = getattr(session.config, "_prism_state", None)
    if st is None:
        return
    fail_on_err = session.config.getoption("--prism-fail-on-hook-error")

    hook_post_results: dict[str, dict] = {}
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

    run_meta = {
        "started_at": st.started_at,
        "ended_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "tags": dict(st.cfg.user_tags),
        "plugin_version": _PLUGIN_VERSION,
        "session_pre": st.hook_pre_results,
        "session_post": hook_post_results,
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
            session.exitstatus = 5
        return
    sys.stderr.write(
        f"pytest-prism: uploaded run {result.run_id} (status={result.status}) "
        f"-> {st.cfg.upload_url}{result.url}\n"
    )
