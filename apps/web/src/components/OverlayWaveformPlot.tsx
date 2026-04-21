import { Box, Text } from '@chakra-ui/react';
import { useQueries } from '@tanstack/react-query';
import Plotly from 'plotly.js-basic-dist';
import createPlotlyComponent from 'react-plotly.js/factory';

import { api } from '../api/client';
import type { WaveformResponse } from '../api/types';

const Plot = createPlotlyComponent(Plotly as object);

const PALETTE = ['#63b3ed', '#fc8181', '#68d391', '#f6ad55', '#b794f4', '#76e4f7'];

export interface OverlayTrace {
  artifactId: string;
  label: string;
}

export function OverlayWaveformPlot({ traces }: { traces: OverlayTrace[] }) {
  const queries = useQueries({
    queries: traces.map((t) => ({
      queryKey: ['artifacts', t.artifactId, 'waveform', 4000],
      queryFn: async () =>
        (
          await api.get<WaveformResponse>(`/artifacts/${t.artifactId}/waveform`, {
            params: { downsample: 4000 },
          })
        ).data,
    })),
  });

  if (queries.some((q) => q.isLoading)) return <Text>Loading waveforms…</Text>;
  const failed = queries.findIndex((q) => q.isError || !q.data);
  if (failed >= 0) {
    return <Text color="red.400">Failed to load waveform for {traces[failed].label}</Text>;
  }

  const plotData = queries.map((q, i) => {
    const data = q.data!;
    const stride = data.stride;
    const sr = data.sample_rate;
    const x = sr
      ? data.samples.map((_, j) => (j * stride) / sr)
      : data.samples.map((_, j) => j * stride);
    return {
      x,
      y: data.samples,
      type: 'scatter' as const,
      mode: 'lines' as const,
      name: traces[i].label,
      line: { color: PALETTE[i % PALETTE.length], width: 1 },
    };
  });

  const xTitle = queries[0].data?.sample_rate ? 'Time (s)' : 'Sample index';

  return (
    <Box>
      <Plot
        data={plotData}
        layout={{
          paper_bgcolor: '#171923',
          plot_bgcolor: '#0a0e13',
          font: { color: '#e2e8f0' },
          margin: { l: 50, r: 20, t: 20, b: 40 },
          xaxis: { title: { text: xTitle }, gridcolor: '#2d3748' },
          yaxis: { title: { text: 'Amplitude' }, gridcolor: '#2d3748' },
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
