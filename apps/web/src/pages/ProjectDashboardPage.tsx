import { Box, Heading, Text } from '@chakra-ui/react';
import { useParams } from 'react-router-dom';

import { useRuns } from '../api/queries';
import { AppShell } from '../components/AppShell';
import { RunsTable } from '../components/RunsTable';

export function ProjectDashboardPage() {
  const { slug } = useParams<{ slug: string }>();
  const runsQuery = useRuns(slug);

  return (
    <AppShell>
      <Heading size="lg" mb={4}>
        {slug}
      </Heading>
      {runsQuery.isLoading && <Text>Loading…</Text>}
      {runsQuery.isError && (
        <Text color="red.400">Could not load runs — {String(runsQuery.error)}</Text>
      )}
      {runsQuery.data && (
        <Box>
          <RunsTable runs={runsQuery.data} />
        </Box>
      )}
    </AppShell>
  );
}
