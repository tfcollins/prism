import type { Config } from 'plotly.js';

import type { ColorMode } from '../colorMode';

/**
 * Mode-aware Plotly layout colors. Kept centralized so all four plot
 * components stay in visual sync when the color mode flips. Mirrors the
 * corresponding `--prism-bg-surface` / `--prism-bg-plot` / `--prism-text`
 * / `--prism-border` tokens from theme.ts — Plotly needs literal color
 * strings, not CSS vars.
 */
/**
 * Instrument-panel plot palette. Plots sit on a near-black "scope" surface in
 * both modes (an oscilloscope/spectrum-analyzer reads on black regardless of
 * the surrounding UI theme), with a faint graticule and the mono UI font so the
 * embedded Plotly canvas stops looking like a foreign object.
 */
export function plotLayoutColors(mode: ColorMode) {
  if (mode === 'light') {
    return {
      paper: '#ffffff',
      plot: '#0c1322',
      font: '#0c1322',
      plotFont: '#e5e7eb',
      grid: 'rgba(148, 163, 184, 0.18)',
    };
  }
  return {
    paper: '#111827',
    plot: '#04060c',
    font: '#f9fafb',
    plotFont: '#cbd5e0',
    grid: 'rgba(148, 163, 184, 0.14)',
  };
}

/** Font stack Plotly should use so axis/legend text matches the app. */
export const PLOT_FONT_FAMILY = "'IBM Plex Mono', ui-monospace, 'SF Mono', Menlo, monospace";

/**
 * Shared Plotly `config`. Hides the logo and the busy default modebar (it only
 * appears on hover and is stripped to the useful zoom/reset controls), so the
 * chart reads as part of the UI rather than an embedded tool.
 */
export const PLOT_CONFIG: Partial<Config> = {
  displaylogo: false,
  responsive: true,
  displayModeBar: 'hover',
  modeBarButtonsToRemove: [
    'lasso2d',
    'select2d',
    'autoScale2d',
    'toggleSpikelines',
    'hoverClosestCartesian',
    'hoverCompareCartesian',
  ],
};

/** Static config (no modebar at all) for compact, non-interactive charts. */
export const PLOT_CONFIG_STATIC: Partial<Config> = {
  displaylogo: false,
  responsive: true,
  displayModeBar: false,
};

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
    font: { color: c.font, family: PLOT_FONT_FAMILY, size: 11 },
    margin: { l: 60, r: 20, t: 20, b: 48 },
    xaxis: axis(opts.x),
    yaxis: axis(opts.y),
    height: opts.height ?? 340,
    autosize: true,
  };
}
