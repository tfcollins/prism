import { Box, Text } from '@chakra-ui/react';
import Plotly from 'plotly.js-basic-dist';
import createPlotlyComponent from 'react-plotly.js/factory';

import { useFFT } from '../api/queries';
import { useColorMode } from '../colorMode';
import { plotLayoutColors } from './plotLayout';

const Plot = createPlotlyComponent(Plotly as object);

export function FFTPlot({ artifactId }: { artifactId: string }) {
  const q = useFFT(artifactId);
  const { colorMode } = useColorMode();
  if (q.isLoading) return <Text>Loading FFT…</Text>;
  if (q.isError || !q.data) return <Text color="red.400">Failed to load FFT</Text>;
  const { frequencies, magnitudes, sample_rate } = q.data;
  const dB = magnitudes.map((m) => 20 * Math.log10(Math.max(m, 1e-12)));
  const c = plotLayoutColors(colorMode);
  return (
    <Box>
      <Plot
        data={[{ x: frequencies, y: dB, type: 'scatter', mode: 'lines', line: { color: '#fc8181', width: 1 } }]}
        layout={{
          paper_bgcolor: c.paper,
          plot_bgcolor: c.plot,
          font: { color: c.font },
          margin: { l: 50, r: 20, t: 20, b: 40 },
          xaxis: { title: { text: 'Frequency (Hz)' }, gridcolor: c.grid },
          yaxis: { title: { text: 'Magnitude (dB)' }, gridcolor: c.grid },
          height: 320,
          autosize: true,
        }}
        config={{ displaylogo: false, responsive: true }}
        style={{ width: '100%' }}
      />
      <Text fontSize="xs" color="gray.300" mt={1}>
        Sample rate: {sample_rate} Hz
      </Text>
    </Box>
  );
}
