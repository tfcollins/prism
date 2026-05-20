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

/**
 * Categorical trace palette (Okabe–Ito) — colour-blind safe and consistent
 * across overlays, trends, and compare so a given run reads the same colour
 * everywhere. Index into it with the trace/run position.
 */
export const TRACE_PALETTE = [
  '#56b4e9', // sky blue
  '#e69f00', // orange
  '#009e73', // green
  '#f0e442', // yellow
  '#d55e00', // vermillion
  '#cc79a7', // reddish purple
  '#0072b2', // blue
  '#999999', // grey
];

export function traceColor(i: number): string {
  return TRACE_PALETTE[i % TRACE_PALETTE.length];
}

interface AnalyzerAxis {
  title: string;
  /** Engineering SI tick formatting with a unit suffix (e.g. frequency in Hz). */
  eng?: boolean;
  suffix?: string;
}

/**
 * Shared analyzer-style Plotly layout: dark/light aware, faint graticule, and
 * optional engineering ('~s' SI) tick formatting on either axis. Centralised so
 * WaveformPlot / FFTPlot / SpectrumPlot / TrendPlot stay visually identical.
 */
export function analyzerLayout(
  mode: ColorMode,
  opts: { x: AnalyzerAxis; y: AnalyzerAxis; height?: number },
) {
  const c = plotLayoutColors(mode);
  const axis = (a: AnalyzerAxis) => ({
    title: { text: a.title },
    gridcolor: c.grid,
    zeroline: false,
    ...(a.eng ? { tickformat: '~s' } : {}),
    ...(a.suffix ? { ticksuffix: a.suffix } : {}),
  });
  return {
    paper_bgcolor: c.paper,
    plot_bgcolor: c.plot,
    font: { color: c.font },
    margin: { l: 60, r: 20, t: 20, b: 48 },
    xaxis: axis(opts.x),
    yaxis: axis(opts.y),
    height: opts.height ?? 340,
    autosize: true,
  };
}
