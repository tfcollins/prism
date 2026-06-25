import { Box, Button, Flex, Text } from '@chakra-ui/react';
import Plotly from 'plotly.js-basic-dist';
import { useState } from 'react';
import createPlotlyComponent from 'react-plotly.js/factory';

import { useFFT, useGenalyzer } from '../api/queries';
import { useColorMode } from '../colorMode';
import { analyzerLayout, traceColor } from './plotLayout';
import { PlotSkeleton } from './PlotSkeleton';

const Plot = createPlotlyComponent(Plotly as object);

function Metric({ label, value, unit }: { label: string; value: number | null; unit: string }) {
  return (
    <Text as="span" fontSize="xs" color="var(--prism-text-subtle)">
      <Text as="span" color="var(--prism-text-faint)">
        {label}
      </Text>{' '}
      {value == null ? '—' : `${value.toFixed(1)} ${unit}`}
    </Text>
  );
}

export function FFTPlot({ artifactId }: { artifactId: string }) {
  const q = useFFT(artifactId);
  const [showGen, setShowGen] = useState(false);
  const gen = useGenalyzer(artifactId, showGen);
  const { colorMode } = useColorMode();
  if (q.isLoading) return <PlotSkeleton height={320} label="Loading FFT…" />;
  if (q.isError || !q.data) return <Text color="red.400">Failed to load FFT</Text>;
  const { frequencies, magnitudes, sample_rate } = q.data;
  const dB = magnitudes.map((m) => 20 * Math.log10(Math.max(m, 1e-12)));

  const markers = showGen ? (gen.data?.markers ?? []) : [];
  const data: Array<Record<string, unknown>> = [
    {
      x: frequencies,
      y: dB,
      type: 'scatter',
      mode: 'lines',
      line: { color: traceColor(4), width: 1 },
      name: 'FFT',
    },
  ];
  if (markers.length > 0) {
    data.push({
      x: markers.map((m) => m.frequency),
      y: markers.map((m) => m.mag_dbfs),
      text: markers.map((m) => m.label),
      type: 'scatter',
      mode: 'markers+text',
      textposition: 'top center',
      textfont: { size: 10 },
      marker: { color: '#f59e0b', size: 8, symbol: 'diamond' },
      name: 'genalyzer',
      hovertemplate: '%{text}<br>%{x:.4s}Hz<br>%{y:.1f} dBFS<extra></extra>',
    });
  }

  return (
    <Box>
      <Flex justify="flex-end" mb={1}>
        <Button
          size="xs"
          variant={showGen ? 'solid' : 'outline'}
          colorPalette={showGen ? 'orange' : 'gray'}
          onClick={() => setShowGen((s) => !s)}
        >
          {showGen ? '✓ genalyzer markers' : 'genalyzer markers'}
        </Button>
      </Flex>
      <Plot
        data={data}
        layout={analyzerLayout(colorMode, {
          x: { title: 'Frequency', eng: true, suffix: 'Hz' },
          y: { title: 'Magnitude (dB)' },
          height: 320,
        })}
        config={{ displaylogo: false, responsive: true }}
        style={{ width: '100%' }}
      />
      {showGen && gen.isError && (
        <Text fontSize="xs" color="red.400" mt={1}>
          Failed to compute genalyzer analysis.
        </Text>
      )}
      {showGen && gen.data && (
        <Flex gap={3} wrap="wrap" mt={1}>
          <Metric label="SNR" value={gen.data.snr} unit="dB" />
          <Metric label="SFDR" value={gen.data.sfdr} unit="dB" />
          <Metric label="SINAD" value={gen.data.sinad} unit="dB" />
          <Metric label="THD" value={gen.data.thd} unit="dBc" />
          <Metric label="ENOB" value={gen.data.enob} unit="bits" />
        </Flex>
      )}
      <Text fontSize="xs" color="var(--prism-text-subtle)" mt={1}>
        Sample rate: {sample_rate} Hz
      </Text>
    </Box>
  );
}
