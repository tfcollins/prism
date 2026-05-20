import type { MaskSegment } from '../api/types';

/** Piecewise-constant mask limit at frequency f, or null if f is outside all segments. */
export function maskLimitAt(segments: MaskSegment[], f: number): number | null {
  for (const s of segments) {
    if (f >= s.f_start && f <= s.f_end) return s.max_dbm;
  }
  return null;
}

export interface Violation {
  frequency: number;
  power: number;
  limit: number;
}

/** Spectrum points whose power exceeds the mask limit at their frequency. */
export function findMaskViolations(
  frequencies: number[],
  powers: number[],
  segments: MaskSegment[],
): Violation[] {
  const out: Violation[] = [];
  for (let i = 0; i < frequencies.length; i++) {
    const limit = maskLimitAt(segments, frequencies[i]);
    if (limit !== null && powers[i] > limit) {
      out.push({ frequency: frequencies[i], power: powers[i], limit });
    }
  }
  return out;
}

/**
 * Step-line points (x, y) tracing the mask limit, with vertical jumps between
 * adjacent segments — the shape an analyzer draws for a limit line.
 */
export function maskStepLine(segments: MaskSegment[]): { x: number[]; y: number[] } {
  const x: number[] = [];
  const y: number[] = [];
  for (const s of segments) {
    x.push(s.f_start, s.f_end);
    y.push(s.max_dbm, s.max_dbm);
  }
  return { x, y };
}
