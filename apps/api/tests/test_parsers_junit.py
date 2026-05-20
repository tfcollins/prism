from pathlib import Path

from prism_api.parsers.junit import (
    ParsedCase,
    ParsedMeasurement,
    ParsedSuite,
    parse_junit_xml,
)


def test_parse_sample() -> None:
    xml = Path(__file__).parent / "fixtures" / "sample-junit.xml"
    result = parse_junit_xml(xml.read_bytes())
    assert len(result) == 2
    dsp, api = result
    assert isinstance(dsp, ParsedSuite)
    assert dsp.name == "dsp"
    assert dsp.pass_count == 2
    assert dsp.fail_count == 1
    assert dsp.error_count == 0
    assert dsp.skip_count == 0
    assert len(dsp.cases) == 3
    sweep = next(c for c in dsp.cases if c.name == "sine_sweep_5khz")
    assert isinstance(sweep, ParsedCase)
    assert sweep.classname == "codec"
    assert sweep.status == "fail"
    assert "SNR" in (sweep.failure_message or "")
    assert api.name == "api"
    assert api.pass_count == 1


def test_parse_empty_wrapper() -> None:
    empty = b'<?xml version="1.0"?><testsuites></testsuites>'
    assert parse_junit_xml(empty) == []


_MEAS_XML = b"""<?xml version="1.0"?><testsuites>
<testsuite name="rf" tests="1" failures="0" time="0.1">
<testcase classname="acpr" name="lower" time="0.05">
<properties>
<property name="channel_power_dBm" value="-10.2"/>
<property name="channel_power_dBm__unit" value="dBm"/>
<property name="channel_power_dBm__max" value="-9.0"/>
<property name="channel_power_dBm__min" value="-12.0"/>
<property name="acpr_dBc" value="-45.3"/>
<property name="acpr_dBc__max" value="-40.0"/>
<property name="git_sha" value="abc123"/>
</properties>
</testcase>
</testsuite></testsuites>"""


def test_parse_testcase_measurements() -> None:
    [suite] = parse_junit_xml(_MEAS_XML)
    [case] = suite.cases
    by_name = {m.name: m for m in case.measurements}
    # Two numeric measurements; the non-numeric git_sha property is ignored.
    assert set(by_name) == {"channel_power_dBm", "acpr_dBc"}
    cp = by_name["channel_power_dBm"]
    assert isinstance(cp, ParsedMeasurement)
    assert cp.value == -10.2
    assert cp.unit == "dBm"
    assert cp.spec_min == -12.0
    assert cp.spec_max == -9.0
    acpr = by_name["acpr_dBc"]
    assert acpr.value == -45.3
    assert acpr.unit is None
    assert acpr.spec_min is None
    assert acpr.spec_max == -40.0


def test_parse_no_measurements_when_no_properties() -> None:
    [suite] = parse_junit_xml(
        b'<?xml version="1.0"?><testsuites>'
        b'<testsuite name="s" tests="1"><testcase classname="c" name="t" time="0.1"/>'
        b"</testsuite></testsuites>"
    )
    assert suite.cases[0].measurements == []
