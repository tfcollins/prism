# apps/api/src/prism_api/parsers/logs.py
"""Boot/dmesg log parser.

Extracts kernel + HDL commit, kernel version, board, and a capped sample of
notable lines (panic / error / warn / probe_fail) with full tallies. Pure and
unit-testable; ingest persists the result. Commit patterns are configurable
(first capture group = hash); these defaults are ADI-oriented starting points
and should be confirmed against a real boot log.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

DEFAULT_KERNEL_PATTERN = r"Linux version (\S+)"
DEFAULT_HDL_PATTERN = r"(?i)hdl.*?([0-9a-f]{7,40})\b"
DEFAULT_FINDINGS_CAP = 200

# kernel commit is the trailing -g<sha> of the version token, when present
_KERNEL_SHA = re.compile(r"-g([0-9a-f]{7,40})$")
_VERSION = re.compile(r"Linux version (\S+)")
_BOARD = re.compile(r"(?:Machine model|Hardware name):\s*(.+?)\s*$")
_DMESG_PREFIX = re.compile(r"^\[\s*\d+\.\d+\]\s*")
_SYSLOG = re.compile(r"<(\d)>")

# severity precedence: panic > probe_fail > error > warn (probe phrases contain
# "fail", so they must be matched before the generic error rule)
_PANIC = re.compile(r"(?i)kernel panic|\bOops\b|\bBUG:|Call Trace")
_PROBE = re.compile(r"(?i)probe failed|failed to|timeout")
_ERROR_KW = re.compile(r"(?i)error|fail")
_WARN_KW = re.compile(r"(?i)warn")


@dataclass
class ParsedFinding:
    severity: str          # error | warn | panic | probe_fail
    line_no: int | None
    text: str


@dataclass
class ParsedLog:
    kernel_version: str | None = None
    board: str | None = None
    kernel_commit: str | None = None
    hdl_commit: str | None = None
    error_count: int = 0
    warn_count: int = 0
    has_panic: bool = False
    findings: list[ParsedFinding] = field(default_factory=list)


def _classify(body: str) -> str | None:
    if _PANIC.search(body):
        return "panic"
    if _PROBE.search(body):
        return "probe_fail"
    m = _SYSLOG.search(body)
    if m and int(m.group(1)) <= 3:
        return "error"
    if m and int(m.group(1)) == 4:
        return "warn"
    if _ERROR_KW.search(body):
        return "error"
    if _WARN_KW.search(body):
        return "warn"
    return None


def parse_log(
    data: bytes,
    *,
    kernel_pattern: str | None,
    hdl_pattern: str | None,
    findings_cap: int,
) -> ParsedLog:
    text = data.decode("utf-8", errors="replace")
    kp = re.compile(kernel_pattern) if kernel_pattern else None
    hp = re.compile(hdl_pattern) if hdl_pattern else re.compile(DEFAULT_HDL_PATTERN)
    out = ParsedLog()

    for i, raw in enumerate(text.splitlines()):
        body = _DMESG_PREFIX.sub("", raw)

        if out.kernel_version is None:
            v = _VERSION.search(body)
            if v:
                out.kernel_version = v.group(1)
                sha = _KERNEL_SHA.search(v.group(1))
                if sha:
                    out.kernel_commit = sha.group(1)
        if out.kernel_commit is None and kp:
            km = kp.search(body)
            if km and km.groups():
                out.kernel_commit = km.group(1)
        if out.board is None:
            b = _BOARD.search(body)
            if b:
                out.board = b.group(1)
        if out.hdl_commit is None:
            hm = hp.search(body)
            if hm:
                out.hdl_commit = hm.group(1)

        sev = _classify(body)
        if sev == "panic":
            out.has_panic = True
        elif sev == "error":
            out.error_count += 1
        elif sev == "warn":
            out.warn_count += 1
        if sev is not None and len(out.findings) < findings_cap:
            out.findings.append(ParsedFinding(severity=sev, line_no=i + 1, text=body[:1000]))

    return out
