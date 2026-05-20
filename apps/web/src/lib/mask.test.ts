import { describe, expect, it } from 'vitest';

import type { MaskSegment } from '../api/types';
import { findMaskViolations, maskLimitAt, maskStepLine } from './mask';

const SEGMENTS: MaskSegment[] = [
  { f_start: 0, f_end: 10, max_dbm: -40 },
  { f_start: 10, f_end: 20, max_dbm: 0 },
  { f_start: 20, f_end: 30, max_dbm: -40 },
];

describe('maskLimitAt', () => {
  it('returns the segment limit covering the frequency', () => {
    expect(maskLimitAt(SEGMENTS, 5)).toBe(-40);
    expect(maskLimitAt(SEGMENTS, 15)).toBe(0);
  });
  it('returns null outside all segments', () => {
    expect(maskLimitAt(SEGMENTS, 100)).toBeNull();
  });
});

describe('findMaskViolations', () => {
  it('flags points above the limit', () => {
    const freqs = [5, 15, 25];
    const powers = [-30, -10, -35]; // 5 and 25 are in the -40 stop bands
    const v = findMaskViolations(freqs, powers, SEGMENTS);
    expect(v.map((x) => x.frequency)).toEqual([5, 25]);
    expect(v[0].limit).toBe(-40);
  });
  it('returns none when all within limit', () => {
    expect(findMaskViolations([5, 15], [-50, -10], SEGMENTS)).toEqual([]);
  });
});

describe('maskStepLine', () => {
  it('traces each segment as a flat run', () => {
    const { x, y } = maskStepLine(SEGMENTS);
    expect(x).toEqual([0, 10, 10, 20, 20, 30]);
    expect(y).toEqual([-40, -40, 0, 0, -40, -40]);
  });
});
