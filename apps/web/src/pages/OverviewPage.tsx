import { Box, Flex, Grid, Heading, Stack, Table, Text } from '@chakra-ui/react';
import Plotly from 'plotly.js-basic-dist';
import createPlotlyComponent from 'react-plotly.js/factory';
import { Link } from 'react-router-dom';

import { useOverview } from '../api/queries';
import type { DailyPoint, RecentRun } from '../api/types';
import { useColorMode } from '../colorMode';
import { AppShell } from '../components/AppShell';
import { PLOT_CONFIG, PLOT_FONT_FAMILY, plotLayoutColors } from '../components/plotLayout';
import { Sparkline } from '../components/Sparkline';

const Plot = createPlotlyComponent(Plotly as object);

const STATUS_COLOR: Record<string, string> = {
  pass: 'var(--prism-spectrum-g)',
  fail: 'var(--prism-spectrum-r)',
  mixed: 'var(--prism-spectrum-o)',
  error: 'var(--prism-spectrum-r)',
  pending: 'var(--prism-text-faint)',
};

// `fg` uses mode-aware, contrast-tuned tokens (the big numerals must pass WCAG
// on both canvases); `spark` keeps the bright spectral hue since the sparkline
// is aria-hidden decoration, not text.
const HUES = {
  brand: { fg: 'var(--prism-brand)', spark: '#22d3ee' },
  pass: { fg: 'var(--prism-status-pass-fg)', spark: '#34d399' },
  fail: { fg: 'var(--prism-status-fail-fg)', spark: '#f87171' },
  neutral: { fg: 'var(--prism-text)', spark: '#94a3b8' },
} as const;

/** Sum of the last `n` points minus the `n` before them — a simple 7d trend. */
function windowDelta(values: number[], n = 7): number {
  if (values.length < 2) return 0;
  const last = values.slice(-n).reduce((a, b) => a + b, 0);
  const prev = values.slice(-n * 2, -n).reduce((a, b) => a + b, 0);
  return last - prev;
}

function StatCard({
  label,
  value,
  hue = 'neutral',
  spark,
  delta,
  deltaGoodWhenDown = false,
  meter,
}: {
  label: string;
  value: string | number;
  hue?: keyof typeof HUES;
  spark?: number[];
  delta?: number;
  deltaGoodWhenDown?: boolean;
  meter?: number;
}) {
  const h = HUES[hue];
  const glow = hue === 'neutral' ? 'none' : `0 0 24px -10px ${h.spark}`;
  const showDelta = delta !== undefined && delta !== 0;
  const up = (delta ?? 0) > 0;
  const good = deltaGoodWhenDown ? !up : up;

  return (
    <Box
      position="relative"
      overflow="hidden"
      borderWidth={1}
      borderColor="var(--prism-border)"
      borderRadius="lg"
      p={4}
      bg="var(--prism-bg-surface)"
      boxShadow="var(--prism-shadow-card)"
    >
      <Text
        fontSize="10px"
        textTransform="uppercase"
        letterSpacing="0.12em"
        fontFamily="var(--prism-font-mono)"
        color="var(--prism-text-faint)"
        mb={2}
      >
        {label}
      </Text>
      <Flex align="baseline" justify="space-between" gap={2}>
        <Text
          className="prism-num"
          fontSize="32px"
          fontWeight={600}
          lineHeight={1}
          color={h.fg}
          style={{ textShadow: glow }}
        >
          {value}
        </Text>
        {showDelta && (
          <Text
            className="prism-num"
            fontSize="11px"
            whiteSpace="nowrap"
            color={good ? 'var(--prism-status-pass-fg)' : 'var(--prism-status-fail-fg)'}
          >
            {up ? '▲' : '▼'} {Math.abs(delta as number)} · 7d
          </Text>
        )}
      </Flex>
      {meter !== undefined && (
        <Box mt={3} h="4px" borderRadius="full" bg="var(--prism-bg-hover)" overflow="hidden">
          <Box h="100%" w={`${Math.round(meter * 100)}%`} bg={h.fg} borderRadius="full" />
        </Box>
      )}
      {spark && spark.length > 1 && (
        <Box mt={3} mx={-1}>
          <Sparkline values={spark} color={h.spark} width={220} height={34} />
        </Box>
      )}
    </Box>
  );
}

function DailyChart({ daily }: { daily: DailyPoint[] }) {
  const { colorMode } = useColorMode();
  const c = plotLayoutColors(colorMode);
  const x = daily.map((d) => d.date);
  return (
    <Plot
      data={[
        {
          type: 'bar',
          name: 'Runs',
          x,
          y: daily.map((d) => d.runs),
          marker: { color: '#22d3ee' },
        },
        {
          type: 'scatter',
          mode: 'lines',
          name: 'Test failures',
          x,
          y: daily.map((d) => d.failures),
          line: { color: '#f87171', width: 2, shape: 'spline', smoothing: 0.6 },
          fill: 'tozeroy',
          fillcolor: 'rgba(248,113,113,0.12)',
        },
      ]}
      layout={{
        paper_bgcolor: c.paper,
        plot_bgcolor: c.plot,
        font: { color: c.font, family: PLOT_FONT_FAMILY, size: 11 },
        margin: { l: 48, r: 20, t: 10, b: 40 },
        xaxis: { gridcolor: c.grid, type: 'date', zeroline: false },
        yaxis: {
          title: { text: 'Count' },
          gridcolor: c.grid,
          rangemode: 'tozero',
          zeroline: false,
        },
        legend: { orientation: 'h', y: 1.16, font: { size: 11 } },
        height: 300,
        autosize: true,
        bargap: 0.45,
      }}
      config={PLOT_CONFIG}
      style={{ width: '100%' }}
    />
  );
}

function RecentRunsTable({ runs }: { runs: RecentRun[] }) {
  if (runs.length === 0) return <Text color="var(--prism-text-subtle)">No runs yet.</Text>;
  return (
    <Box overflowX="auto">
      <Table.Root variant="outline" size="sm">
        <Table.Header>
          <Table.Row>
            <Table.ColumnHeader>Status</Table.ColumnHeader>
            <Table.ColumnHeader>Project</Table.ColumnHeader>
            <Table.ColumnHeader>Run</Table.ColumnHeader>
            <Table.ColumnHeader>Pass</Table.ColumnHeader>
            <Table.ColumnHeader>Fail</Table.ColumnHeader>
            <Table.ColumnHeader>When</Table.ColumnHeader>
          </Table.Row>
        </Table.Header>
        <Table.Body>
          {runs.map((r) => (
            <Table.Row key={r.id}>
              <Table.Cell>
                <Flex
                  as="span"
                  display="inline-flex"
                  align="center"
                  gap={2}
                  px={2}
                  py="2px"
                  borderRadius="full"
                  borderWidth={1}
                  borderColor="var(--prism-border)"
                  fontSize="11px"
                  fontFamily="var(--prism-font-mono)"
                >
                  <Box
                    w="7px"
                    h="7px"
                    borderRadius="50%"
                    bg={STATUS_COLOR[r.status] ?? 'var(--prism-text-faint)'}
                    boxShadow={`0 0 8px -1px ${STATUS_COLOR[r.status] ?? 'transparent'}`}
                  />
                  {r.status}
                </Flex>
              </Table.Cell>
              <Table.Cell>
                <Link to={`/projects/${r.project_slug}`} style={{ color: 'var(--prism-brand)' }}>
                  {r.project_name}
                </Link>
              </Table.Cell>
              <Table.Cell>
                <Link to={`/runs/${r.id}`} style={{ color: 'var(--prism-brand)' }}>
                  {r.name}
                </Link>
              </Table.Cell>
              <Table.Cell className="prism-num">{r.pass_count}</Table.Cell>
              <Table.Cell
                className="prism-num"
                color={r.fail_count > 0 ? 'var(--prism-status-fail-fg)' : undefined}
              >
                {r.fail_count}
              </Table.Cell>
              <Table.Cell>
                <Text as="span" fontSize="xs" color="var(--prism-text-subtle)" whiteSpace="nowrap">
                  {new Date(r.created_at).toLocaleString()}
                </Text>
              </Table.Cell>
            </Table.Row>
          ))}
        </Table.Body>
      </Table.Root>
    </Box>
  );
}

export function OverviewPage() {
  const q = useOverview();

  return (
    <AppShell>
      <Box p={8}>
        <Heading size="xl" mb={6}>
          Overview
        </Heading>

        {q.isLoading && <Text>Loading…</Text>}
        {q.isError && <Text color="red.400">Failed to load overview.</Text>}
        {q.data && (
          <Stack gap={8}>
            <Grid templateColumns={{ base: '1fr 1fr', md: 'repeat(5, 1fr)' }} gap={4}>
              <StatCard label="Projects" value={q.data.stats.total_projects} hue="neutral" />
              <StatCard
                label="Runs"
                value={q.data.stats.total_runs}
                hue="brand"
                spark={q.data.daily.map((d) => d.runs)}
                delta={windowDelta(q.data.daily.map((d) => d.runs))}
              />
              <StatCard label="Tests" value={q.data.stats.total_tests} hue="neutral" />
              <StatCard
                label="Failures"
                value={q.data.stats.total_failures}
                hue="fail"
                spark={q.data.daily.map((d) => d.failures)}
                delta={windowDelta(q.data.daily.map((d) => d.failures))}
                deltaGoodWhenDown
              />
              <StatCard
                label="Pass rate"
                value={`${(q.data.stats.pass_rate * 100).toFixed(1)}%`}
                hue="pass"
                meter={q.data.stats.pass_rate}
              />
            </Grid>

            <Box>
              <Heading size="md" mb={3}>
                Last 30 days
              </Heading>
              <Box
                borderWidth={1}
                borderColor="var(--prism-border)"
                borderRadius="lg"
                p={2}
                bg="var(--prism-bg-surface)"
                boxShadow="var(--prism-shadow-card)"
              >
                <DailyChart daily={q.data.daily} />
              </Box>
            </Box>

            <Box>
              <Heading size="md" mb={3}>
                Recent runs
              </Heading>
              <RecentRunsTable runs={q.data.recent_runs} />
            </Box>
          </Stack>
        )}
      </Box>
    </AppShell>
  );
}
