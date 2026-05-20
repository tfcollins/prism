import { describe, expect, it } from 'vitest';

import type { TrendPoint } from '../api/types';
import { groupTrendByTag, tagKeysFor } from './trend';

function pt(run: string, value: number, tags: Record<string, string>): TrendPoint {
  return {
    run_id: run,
    run_name: run,
    created_at: '2026-01-01T00:00:00Z',
    case_id: `c-${run}`,
    case_name: 'case',
    value,
    unit: 'dBm',
    spec_min: null,
    spec_max: null,
    in_spec: null,
    margin: null,
    tags,
  };
}

describe('tagKeysFor', () => {
  it('returns the sorted union of keys across points', () => {
    const points = [pt('a', 1, { temp: '25', dut: 'x' }), pt('b', 2, { dut: 'y' }), pt('c', 3, {})];
    expect(tagKeysFor(points)).toEqual(['dut', 'temp']);
  });

  it('returns empty when no tags', () => {
    expect(tagKeysFor([pt('a', 1, {})])).toEqual([]);
  });
});

describe('groupTrendByTag', () => {
  it('splits into one group per tag value, preserving order within a group', () => {
    const points = [pt('a', 1, { dut: 'x' }), pt('b', 2, { dut: 'y' }), pt('c', 3, { dut: 'x' })];
    const groups = groupTrendByTag(points, 'dut');
    expect(groups.map((g) => g.value)).toEqual(['x', 'y']);
    expect(groups[0].points.map((p) => p.run_name)).toEqual(['a', 'c']);
    expect(groups[1].points.map((p) => p.run_name)).toEqual(['b']);
  });

  it('buckets points missing the tag into (none), sorted last', () => {
    const points = [pt('a', 1, { dut: 'x' }), pt('b', 2, {})];
    const groups = groupTrendByTag(points, 'dut');
    expect(groups.map((g) => g.value)).toEqual(['x', '(none)']);
    expect(groups[1].points.map((p) => p.run_name)).toEqual(['b']);
  });
});
