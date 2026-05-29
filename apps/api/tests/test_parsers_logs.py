# apps/api/tests/test_parsers_logs.py
from prism_api.parsers.logs import parse_log

_BOOT = b"""[    0.000000] Linux version 6.1.0-g1a2b3c4 (jenkins@build) (gcc 12) #1 SMP
[    0.000000] Machine model: Analog Devices ZynqMP ZCU102 Rev1.0
HDL git hash: deadbeef1234
[    1.100000] <6> usb 1-1: new high-speed USB device
[    1.200000] <4> spi-nor: warning: unknown flash id
[    1.300000] ad9361 spi0.0: probe failed with error -110
[    1.400000] <3> mmc0: error -84 reading sector
[    2.000000] Kernel panic - not syncing: oops
"""


def test_extracts_commits_version_board() -> None:
    p = parse_log(_BOOT, kernel_pattern=None, hdl_pattern=None, findings_cap=200)
    assert p.kernel_commit == "1a2b3c4"
    assert p.hdl_commit == "deadbeef1234"
    assert p.kernel_version == "6.1.0-g1a2b3c4"
    assert p.board == "Analog Devices ZynqMP ZCU102 Rev1.0"


def test_tallies_and_flags() -> None:
    p = parse_log(_BOOT, kernel_pattern=None, hdl_pattern=None, findings_cap=200)
    assert p.has_panic is True
    assert p.error_count == 1  # the <3> mmc0 error
    assert p.warn_count == 1  # the <4> spi-nor warning
    sev = sorted(f.severity for f in p.findings)
    assert sev == ["error", "panic", "probe_fail", "warn"]


def test_findings_cap_enforced() -> None:
    many = b"\n".join(b"<3> error line %d" % i for i in range(50))
    p = parse_log(many, kernel_pattern=None, hdl_pattern=None, findings_cap=10)
    assert len(p.findings) == 10
    assert p.error_count == 50  # count is full, sample is capped


def test_missing_commits_is_not_fatal() -> None:
    p = parse_log(
        b"nothing interesting here\n", kernel_pattern=None, hdl_pattern=None, findings_cap=5
    )
    assert p.kernel_commit is None and p.hdl_commit is None
    assert p.error_count == 0 and p.has_panic is False
