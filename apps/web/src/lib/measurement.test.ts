import { describe, expect, it } from 'vitest';

import type { Measurement } from '../api/types';
import { formatEng, measurementStatus } from './measurement';

function meas(over: Partial<Measurement>): Measurement {
  return {
    name: 'm',
    value: 0,
    unit: null,
    spec_min: null,
    spec_max: null,
    in_spec: null,
    margin: null,
    ...over,
  };
}

describe('formatEng', () => {
  it('applies SI prefixes to physical units', () => {
    expect(formatEng(2.4e9, 'Hz')).toBe('2.4 GHz');
    expect(formatEng(10e6, 'Hz')).toBe('10 MHz');
    expect(formatEng(48000, 'Hz')).toBe('48 kHz');
    expect(formatEng(1.5e-3, 's')).toBe('1.5 ms');
  });

  it('does not SI-prefix logarithmic/ratio units', () => {
    expect(formatEng(-10.234, 'dBm')).toBe('-10.23 dBm');
    expect(formatEng(-45.3, 'dBc')).toBe('-45.3 dBc');
    expect(formatEng(99.5, '%')).toBe('99.5 %');
  });

  it('handles unitless values', () => {
    expect(formatEng(3.14159, null)).toBe('3.14');
  });
});

describe('measurementStatus', () => {
  it('is none when there is no spec', () => {
    expect(measurementStatus(meas({ in_spec: null, margin: null }))).toBe('none');
  });

  it('is fail when out of spec', () => {
    expect(measurementStatus(meas({ in_spec: false, margin: -1 }))).toBe('fail');
  });

  it('is warn when inside spec but within the warn band', () => {
    // window of 10, margin 0.5 → < 10% of 10
    const m = meas({ in_spec: true, margin: 0.5, spec_min: 0, spec_max: 10 });
    expect(measurementStatus(m)).toBe('warn');
  });

  it('is pass when comfortably inside spec', () => {
    const m = meas({ in_spec: true, margin: 5, spec_min: 0, spec_max: 10 });
    expect(measurementStatus(m)).toBe('pass');
  });
});
