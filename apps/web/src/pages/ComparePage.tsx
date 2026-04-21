import { Badge, Box, Heading, Stack, Table, Tabs, Text } from '@chakra-ui/react';
import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';

import { useCompare } from '../api/queries';
import type { CaseDiff } from '../api/types';
import { AppShell } from '../components/AppShell';
import { OverlayFFTPlot } from '../components/OverlayFFTPlot';
import { OverlayWaveformPlot, type OverlayTrace } from '../components/OverlayWaveformPlot';

export function ComparePage() {
  const [params] = useSearchParams();
  const runIds = (params.get('runs') ?? '').split(',').filter(Boolean);
  const q = useCompare(runIds);
  const [selected, setSelected] = useState<CaseDiff | null>(null);

  const runById = q.data ? Object.fromEntries(q.data.runs.map((r) => [r.id, r])) : {};

  const overlayTraces: OverlayTrace[] = selected
    ? selected.waveform_artifact_ids
        .map((aid, i) => ({
          artifactId: aid ?? '',
          label: q.data?.runs[i]?.name ?? `run ${i + 1}`,
          present: aid !== null,
        }))
        .filter((t) => t.present)
        .map(({ artifactId, label }) => ({ artifactId, label }))
    : [];

  return (
    <AppShell>
      <Heading size="lg" mb={2}>
        Compare
      </Heading>
      <Text fontSize="sm" color="gray.300" mb={4}>
        {runIds.length} runs selected
      </Text>

      {runIds.length < 2 && (
        <Text>Select at least 2 runs from the dashboard, then use the Compare button.</Text>
      )}
      {q.isLoading && <Text>Loading…</Text>}
      {q.isError && <Text color="red.400">Failed to load comparison</Text>}
      {q.data && (
        <Stack gap={4}>
          <Box>
            <Text fontSize="sm" color="gray.400">
              Pass rate Δ:&nbsp;
              {q.data.pass_rate_delta === null
                ? 'n/a'
                : `${(q.data.pass_rate_delta * 100).toFixed(1)}%`}
            </Text>
          </Box>
          <Table.Root variant="outline" size="sm">
            <Table.Header>
              <Table.Row>
                <Table.ColumnHeader>Suite</Table.ColumnHeader>
                <Table.ColumnHeader>Case</Table.ColumnHeader>
                {q.data.runs.map((r) => (
                  <Table.ColumnHeader key={r.id}>{r.name}</Table.ColumnHeader>
                ))}
                <Table.ColumnHeader>Overlay</Table.ColumnHeader>
              </Table.Row>
            </Table.Header>
            <Table.Body>
              {q.data.cases.map((c) => {
                const isSelected = selected?.suite_name === c.suite_name && selected?.name === c.name;
                const hasAnyWaveform = c.waveform_artifact_ids.some((id) => id !== null);
                return (
                  <Table.Row
                    key={`${c.suite_name}/${c.name}`}
                    onClick={() => hasAnyWaveform && setSelected(isSelected ? null : c)}
                    cursor={hasAnyWaveform ? 'pointer' : 'default'}
                    bg={isSelected ? 'var(--prism-bg-sel)' : undefined}
                    _hover={
                      hasAnyWaveform
                        ? { bg: isSelected ? 'var(--prism-bg-sel)' : 'var(--prism-bg-hover)' }
                        : undefined
                    }
                  >
                    <Table.Cell>{c.suite_name}</Table.Cell>
                    <Table.Cell>{c.name}</Table.Cell>
                    {c.statuses.map((s, i) => (
                      <Table.Cell key={i}>
                        {s ? (
                          <Badge colorPalette={s === 'pass' ? 'green' : s === 'skip' ? 'gray' : 'red'}>{s}</Badge>
                        ) : (
                          <Text fontSize="xs" color="gray.300">absent</Text>
                        )}
                      </Table.Cell>
                    ))}
                    <Table.Cell>
                      {hasAnyWaveform ? (
                        <Text fontSize="xs" color={isSelected ? 'blue.300' : 'gray.300'}>
                          {isSelected ? '▾ shown below' : 'click to overlay'}
                        </Text>
                      ) : (
                        <Text fontSize="xs" color="gray.400">no waveform</Text>
                      )}
                    </Table.Cell>
                  </Table.Row>
                );
              })}
            </Table.Body>
          </Table.Root>

          {selected && overlayTraces.length > 0 && (
            <Box
              borderWidth={1}
              borderColor="var(--prism-border)"
              borderRadius="md"
              p={4}
              bg="var(--prism-bg-surface)"
            >
              <Heading size="sm" mb={3}>
                {selected.suite_name} · {selected.name}
              </Heading>
              <Text fontSize="xs" color="gray.300" mb={3}>
                Overlaying waveforms from {overlayTraces.length} of {runIds.length} runs
                {overlayTraces.length < runIds.length &&
                  ` (others have no waveform attached: ${selected.waveform_artifact_ids
                    .map((aid, i) => (aid ? null : runById[runIds[i]]?.name ?? runIds[i]))
                    .filter(Boolean)
                    .join(', ')})`}
              </Text>
              <Tabs.Root defaultValue="time">
                <Tabs.List>
                  <Tabs.Trigger value="time">Time domain</Tabs.Trigger>
                  <Tabs.Trigger value="fft">FFT</Tabs.Trigger>
                </Tabs.List>
                <Tabs.Content value="time">
                  <OverlayWaveformPlot traces={overlayTraces} />
                </Tabs.Content>
                <Tabs.Content value="fft">
                  <OverlayFFTPlot traces={overlayTraces} />
                </Tabs.Content>
              </Tabs.Root>
            </Box>
          )}
        </Stack>
      )}
    </AppShell>
  );
}
