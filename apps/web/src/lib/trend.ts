import type { TrendPoint } from '../api/types';

/** Distinct tag keys present across the trend's points, sorted for a stable selector. */
export function tagKeysFor(points: TrendPoint[]): string[] {
  const keys = new Set<string>();
  for (const p of points) {
    for (const k of Object.keys(p.tags)) keys.add(k);
  }
  return [...keys].sort();
}

export interface TrendGroup {
  /** The tag value shared by every point in the group; '(none)' when the tag is absent. */
  value: string;
  points: TrendPoint[];
}

/**
 * Split trend points into one series per distinct value of `tagKey`, preserving
 * input order within each group. Points lacking the tag fall into a '(none)'
 * group. Groups are sorted by value with '(none)' last so legends read stably.
 */
export function groupTrendByTag(points: TrendPoint[], tagKey: string): TrendGroup[] {
  const NONE = '(none)';
  const byValue = new Map<string, TrendPoint[]>();
  for (const p of points) {
    const v = p.tags[tagKey] ?? NONE;
    const bucket = byValue.get(v);
    if (bucket) bucket.push(p);
    else byValue.set(v, [p]);
  }
  return [...byValue.entries()]
    .map(([value, pts]) => ({ value, points: pts }))
    .sort((a, b) => {
      if (a.value === NONE) return 1;
      if (b.value === NONE) return -1;
      return a.value.localeCompare(b.value);
    });
}
