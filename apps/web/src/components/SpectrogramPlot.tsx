import { Box, Text } from '@chakra-ui/react';
import Plotly from 'plotly.js-cartesian-dist-min';
import createPlotlyComponent from 'react-plotly.js/factory';

import { useSpectrogram } from '../api/queries';
import { useColorMode } from '../colorMode';
import { plotLayoutColors } from './plotLayout';
import { PlotSkeleton } from './PlotSkeleton';

// The basic dist lacks the heatmap trace, so the spectrogram view uses the
// cartesian dist exclusively (separate Plotly factory from the other plots).
const Plot = createPlotlyComponent(Plotly as object);

export function SpectrogramPlot({ artifactId }: { artifactId: string }) {
  const q = useSpectrogram(artifactId);
  const { colorMode } = useColorMode();

  if (q.isLoading) return <PlotSkeleton height={360} label="Loading spectrogram…" />;
  if (q.isError || !q.data) return <Text color="red.400">Failed to load spectrogram</Text>;
  if (q.data.powers.length === 0) {
    return (
      <Text color="var(--prism-text-subtle)" fontSize="sm">
        Spectrogram has no data.
      </Text>
    );
  }

  const c = plotLayoutColors(colorMode);
  const { frequencies, times, powers, unit } = q.data;

  return (
    <Box>
      <Plot
        data={[
          {
            type: 'heatmap',
            x: frequencies,
            y: times,
            z: powers,
            colorscale: 'Viridis',
            colorbar: { title: { text: unit ?? 'power' } },
          },
        ]}
        layout={{
          paper_bgcolor: c.paper,
          plot_bgcolor: c.plot,
          font: { color: c.font },
          margin: { l: 64, r: 20, t: 20, b: 48 },
          xaxis: { title: { text: 'Frequency' }, tickformat: '~s', ticksuffix: 'Hz' },
          yaxis: { title: { text: 'Time (s)' } },
          height: 380,
          autosize: true,
        }}
        config={{ displaylogo: false, responsive: true }}
        style={{ width: '100%' }}
      />
    </Box>
  );
}
