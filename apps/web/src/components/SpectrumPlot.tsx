import { Box, Flex, Text } from '@chakra-ui/react';
import Plotly from 'plotly.js-basic-dist';
import { useState } from 'react';
import createPlotlyComponent from 'react-plotly.js/factory';

import { useSpectrum } from '../api/queries';
import type { MaskSegment } from '../api/types';
import { useColorMode } from '../colorMode';
import { findMaskViolations, maskStepLine } from '../lib/mask';
import { formatEng } from '../lib/measurement';
import { analyzerLayout, plotLayoutColors, traceColor } from './plotLayout';
import { PlotSkeleton } from './PlotSkeleton';

interface DeltaMarker {
  frequency: number;
  power: number;
}

const Plot = createPlotlyComponent(Plotly as object);
const MASK_COLOR = '#f87171';

function metaChips(metadata: Record<string, string | number>): string[] {
  const order = ['center', 'span', 'rbw', 'vbw', 'ref_level', 'detector'];
  const chips: string[] = [];
  for (const k of order) {
    if (metadata[k] === undefined) continue;
    chips.push(`${k}=${metadata[k]}`);
  }
  return chips;
}

export interface SpectrumBand {
  lo: number;
  hi: number;
  color: string;
  label?: string;
}

export interface SpectrumMarker {
  frequency: number;
  power: number;
}

export function SpectrumPlot({
  artifactId,
  bands = [],
  markers = [],
  maskSegments,
}: {
  artifactId: string;
  bands?: SpectrumBand[];
  markers?: SpectrumMarker[];
  maskSegments?: MaskSegment[];
}) {
  const q = useSpectrum(artifactId);
  const { colorMode } = useColorMode();
  const [placed, setPlaced] = useState<DeltaMarker[]>([]);
  const [refIdx, setRefIdx] = useState<number | null>(null);

  if (q.isLoading) return <PlotSkeleton label="Loading spectrum…" />;
  if (q.isError || !q.data) return <Text color="red.400">Failed to load spectrum</Text>;

  const { frequencies, powers, unit, metadata } = q.data;
  const yLabel = unit ? `Power (${unit})` : 'Power';

  const violations = maskSegments ? findMaskViolations(frequencies, powers, maskSegments) : [];

  const layout = analyzerLayout(colorMode, {
    x: { title: 'Frequency', eng: true, suffix: 'Hz' },
    y: { title: yLabel },
  });
  const shapes = bands.map((b) => ({
    type: 'rect' as const,
    xref: 'x' as const,
    yref: 'paper' as const,
    x0: b.lo,
    x1: b.hi,
    y0: 0,
    y1: 1,
    fillcolor: b.color,
    opacity: 0.18,
    line: { width: 0 },
    layer: 'below' as const,
  }));

  const data: Array<Record<string, unknown>> = [
    {
      x: frequencies,
      y: powers,
      type: 'scatter',
      mode: 'lines',
      line: { color: traceColor(0), width: 1 },
      name: 'spectrum',
    },
  ];
  if (markers.length > 0) {
    data.push({
      x: markers.map((m) => m.frequency),
      y: markers.map((m) => m.power),
      type: 'scatter',
      mode: 'markers',
      marker: { color: '#f87171', size: 9, symbol: 'triangle-down' },
      name: 'spurs',
      hovertemplate: '%{x:.4s}Hz<br>%{y:.1f}<extra>spur</extra>',
    });
  }
  if (placed.length > 0) {
    data.push({
      x: placed.map((m) => m.frequency),
      y: placed.map((m) => m.power),
      text: placed.map((_, i) => (i === refIdx ? 'R' : `M${i + 1}`)),
      type: 'scatter',
      mode: 'markers+text',
      textposition: 'top center',
      // The plot area is dark in both themes, so label text uses the on-plot
      // color (plotFont) — a dark color in light mode would be invisible here.
      textfont: { color: plotLayoutColors(colorMode).plotFont, size: 10 },
      marker: { color: '#22d3ee', size: 9, symbol: 'diamond' },
      name: 'markers',
      hoverinfo: 'skip',
    });
  }
  if (maskSegments && maskSegments.length > 0) {
    const line = maskStepLine(maskSegments);
    data.push({
      x: line.x,
      y: line.y,
      type: 'scatter',
      mode: 'lines',
      line: { color: MASK_COLOR, width: 1.5, dash: 'dash' },
      name: 'mask',
    });
    if (violations.length > 0) {
      data.push({
        x: violations.map((v) => v.frequency),
        y: violations.map((v) => v.power),
        type: 'scatter',
        mode: 'markers',
        marker: { color: MASK_COLOR, size: 7, symbol: 'x' },
        name: 'violations',
        hovertemplate: '%{x:.4s}Hz<br>%{y:.1f}<extra>mask violation</extra>',
      });
    }
  }

  const ref = refIdx !== null ? placed[refIdx] : null;

  return (
    <Box position="relative">
      <Plot
        data={data}
        layout={{ ...layout, shapes, showlegend: false }}
        config={{ displaylogo: false, responsive: true }}
        style={{ width: '100%' }}
        onClick={(e) => {
          const pt = e.points?.[0];
          if (!pt) return;
          const fp = { frequency: Number(pt.x), power: Number(pt.y) };
          if (!Number.isFinite(fp.frequency) || !Number.isFinite(fp.power)) return;
          if ((e.event as MouseEvent | undefined)?.shiftKey) {
            setPlaced((prev) => {
              const next = [...prev, fp];
              setRefIdx(next.length - 1);
              return next;
            });
          } else {
            setPlaced((prev) => [...prev, fp]);
          }
        }}
      />
      {placed.length > 0 && (
        <Box
          position="absolute"
          top={2}
          right={2}
          bg="var(--prism-bg-surface)"
          borderWidth={1}
          borderColor="var(--prism-border)"
          borderRadius="md"
          px={2}
          py={1}
          fontSize="xs"
          fontFamily="mono"
          maxW="240px"
        >
          <Flex justify="space-between" align="center" mb={1} gap={3}>
            <Text color="var(--prism-text-faint)">markers (shift-click = ref)</Text>
            <Box
              as="button"
              onClick={() => {
                setPlaced([]);
                setRefIdx(null);
              }}
              color="var(--prism-link)"
              cursor="pointer"
            >
              clear
            </Box>
          </Flex>
          {placed.map((m, i) => {
            const dF = ref && i !== refIdx ? m.frequency - ref.frequency : null;
            const dP = ref && i !== refIdx ? m.power - ref.power : null;
            return (
              <Text key={`${m.frequency}:${m.power}:${i}`} color="var(--prism-text-muted)">
                {i === refIdx ? 'R' : `M${i + 1}`}: {formatEng(m.frequency, 'Hz')} ·{' '}
                {formatEng(m.power, unit)}
                {dF !== null && dP !== null && (
                  <Text as="span" color="var(--prism-text-faint)">
                    {' '}
                    (Δ {formatEng(dF, 'Hz')}, {dP >= 0 ? '+' : ''}
                    {dP.toFixed(2)})
                  </Text>
                )}
              </Text>
            );
          })}
        </Box>
      )}
      {metaChips(metadata).length > 0 && (
        <Flex wrap="wrap" gap={2} mt={1}>
          {metaChips(metadata).map((chip) => (
            <Text
              key={chip}
              fontSize="xs"
              fontFamily="mono"
              color="var(--prism-text-faint)"
              px={2}
              py="1px"
              borderRadius="sm"
              bg="var(--prism-bg-hover)"
            >
              {chip}
            </Text>
          ))}
        </Flex>
      )}
    </Box>
  );
}
