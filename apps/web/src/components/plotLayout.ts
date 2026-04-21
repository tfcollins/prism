import type { ColorMode } from '../colorMode';

/**
 * Mode-aware Plotly layout colors. Kept centralized so all four plot
 * components stay in visual sync when the color mode flips.
 */
export function plotLayoutColors(mode: ColorMode) {
  if (mode === 'light') {
    return {
      paper: '#ffffff',
      plot: '#f7fafc',
      font: '#1a202c',
      grid: '#e2e8f0',
    };
  }
  return {
    paper: '#171923',
    plot: '#0a0e13',
    font: '#e2e8f0',
    grid: '#2d3748',
  };
}
