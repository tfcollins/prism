import type { Measurement } from '../api/types';

export type MeasurementStatus = 'pass' | 'warn' | 'fail' | 'none';

const SI_PREFIXES: Array<[number, string]> = [
  [1e9, 'G'],
  [1e6, 'M'],
  [1e3, 'k'],
  [1, ''],
  [1e-3, 'm'],
  [1e-6, 'µ'],
  [1e-9, 'n'],
];

/**
 * Engineering-notation format: 2.4e9 with unit "Hz" → "2.4 GHz".
 * Pure-ratio units (dB, dBm, dBc, %) are never SI-prefixed — a "kdBm" is
 * meaningless — so those pass through with fixed decimals.
 */
export function formatEng(value: number, unit: string | null, sigDigits = 3): string {
  if (!Number.isFinite(value)) return `${value}`;
  const u = unit ?? '';
  // Ratio/logarithmic units don't take SI prefixes ("kdBm" is meaningless).
  const isRatioUnit = u === '' || /^dB/.test(u) || u === '%';
  if (isRatioUnit) {
    const fixed = Number(value.toFixed(2));
    return unit ? `${fixed} ${unit}` : `${fixed}`;
  }
  const abs = Math.abs(value);
  let prefix = '';
  let scaled = value;
  for (const [factor, p] of SI_PREFIXES) {
    if (abs >= factor || factor === 1e-9) {
      scaled = value / factor;
      prefix = p;
      break;
    }
  }
  const rounded = Number(scaled.toPrecision(sigDigits));
  return `${rounded} ${prefix}${unit}`;
}

/**
 * Derive a display status for a measurement. `warnFraction` is the slice of the
 * spec window (or of |value| when only one limit exists) within which an
 * in-spec measurement is flagged amber rather than green.
 */
export function measurementStatus(m: Measurement, warnFraction = 0.1): MeasurementStatus {
  if (m.in_spec === null || m.margin === null) return 'none';
  if (!m.in_spec) return 'fail';
  let reference: number;
  if (m.spec_min !== null && m.spec_max !== null) {
    reference = Math.abs(m.spec_max - m.spec_min);
  } else {
    reference = Math.abs(m.value) || 1;
  }
  return m.margin < warnFraction * reference ? 'warn' : 'pass';
}

export const STATUS_GLYPH: Record<MeasurementStatus, string> = {
  pass: '✓',
  warn: '△',
  fail: '✕',
  none: '·',
};
