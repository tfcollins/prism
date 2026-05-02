"""Unit tests for Config CLI > env > defaults precedence."""

from __future__ import annotations

import pytest

from pytest_prism.config import Config, ConfigError


def test_disabled_when_flag_off() -> None:
    cfg = Config.from_argv([])
    assert cfg.enabled is False
    assert cfg.out_dir is None
    assert cfg.upload_url is None


def test_enabled_via_cli_flag() -> None:
    cfg = Config.from_argv(["--prism-report", "--prism-out=./out"])
    assert cfg.enabled is True
    assert str(cfg.out_dir) == "./out" or str(cfg.out_dir) == "out"


def test_enabled_via_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRISM_REPORT", "1")
    cfg = Config.from_argv([])
    assert cfg.enabled is True


def test_cli_overrides_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRISM_OUT", "/tmp/from-env")
    cfg = Config.from_argv(["--prism-report", "--prism-out=/tmp/from-cli"])
    assert str(cfg.out_dir) == "/tmp/from-cli"


def test_default_out_dir_when_no_url() -> None:
    cfg = Config.from_argv(["--prism-report"])
    assert cfg.out_dir is not None
    assert "prism-report-" in str(cfg.out_dir)


def test_url_requires_project() -> None:
    with pytest.raises(ConfigError, match="--prism-project"):
        Config.from_argv(
            [
                "--prism-report",
                "--prism-url=http://x",
                "--prism-email=a",
                "--prism-password=b",
            ]
        )


def test_no_labgrid_conflicts_with_place() -> None:
    with pytest.raises(ConfigError, match="conflicts"):
        Config.from_argv(["--prism-report", "--prism-no-labgrid", "--prism-labgrid-place=p"])


def test_tag_format_validated() -> None:
    with pytest.raises(ConfigError, match="key=value"):
        Config.from_argv(["--prism-report", "--prism-tag=badtag"])


def test_tag_parsed() -> None:
    cfg = Config.from_argv(["--prism-report", "--prism-tag=k1=v1", "--prism-tag=k2=v2"])
    assert cfg.user_tags == {"k1": "v1", "k2": "v2"}
