import { Box, Flex, Text } from '@chakra-ui/react';
import { useQueries } from '@tanstack/react-query';
import Plotly from 'plotly.js-basic-dist';
import { useState } from 'react';
import createPlotlyComponent from 'react-plotly.js/factory';

import { api } from '../api/client';
import type { FFTResponse } from '../api/types';
import { useColorMode } from '../colorMode';
import { aggregateTraces, type PersistenceMode } from '../lib/persistence';
import type { OverlayTrace } from './OverlayWaveformPlot';
import { plotLayoutColors } from './plotLayout';

const Plot = createPlotlyComponent(Plotly as object);

const PALETTE = ['#63b3ed', '#fc8181', '#68d391', '#f6ad55', '#b794f4', '#76e4f7'];
const HOLD_COLOR = '#fbbf24';

const DEFAULT_PARAMS = { window: 'hann', nfft: 1024, overlap: 0.5 };
const MODES: PersistenceMode[] = ['none', 'max', 'min', 'avg'];
const MODE_LABEL: Record<PersistenceMode, string> = {
  none: 'none',
  max: 'max-hold',
  min: 'min-hold',
  avg: 'average',
};

export function OverlayFFTPlot({ traces }: { traces: OverlayTrace[] }) {
  const { colorMode } = useColorMode();
  const [mode, setMode] = useState<PersistenceMode>('none');
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

  const seriesDb = queries.map((q) =>
    q.data!.magnitudes.map((m) => 20 * Math.log10(Math.max(m, 1e-12))),
  );
  const aggregated = aggregateTraces(seriesDb, mode);

  const plotData: Array<Record<string, unknown>> = queries.map((q, i) => ({
    x: q.data!.frequencies,
    y: seriesDb[i],
    type: 'scatter',
    mode: 'lines',
    name: traces[i].label,
    line: { color: PALETTE[i % PALETTE.length], width: 1 },
    opacity: aggregated ? 0.35 : 1,
  }));
  if (aggregated) {
    plotData.push({
      x: queries[0].data!.frequencies,
      y: aggregated,
      type: 'scatter',
      mode: 'lines',
      name: MODE_LABEL[mode],
      line: { color: HOLD_COLOR, width: 2 },
    });
  }

  const c = plotLayoutColors(colorMode);
  return (
    <Box>
      <Flex gap={2} mb={2} align="center">
        <Text fontSize="xs" color="var(--prism-text-faint)">
          Persistence:
        </Text>
        {MODES.map((m) => (
          <Box
            as="button"
            key={m}
            onClick={() => setMode(m)}
            px={2}
            py="2px"
            borderRadius="sm"
            borderWidth={1}
            fontSize="xs"
            cursor="pointer"
            bg={mode === m ? 'var(--prism-sidebar-active-bg)' : 'var(--prism-bg-surface)'}
            color={mode === m ? 'var(--prism-sidebar-active-fg)' : 'var(--prism-text-muted)'}
            borderColor="var(--prism-border)"
          >
            {MODE_LABEL[m]}
          </Box>
        ))}
      </Flex>
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
