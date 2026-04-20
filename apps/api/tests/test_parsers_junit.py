from pathlib import Path

from prism_api.parsers.junit import ParsedCase, ParsedSuite, parse_junit_xml


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
