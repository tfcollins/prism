export type PersistenceMode = 'none' | 'max' | 'min' | 'avg';

/**
 * Combine several equal-length traces into one per-bin aggregate (max-hold,
 * min-hold, or average). Returns null when there are fewer than two traces or
 * their lengths differ — aggregation across mismatched frequency axes would be
 * meaningless, so the caller should fall back to showing individual traces.
 */
export function aggregateTraces(series: number[][], mode: PersistenceMode): number[] | null {
  if (mode === 'none' || series.length < 2) return null;
  const len = series[0].length;
  if (len === 0 || series.some((s) => s.length !== len)) return null;

  const out = new Array<number>(len);
  for (let i = 0; i < len; i++) {
    let acc = mode === 'min' ? Infinity : mode === 'max' ? -Infinity : 0;
    for (const s of series) {
      const v = s[i];
      if (mode === 'max') acc = Math.max(acc, v);
      else if (mode === 'min') acc = Math.min(acc, v);
      else acc += v;
    }
    out[i] = mode === 'avg' ? acc / series.length : acc;
  }
  return out;
}
