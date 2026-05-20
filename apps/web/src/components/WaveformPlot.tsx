import { Box, Text } from '@chakra-ui/react';
import Plotly from 'plotly.js-basic-dist';
import createPlotlyComponent from 'react-plotly.js/factory';

import { useWaveform } from '../api/queries';
import { useColorMode } from '../colorMode';
import { plotLayoutColors } from './plotLayout';

const Plot = createPlotlyComponent(Plotly as object);

export function WaveformPlot({ artifactId }: { artifactId: string }) {
  const q = useWaveform(artifactId, 4000);
  const { colorMode } = useColorMode();
  if (q.isLoading) return <Text>Loading waveform…</Text>;
  if (q.isError || !q.data) return <Text color="red.400">Failed to load waveform</Text>;
  const { samples, sample_rate, stride, total_samples } = q.data;
  const x = sample_rate
    ? samples.map((_, i) => (i * stride) / sample_rate)
    : samples.map((_, i) => i * stride);
  const xTitle = sample_rate ? 'Time (s)' : 'Sample index';
  const c = plotLayoutColors(colorMode);
  return (
    <Box>
      <Plot
        data={[
          { x, y: samples, type: 'scatter', mode: 'lines', line: { color: '#63b3ed', width: 1 } },
        ]}
        layout={{
          paper_bgcolor: c.paper,
          plot_bgcolor: c.plot,
          font: { color: c.font },
          margin: { l: 50, r: 20, t: 20, b: 40 },
          xaxis: { title: { text: xTitle }, gridcolor: c.grid },
          yaxis: { title: { text: 'Amplitude' }, gridcolor: c.grid },
          height: 320,
          autosize: true,
        }}
        config={{ displaylogo: false, responsive: true }}
        style={{ width: '100%' }}
      />
      <Text fontSize="xs" color="var(--prism-text-subtle)" mt={1}>
        {total_samples.toLocaleString()} samples ({stride}× decimated)
      </Text>
    </Box>
  );
}
