import { Box, Text } from '@chakra-ui/react';
import Plotly from 'plotly.js-basic-dist';
import createPlotlyComponent from 'react-plotly.js/factory';

import { useFFT } from '../api/queries';
import { useColorMode } from '../colorMode';
import { analyzerLayout, traceColor } from './plotLayout';
import { PlotSkeleton } from './PlotSkeleton';

const Plot = createPlotlyComponent(Plotly as object);

export function FFTPlot({ artifactId }: { artifactId: string }) {
  const q = useFFT(artifactId);
  const { colorMode } = useColorMode();
  if (q.isLoading) return <PlotSkeleton height={320} label="Loading FFT…" />;
  if (q.isError || !q.data) return <Text color="red.400">Failed to load FFT</Text>;
  const { frequencies, magnitudes, sample_rate } = q.data;
  const dB = magnitudes.map((m) => 20 * Math.log10(Math.max(m, 1e-12)));
  return (
    <Box>
      <Plot
        data={[
          {
            x: frequencies,
            y: dB,
            type: 'scatter',
            mode: 'lines',
            line: { color: traceColor(4), width: 1 },
          },
        ]}
        layout={analyzerLayout(colorMode, {
          x: { title: 'Frequency', eng: true, suffix: 'Hz' },
          y: { title: 'Magnitude (dB)' },
          height: 320,
        })}
        config={{ displaylogo: false, responsive: true }}
        style={{ width: '100%' }}
      />
      <Text fontSize="xs" color="var(--prism-text-subtle)" mt={1}>
        Sample rate: {sample_rate} Hz
      </Text>
    </Box>
  );
}
