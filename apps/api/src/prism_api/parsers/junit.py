"""JUnit XML parser — thin wrapper over `junitparser`."""

from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO

from junitparser import Error, Failure, JUnitXml, Skipped
from junitparser import TestCase as JTCase


@dataclass
class ParsedCase:
    classname: str
    name: str
    status: str  # pass | fail | error | skip
    duration_ms: int
    failure_message: str | None = None
    failure_trace: str | None = None


@dataclass
class ParsedSuite:
    name: str
    pass_count: int = 0
    fail_count: int = 0
    error_count: int = 0
    skip_count: int = 0
    duration_ms: int = 0
    cases: list[ParsedCase] = field(default_factory=list)


def _case_status(case: JTCase) -> tuple[str, str | None, str | None]:
    for result in case.result or []:
        if isinstance(result, Failure):
            return "fail", result.message, (result.text or None)
        if isinstance(result, Error):
            return "error", result.message, (result.text or None)
        if isinstance(result, Skipped):
            return "skip", result.message, None
    return "pass", None, None


def parse_junit_xml(data: bytes) -> list[ParsedSuite]:
    xml = JUnitXml.fromstring(BytesIO(data).read())
    # `JUnitXml.fromstring` returns either a TestSuites root or a single TestSuite
    suites_iter = xml if hasattr(xml, "__iter__") else [xml]
    out: list[ParsedSuite] = []
    for suite in suites_iter:
        parsed = ParsedSuite(name=suite.name or "", duration_ms=int((suite.time or 0) * 1000))
        for c in suite:
            # junitparser yields TestCase | TestSuite when iterating; for a
            # well-formed JUnit doc each suite contains testcases. Skip
            # anything else defensively.
            if not isinstance(c, JTCase):
                continue
            status, msg, trace = _case_status(c)
            duration_ms = int((c.time or 0) * 1000)
            parsed.cases.append(
                ParsedCase(
                    classname=c.classname or "",
                    name=c.name,
                    status=status,
                    duration_ms=duration_ms,
                    failure_message=msg,
                    failure_trace=trace,
                )
            )
            if status == "pass":
                parsed.pass_count += 1
            elif status == "fail":
                parsed.fail_count += 1
            elif status == "error":
                parsed.error_count += 1
            else:
                parsed.skip_count += 1
        out.append(parsed)
    return out
