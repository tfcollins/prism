import { Box, Text } from '@chakra-ui/react';
import { useQueries } from '@tanstack/react-query';
import Plotly from 'plotly.js-basic-dist';
import createPlotlyComponent from 'react-plotly.js/factory';

import { api } from '../api/client';
import type { FFTResponse } from '../api/types';
import { useColorMode } from '../colorMode';
import type { OverlayTrace } from './OverlayWaveformPlot';
import { plotLayoutColors } from './plotLayout';

const Plot = createPlotlyComponent(Plotly as object);

const PALETTE = ['#63b3ed', '#fc8181', '#68d391', '#f6ad55', '#b794f4', '#76e4f7'];

const DEFAULT_PARAMS = { window: 'hann', nfft: 1024, overlap: 0.5 };

export function OverlayFFTPlot({ traces }: { traces: OverlayTrace[] }) {
  const { colorMode } = useColorMode();
  const queries = useQueries({
    queries: traces.map((t) => ({
      queryKey: ['artifacts', t.artifactId, 'fft', DEFAULT_PARAMS],
      queryFn: async () =>
        (
          await api.get<FFTResponse>(`/artifacts/${t.artifactId}/fft`, {
            params: DEFAULT_PARAMS,
          })
        ).data,
    })),
  });

  if (queries.some((q) => q.isLoading)) return <Text>Loading FFTs…</Text>;
  const failed = queries.findIndex((q) => q.isError || !q.data);
  if (failed >= 0) {
    return <Text color="red.400">Failed to load FFT for {traces[failed].label}</Text>;
  }

  const plotData = queries.map((q, i) => {
    const data = q.data!;
    const dB = data.magnitudes.map((m) => 20 * Math.log10(Math.max(m, 1e-12)));
    return {
      x: data.frequencies,
      y: dB,
      type: 'scatter' as const,
      mode: 'lines' as const,
      name: traces[i].label,
      line: { color: PALETTE[i % PALETTE.length], width: 1 },
    };
  });

  const c = plotLayoutColors(colorMode);
  return (
    <Box>
      <Plot
        data={plotData}
        layout={{
          paper_bgcolor: c.paper,
          plot_bgcolor: c.plot,
          font: { color: c.font },
          margin: { l: 50, r: 20, t: 20, b: 40 },
          xaxis: { title: { text: 'Frequency (Hz)' }, gridcolor: c.grid },
          yaxis: { title: { text: 'Magnitude (dB)' }, gridcolor: c.grid },
          showlegend: true,
          legend: { orientation: 'h', y: -0.2 },
          height: 360,
          autosize: true,
        }}
        config={{ displaylogo: false, responsive: true }}
        style={{ width: '100%' }}
      />
    </Box>
  );
}
