"""JUnit XML parser — thin wrapper over `junitparser`."""

from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO

from junitparser import Error, Failure, JUnitXml, Properties, Skipped
from junitparser import TestCase as JTCase


@dataclass
class ParsedMeasurement:
    name: str
    value: float
    unit: str | None = None
    spec_min: float | None = None
    spec_max: float | None = None


@dataclass
class ParsedCase:
    classname: str
    name: str
    status: str  # pass | fail | error | skip
    duration_ms: int
    failure_message: str | None = None
    failure_trace: str | None = None
    measurements: list[ParsedMeasurement] = field(default_factory=list)


@dataclass
class ParsedSuite:
    name: str
    pass_count: int = 0
    fail_count: int = 0
    error_count: int = 0
    skip_count: int = 0
    duration_ms: int = 0
    cases: list[ParsedCase] = field(default_factory=list)


_SPEC_SUFFIXES = ("__unit", "__min", "__max")


def _float_or_none(raw: str | None) -> float | None:
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _case_measurements(case: JTCase) -> list[ParsedMeasurement]:
    """Extract numeric `<property>` entries as measurements.

    Convention: a property whose value parses as a float is a measurement.
    Sibling properties named ``{name}__unit`` / ``{name}__min`` / ``{name}__max``
    supply its unit and spec limits. Non-numeric properties (e.g. git_sha) and
    the spec-suffix properties themselves are not emitted as measurements.
    """
    container = case.child(Properties)  # type: ignore[no-untyped-call]
    if container is None:
        return []
    props: dict[str, str] = {p.name: p.value for p in container if p.name is not None}
    out: list[ParsedMeasurement] = []
    for name, raw in props.items():
        if name.endswith(_SPEC_SUFFIXES):
            continue
        value = _float_or_none(raw)
        if value is None:
            continue
        out.append(
            ParsedMeasurement(
                name=name,
                value=value,
                unit=props.get(f"{name}__unit"),
                spec_min=_float_or_none(props.get(f"{name}__min")),
                spec_max=_float_or_none(props.get(f"{name}__max")),
            )
        )
    return out


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
                    measurements=_case_measurements(c),
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
