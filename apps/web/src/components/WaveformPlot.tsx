import { Box, Text } from '@chakra-ui/react';
import Plotly from 'plotly.js-basic-dist';
import createPlotlyComponent from 'react-plotly.js/factory';

import { useWaveform } from '../api/queries';

const Plot = createPlotlyComponent(Plotly as object);

export function WaveformPlot({ artifactId }: { artifactId: string }) {
  const q = useWaveform(artifactId, 4000);
  if (q.isLoading) return <Text>Loading waveform…</Text>;
  if (q.isError || !q.data) return <Text color="red.400">Failed to load waveform</Text>;
  const { samples, sample_rate, stride, total_samples } = q.data;
  const x = sample_rate
    ? samples.map((_, i) => (i * stride) / sample_rate)
    : samples.map((_, i) => i * stride);
  const xTitle = sample_rate ? 'Time (s)' : 'Sample index';
  return (
    <Box>
      <Plot
        data={[{ x, y: samples, type: 'scatter', mode: 'lines', line: { color: '#63b3ed', width: 1 } }]}
        layout={{
          paper_bgcolor: '#171923',
          plot_bgcolor: '#0a0e13',
          font: { color: '#e2e8f0' },
          margin: { l: 50, r: 20, t: 20, b: 40 },
          xaxis: { title: { text: xTitle }, gridcolor: '#2d3748' },
          yaxis: { title: { text: 'Amplitude' }, gridcolor: '#2d3748' },
          height: 320,
          autosize: true,
        }}
        config={{ displaylogo: false, responsive: true }}
        style={{ width: '100%' }}
      />
      <Text fontSize="xs" color="gray.500" mt={1}>
        {total_samples.toLocaleString()} samples ({stride}× decimated)
      </Text>
    </Box>
  );
}
