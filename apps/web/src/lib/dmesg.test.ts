import { describe, expect, it } from 'vitest';

import { classifyLine, classifyLines, matchesFilter } from './dmesg';

// Mirrors apps/api/tests/test_parsers_logs.py so the TS classifier stays in
// parity with the server's parsers/logs.py::_classify.
const BOOT = `[    0.000000] Linux version 6.1.0-g1a2b3c4 (jenkins@build) (gcc 12) #1 SMP
[    0.000000] Machine model: Analog Devices ZynqMP ZCU102 Rev1.0
HDL git hash: deadbeef1234
[    1.100000] <6> usb 1-1: new high-speed USB device
[    1.200000] <4> spi-nor: warning: unknown flash id
[    1.300000] ad9361 spi0.0: probe failed with error -110
[    1.400000] <3> mmc0: error -84 reading sector
[    2.000000] Kernel panic - not syncing: oops
`;

describe('classifyLine', () => {
  it('flags kernel panic (and panic wins over a syslog/keyword)', () => {
    expect(classifyLine('[    2.000000] Kernel panic - not syncing: oops')).toBe('panic');
    expect(classifyLine('BUG: unable to handle kernel paging request')).toBe('panic');
  });

  it('flags probe failures before the generic error rule', () => {
    expect(classifyLine('[    1.300000] ad9361 spi0.0: probe failed with error -110')).toBe(
      'probe_fail',
    );
  });

  it('reads syslog levels: <=3 error, ==4 warn, others fall through', () => {
    expect(classifyLine('[    1.400000] <3> mmc0: error -84 reading sector')).toBe('error');
    expect(classifyLine('[    1.200000] <4> spi-nor: unknown flash id')).toBe('warn');
    expect(classifyLine('[    1.100000] <6> usb 1-1: new high-speed USB device')).toBe(null);
  });

  it('falls back to error/warn keywords', () => {
    expect(classifyLine('some plain error happened')).toBe('error');
    expect(classifyLine('a warning here')).toBe('warn');
  });

  it('returns null for plain info lines', () => {
    expect(classifyLine('[    0.000000] Linux version 6.1.0-g1a2b3c4 (gcc)')).toBe(null);
    expect(classifyLine('nothing interesting here')).toBe(null);
  });
});

describe('classifyLines', () => {
  it('classifies each line, 1-indexed, with no trailing empty line', () => {
    const lines = classifyLines(BOOT);
    expect(lines).toHaveLength(8);
    expect(lines[0]).toMatchObject({ lineNo: 1, severity: null });
    expect(lines[7]).toMatchObject({ lineNo: 8, severity: 'panic' });
    const sev = lines
      .map((l) => l.severity)
      .filter((s): s is NonNullable<typeof s> => s !== null)
      .sort();
    expect(sev).toEqual(['error', 'panic', 'probe_fail', 'warn']);
  });
});

describe('matchesFilter', () => {
  it('errors = panic + error + probe_fail', () => {
    expect(matchesFilter('panic', 'errors')).toBe(true);
    expect(matchesFilter('error', 'errors')).toBe(true);
    expect(matchesFilter('probe_fail', 'errors')).toBe(true);
    expect(matchesFilter('warn', 'errors')).toBe(false);
    expect(matchesFilter(null, 'errors')).toBe(false);
  });

  it('warnings = warn only', () => {
    expect(matchesFilter('warn', 'warnings')).toBe(true);
    expect(matchesFilter('error', 'warnings')).toBe(false);
  });

  it('all = every line including info', () => {
    expect(matchesFilter(null, 'all')).toBe(true);
    expect(matchesFilter('error', 'all')).toBe(true);
  });
});
