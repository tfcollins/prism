import { Badge, Box, Flex, Grid, Heading, Stack, Tabs, Text } from '@chakra-ui/react';
import { useState } from 'react';
import { useParams } from 'react-router-dom';

import { useCase, useRun } from '../api/queries';
import { AppShell } from '../components/AppShell';
import { FFTPlot } from '../components/FFTPlot';
import { TestTree } from '../components/TestTree';
import { WaveformPlot } from '../components/WaveformPlot';

export function RunDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null);

  const runQuery = useRun(id);
  const caseQuery = useCase(selectedCaseId ?? undefined);

  const waveform = caseQuery.data?.artifacts.find((a) => a.kind.startsWith('waveform'));

  return (
    <AppShell>
      {runQuery.isLoading && <Text>Loading run…</Text>}
      {runQuery.isError && <Text color="red.400">Failed to load run</Text>}
      {runQuery.data && (
        <Box>
          <Heading size="lg" mb={2}>
            {runQuery.data.name}
          </Heading>
          <Stack direction="row" gap={2} mb={6}>
            <Badge colorPalette="blue">{runQuery.data.status}</Badge>
            {runQuery.data.tags.map((t) => (
              <Badge key={`${t.key}:${t.value}`} variant="outline">
                {t.key}={t.value}
              </Badge>
            ))}
          </Stack>
          <Grid templateColumns="240px 1fr" gap={4} minH="500px">
            <Box
              borderWidth={1}
              borderColor="var(--prism-border)"
              borderRadius="md"
              p={3}
              bg="var(--prism-bg-surface)"
              overflowY="auto"
            >
              {runQuery.data.suites.length === 1 && (
                <Flex align="center" gap={2} mb={2} pb={2} borderBottomWidth={1} borderColor="var(--prism-border)">
                  <Text
                    fontSize="10px"
                    textTransform="uppercase"
                    letterSpacing="1px"
                    color="var(--prism-text-faint)"
                  >
                    Suite
                  </Text>
                  <Badge variant="subtle" colorPalette="blue">
                    {runQuery.data.suites[0].name}
                  </Badge>
                </Flex>
              )}
              <TestTree
                suites={runQuery.data.suites}
                selectedCaseId={selectedCaseId}
                onSelectCase={setSelectedCaseId}
                flatten={runQuery.data.suites.length === 1}
              />
            </Box>
            <Box borderWidth={1} borderColor="var(--prism-border)" borderRadius="md" p={3} bg="var(--prism-bg-surface)">
              {!selectedCaseId && <Text color="var(--prism-text-subtle)">Select a case from the tree</Text>}
              {selectedCaseId && caseQuery.isLoading && <Text>Loading case…</Text>}
              {caseQuery.data && (
                <Stack gap={3}>
                  <Box>
                    <Heading size="sm">{caseQuery.data.name}</Heading>
                    <Text fontSize="xs" color="var(--prism-text-subtle)">
                      {caseQuery.data.classname} · {caseQuery.data.status} · {caseQuery.data.duration_ms} ms
                    </Text>
                  </Box>
                  {caseQuery.data.failure_message && (
                    <Box
                      bg="var(--prism-danger-bg)"
                      p={2}
                      borderRadius="md"
                      color="var(--prism-danger-fg)"
                      fontSize="sm"
                    >
                      {caseQuery.data.failure_message}
                    </Box>
                  )}
                  {waveform ? (
                    <Tabs.Root defaultValue="time">
                      <Tabs.List>
                        <Tabs.Trigger value="time">Time domain</Tabs.Trigger>
                        <Tabs.Trigger value="fft">FFT</Tabs.Trigger>
                      </Tabs.List>
                      <Tabs.Content value="time">
                        <WaveformPlot artifactId={waveform.id} />
                      </Tabs.Content>
                      <Tabs.Content value="fft">
                        <FFTPlot artifactId={waveform.id} />
                      </Tabs.Content>
                    </Tabs.Root>
                  ) : (
                    <Text color="var(--prism-text-subtle)" fontSize="sm">
                      No waveform artifact attached to this case.
                    </Text>
                  )}
                </Stack>
              )}
            </Box>
          </Grid>
        </Box>
      )}
    </AppShell>
  );
}
