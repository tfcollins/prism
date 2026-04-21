import type { ColorMode } from '../colorMode';

/**
 * Mode-aware Plotly layout colors. Kept centralized so all four plot
 * components stay in visual sync when the color mode flips. Mirrors the
 * corresponding `--prism-bg-surface` / `--prism-bg-plot` / `--prism-text`
 * / `--prism-border` tokens from theme.ts — Plotly needs literal color
 * strings, not CSS vars.
 */
export function plotLayoutColors(mode: ColorMode) {
  if (mode === 'light') {
    return {
      paper: '#ffffff',
      plot: '#f3f4f6',
      font: '#111827',
      grid: '#e5e7eb',
    };
  }
  return {
    paper: '#111827',
    plot: '#030712',
    font: '#f9fafb',
    grid: '#374151',
  };
}
