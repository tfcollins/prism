import { Badge, Box, Heading, Stack, Table, Text } from '@chakra-ui/react';
import { useSearchParams } from 'react-router-dom';

import { useCompare } from '../api/queries';
import { AppShell } from '../components/AppShell';

export function ComparePage() {
  const [params] = useSearchParams();
  const runIds = (params.get('runs') ?? '').split(',').filter(Boolean);
  const q = useCompare(runIds);

  return (
    <AppShell>
      <Heading size="lg" mb={2}>Compare</Heading>
      <Text fontSize="sm" color="gray.500" mb={4}>{runIds.length} runs selected</Text>

      {runIds.length < 2 && (
        <Text>Select at least 2 runs from the dashboard, then use the Compare button.</Text>
      )}
      {q.isLoading && <Text>Loading…</Text>}
      {q.isError && <Text color="red.400">Failed to load comparison</Text>}
      {q.data && (
        <Stack gap={4}>
          <Box>
            <Text fontSize="sm" color="gray.400">Pass rate Δ:&nbsp;
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
              </Table.Row>
            </Table.Header>
            <Table.Body>
              {q.data.cases.map((c) => (
                <Table.Row key={`${c.suite_name}/${c.name}`}>
                  <Table.Cell>{c.suite_name}</Table.Cell>
                  <Table.Cell>{c.name}</Table.Cell>
                  {c.statuses.map((s, i) => (
                    <Table.Cell key={i}>
                      {s ? (
                        <Badge colorPalette={s === 'pass' ? 'green' : s === 'skip' ? 'gray' : 'red'}>{s}</Badge>
                      ) : (
                        <Text fontSize="xs" color="gray.500">absent</Text>
                      )}
                    </Table.Cell>
                  ))}
                </Table.Row>
              ))}
            </Table.Body>
          </Table.Root>
        </Stack>
      )}
    </AppShell>
  );
}
