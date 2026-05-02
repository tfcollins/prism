import { Box, Text } from '@chakra-ui/react';
import type { Data, Layout } from 'plotly.js';
import Plotly from 'plotly.js-basic-dist';
import createPlotlyComponent from 'react-plotly.js/factory';

import { useArtifactJson } from '../api/queries';
import { useColorMode } from '../colorMode';
import { plotLayoutColors } from './plotLayout';

const Plot = createPlotlyComponent(Plotly as object);

interface PlotlyFigureSpec {
  data: Data[];
  layout: Partial<Layout>;
  config?: Record<string, unknown>;
}

export function InlinePlotlyFigure({ artifactId }: { artifactId: string }) {
  const q = useArtifactJson<PlotlyFigureSpec>(artifactId);
  const { colorMode } = useColorMode();

  if (q.isLoading) return <Text>Loading figure…</Text>;
  if (q.isError || !q.data) return <Text color="red.400">Failed to load figure</Text>;

  const c = plotLayoutColors(colorMode);
  // Merge our app-wide colors into the figure's own layout so the upstream
  // figure JSON remains theme-agnostic.
  const layout: Partial<Layout> = {
    ...q.data.layout,
    paper_bgcolor: c.paper,
    plot_bgcolor: c.plot,
    font: { color: c.font },
    autosize: true,
  };

  return (
    <Box>
      <Plot
        data={q.data.data}
        layout={layout}
        config={{ displaylogo: false, responsive: true, ...(q.data.config ?? {}) }}
        style={{ width: '100%', minHeight: '500px' }}
        useResizeHandler
      />
    </Box>
  );
}
