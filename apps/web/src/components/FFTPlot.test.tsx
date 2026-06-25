import { ChakraProvider } from '@chakra-ui/react';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { system } from '../theme';

// Plotly is unusable in jsdom — mock the factory to a component that renders the
// text of any markers+text trace, so we can assert overlaid marker labels.
vi.mock('plotly.js-basic-dist', () => ({ default: {} }));
vi.mock('react-plotly.js/factory', () => ({
  default: () => (props: { data?: { text?: string[] }[] }) => (
    <div data-testid="plot">{(props.data ?? []).flatMap((t) => t.text ?? []).join(' ')}</div>
  ),
}));

const FFT = { frequencies: [0, 1000, 2000], magnitudes: [0.01, 1.0, 0.02], sample_rate: 8000 };
const GENALYZER = {
  markers: [
    { label: 'Fund', frequency: 1000, mag_dbfs: -1 },
    { label: 'HD2', frequency: 2000, mag_dbfs: -70 },
  ],
  snr: 84.2,
  sfdr: 91.5,
  sinad: 83.9,
  thd: -88.1,
  enob: 13.6,
  fsnr: 84.0,
};

vi.mock('../api/queries', () => ({
  useFFT: () => ({ data: FFT, isLoading: false, isError: false }),
  useGenalyzer: () => ({ data: GENALYZER, isLoading: false, isError: false }),
}));

vi.mock('../colorMode', () => ({ useColorMode: () => ({ colorMode: 'dark' }) }));

import { FFTPlot } from './FFTPlot';

function renderPlot() {
  return render(
    <ChakraProvider value={system}>
      <FFTPlot artifactId="a1" />
    </ChakraProvider>,
  );
}

describe('FFTPlot genalyzer markers', () => {
  it('hides markers and metrics until toggled on', () => {
    renderPlot();
    expect(screen.queryByText('Fund')).toBeNull();
    expect(screen.queryByText(/SNR/i)).toBeNull();
  });

  it('overlays marker labels and a metrics panel when toggled on', () => {
    renderPlot();
    fireEvent.click(screen.getByRole('button', { name: /genalyzer/i }));
    // marker labels reach the (mocked) plot trace
    expect(screen.getByTestId('plot').textContent).toContain('Fund');
    expect(screen.getByTestId('plot').textContent).toContain('HD2');
    // metrics panel
    expect(screen.getByText(/SNR/i)).toBeInTheDocument();
    expect(screen.getByText(/84\.2/)).toBeInTheDocument();
    expect(screen.getByText(/SFDR/i)).toBeInTheDocument();
  });
});
