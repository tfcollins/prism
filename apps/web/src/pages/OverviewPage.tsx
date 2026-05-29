import { Box, Grid, Heading, Stack, Table, Text } from '@chakra-ui/react';
import Plotly from 'plotly.js-basic-dist';
import createPlotlyComponent from 'react-plotly.js/factory';
import { Link } from 'react-router-dom';

import { useOverview } from '../api/queries';
import type { DailyPoint, RecentRun } from '../api/types';
import { useColorMode } from '../colorMode';
import { AppShell } from '../components/AppShell';
import { plotLayoutColors } from '../components/plotLayout';

const Plot = createPlotlyComponent(Plotly as object);

const STATUS_COLOR: Record<string, string> = {
  pass: '#48bb78',
  fail: '#f56565',
  mixed: '#ed8936',
  error: '#f56565',
  pending: '#a0aec0',
};

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <Box
      borderWidth={1}
      borderColor="var(--prism-border)"
      borderRadius="md"
      p={4}
      bg="var(--prism-bg-surface)"
    >
      <Text fontSize="xs" textTransform="uppercase" letterSpacing="1px" color="var(--prism-text-faint)" mb={1}>
        {label}
      </Text>
      <Text fontSize="2xl" fontWeight="bold" color="var(--prism-text)">
        {value}
      </Text>
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
          marker: { color: '#56b4e9' },
        },
        {
          type: 'scatter',
          mode: 'lines+markers',
          name: 'Test failures',
          x,
          y: daily.map((d) => d.failures),
          line: { color: '#f87171', width: 2 },
          marker: { color: '#f87171', size: 5 },
        },
      ]}
      layout={{
        paper_bgcolor: c.paper,
        plot_bgcolor: c.plot,
        font: { color: c.font },
        margin: { l: 48, r: 20, t: 10, b: 48 },
        xaxis: { gridcolor: c.grid, type: 'date' },
        yaxis: { title: { text: 'Count' }, gridcolor: c.grid, rangemode: 'tozero' },
        legend: { orientation: 'h', y: 1.12 },
        height: 300,
        autosize: true,
        bargap: 0.3,
      }}
      config={{ displaylogo: false, responsive: true }}
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
                <Box
                  display="inline-block"
                  w="8px"
                  h="8px"
                  borderRadius="50%"
                  bg={STATUS_COLOR[r.status] ?? '#a0aec0'}
                  mr={2}
                />
                {r.status}
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
              <Table.Cell>{r.pass_count}</Table.Cell>
              <Table.Cell>{r.fail_count}</Table.Cell>
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
            <Grid
              templateColumns={{ base: '1fr 1fr', md: 'repeat(5, 1fr)' }}
              gap={4}
            >
              <StatCard label="Projects" value={q.data.stats.total_projects} />
              <StatCard label="Runs" value={q.data.stats.total_runs} />
              <StatCard label="Tests" value={q.data.stats.total_tests} />
              <StatCard label="Failures" value={q.data.stats.total_failures} />
              <StatCard
                label="Pass rate"
                value={`${(q.data.stats.pass_rate * 100).toFixed(1)}%`}
              />
            </Grid>

            <Box>
              <Heading size="md" mb={3}>
                Last 30 days
              </Heading>
              <Box
                borderWidth={1}
                borderColor="var(--prism-border)"
                borderRadius="md"
                p={2}
                bg="var(--prism-bg-surface)"
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
