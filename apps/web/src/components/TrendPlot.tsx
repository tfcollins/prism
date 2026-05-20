import { Box, Flex, Text } from '@chakra-ui/react';
import Plotly from 'plotly.js-basic-dist';
import { useState } from 'react';
import createPlotlyComponent from 'react-plotly.js/factory';

import { useMeasurementTrend } from '../api/queries';
import { useColorMode } from '../colorMode';
import { groupTrendByTag, tagKeysFor } from '../lib/trend';
import { plotLayoutColors, traceColor } from './plotLayout';
import { PlotSkeleton } from './PlotSkeleton';

const Plot = createPlotlyComponent(Plotly as object);

const PASS_COLOR = '#34d399';
const FAIL_COLOR = '#f87171';
const SPEC_COLOR = '#fbbf24';

export function TrendPlot({
  projectSlug,
  measurementName,
}: {
  projectSlug: string;
  measurementName: string;
}) {
  const q = useMeasurementTrend(projectSlug, measurementName);
  const { colorMode } = useColorMode();
  const [groupBy, setGroupBy] = useState<string | null>(null);

  if (q.isLoading) return <PlotSkeleton height={360} label="Loading trend…" />;
  if (q.isError || !q.data) return <Text color="red.400">Failed to load trend</Text>;
  if (q.data.points.length === 0) {
    return (
      <Text color="var(--prism-text-subtle)" fontSize="sm">
        No measurements named “{measurementName}” found in this project yet.
      </Text>
    );
  }

  const c = plotLayoutColors(colorMode);
  const pts = q.data.points;
  const unit = pts.find((p) => p.unit)?.unit ?? '';
  const tagKeys = tagKeysFor(pts);
  const activeGroup = groupBy && tagKeys.includes(groupBy) ? groupBy : null;

  const hoverFor = (p: (typeof pts)[number]) =>
    `${p.run_name}<br>${p.value}${unit ? ' ' + unit : ''}` +
    (p.margin !== null ? `<br>margin ${p.margin >= 0 ? '+' : ''}${p.margin.toFixed(2)}` : '') +
    (Object.keys(p.tags).length
      ? '<br>' +
        Object.entries(p.tags)
          .map(([k, v]) => `${k}=${v}`)
          .join(', ')
      : '');
  // out-of-spec points always read as an 'x' so the signal survives grouping
  // (where marker colour encodes the tag value, not pass/fail).
  const symbolFor = (p: (typeof pts)[number]) => (p.in_spec === false ? 'x' : 'circle');

  const data: Array<Record<string, unknown>> = activeGroup
    ? groupTrendByTag(pts, activeGroup).map((g, i) => ({
        x: g.points.map((p) => p.run_name),
        y: g.points.map((p) => p.value),
        text: g.points.map(hoverFor),
        hoverinfo: 'text',
        type: 'scatter',
        mode: 'lines+markers',
        name: `${activeGroup}=${g.value}`,
        line: { color: traceColor(i), width: 1 },
        marker: { color: traceColor(i), size: 8, symbol: g.points.map(symbolFor) },
      }))
    : [
        {
          x: pts.map((p) => p.run_name),
          y: pts.map((p) => p.value),
          text: pts.map(hoverFor),
          hoverinfo: 'text',
          type: 'scatter',
          mode: 'lines+markers',
          line: { color: c.font, width: 1 },
          marker: {
            color: pts.map((p) =>
              p.in_spec === false ? FAIL_COLOR : p.in_spec === true ? PASS_COLOR : c.font,
            ),
            size: 8,
          },
        },
      ];

  const specMax = pts.find((p) => p.spec_max !== null)?.spec_max ?? null;
  const specMin = pts.find((p) => p.spec_min !== null)?.spec_min ?? null;
  const shapes = [specMax, specMin]
    .filter((v): v is number => v !== null)
    .map((v) => ({
      type: 'line' as const,
      xref: 'paper' as const,
      x0: 0,
      x1: 1,
      y0: v,
      y1: v,
      line: { color: SPEC_COLOR, width: 1, dash: 'dash' as const },
    }));

  return (
    <Box>
      {tagKeys.length > 0 && (
        <Flex align="center" gap={2} mb={2} fontSize="sm">
          <Text color="var(--prism-text-subtle)">Group by tag:</Text>
          <Box
            as="button"
            onClick={() => setGroupBy(null)}
            px={2}
            py="2px"
            borderRadius="md"
            borderWidth={1}
            cursor="pointer"
            bg={activeGroup === null ? 'var(--prism-sidebar-active-bg)' : 'var(--prism-bg-surface)'}
            color={
              activeGroup === null ? 'var(--prism-sidebar-active-fg)' : 'var(--prism-text-muted)'
            }
            borderColor="var(--prism-border)"
          >
            none
          </Box>
          {tagKeys.map((k) => (
            <Box
              as="button"
              key={k}
              onClick={() => setGroupBy(k)}
              px={2}
              py="2px"
              borderRadius="md"
              borderWidth={1}
              cursor="pointer"
              bg={activeGroup === k ? 'var(--prism-sidebar-active-bg)' : 'var(--prism-bg-surface)'}
              color={
                activeGroup === k ? 'var(--prism-sidebar-active-fg)' : 'var(--prism-text-muted)'
              }
              borderColor="var(--prism-border)"
            >
              {k}
            </Box>
          ))}
        </Flex>
      )}
      <Plot
        data={data}
        layout={{
          paper_bgcolor: c.paper,
          plot_bgcolor: c.plot,
          font: { color: c.font },
          margin: { l: 60, r: 20, t: 20, b: 80 },
          xaxis: { title: { text: 'Run' }, gridcolor: c.grid, tickangle: -40, automargin: true },
          yaxis: { title: { text: unit ? `Value (${unit})` : 'Value' }, gridcolor: c.grid },
          shapes,
          height: 360,
          autosize: true,
          showlegend: activeGroup !== null,
          legend: { orientation: 'h', y: -0.3 },
        }}
        config={{ displaylogo: false, responsive: true }}
        style={{ width: '100%' }}
      />
    </Box>
  );
}
