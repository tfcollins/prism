import { describe, expect, it } from 'vitest';

import { aggregateTraces } from './persistence';

describe('aggregateTraces', () => {
  const a = [1, 5, 3];
  const b = [4, 2, 6];

  it('max-hold takes the per-bin maximum', () => {
    expect(aggregateTraces([a, b], 'max')).toEqual([4, 5, 6]);
  });

  it('min-hold takes the per-bin minimum', () => {
    expect(aggregateTraces([a, b], 'min')).toEqual([1, 2, 3]);
  });

  it('avg takes the per-bin mean', () => {
    expect(aggregateTraces([a, b], 'avg')).toEqual([2.5, 3.5, 4.5]);
  });

  it('returns null for none, single trace, or mismatched lengths', () => {
    expect(aggregateTraces([a, b], 'none')).toBeNull();
    expect(aggregateTraces([a], 'max')).toBeNull();
    expect(aggregateTraces([a, [1, 2]], 'max')).toBeNull();
  });
});
