import { Box, Button, Flex, Heading, Text } from '@chakra-ui/react';
import { useState } from 'react';
import { useParams } from 'react-router-dom';

import { useMatrix, useMatrixConfig } from '../api/queries';
import { AppShell } from '../components/AppShell';
import { MatrixGrid } from '../components/MatrixGrid';

export function MatrixDashboardPage() {
  const { slug } = useParams();
  const scope = slug ? `project:${slug}` : 'global';
  const config = useMatrixConfig(scope);
  const refreshMs = (config.data?.config.refresh_seconds ?? 30) * 1000;

  const [bootFiles, setBootFiles] = useState<string[]>([]);
  const q = useMatrix(scope, bootFiles, refreshMs);

  const toggleBoot = (bf: string) =>
    setBootFiles((cur) => (cur.includes(bf) ? cur.filter((x) => x !== bf) : [...cur, bf]));

  return (
    <AppShell>
      <Box p={8}>
        <Flex justify="space-between" align="center" mb={2}>
          <Heading size="xl">Matrix — {scope === 'global' ? 'All releases' : slug}</Heading>
          {q.isFetching && <Text fontSize="sm" color="var(--prism-text-muted)">refreshing…</Text>}
        </Flex>
        {q.isError && !q.data && (
          <Text color="red.400">Failed to load matrix.</Text>
        )}
        {q.data && (
          <>
            {q.data.boot_files.length > 0 && (
              <Flex gap={2} mb={4} wrap="wrap" align="center">
                <Text fontSize="sm" color="var(--prism-text-muted)">boot file:</Text>
                {q.data.boot_files.map((bf) => (
                  <Button
                    key={bf}
                    size="xs"
                    variant={bootFiles.includes(bf) ? 'solid' : 'outline'}
                    colorPalette="blue"
                    onClick={() => toggleBoot(bf)}
                  >
                    {bf}
                  </Button>
                ))}
                {bootFiles.length > 0 && (
                  <Button size="xs" variant="ghost" onClick={() => setBootFiles([])}>
                    clear
                  </Button>
                )}
              </Flex>
            )}
            {q.data.unplaced_runs > 0 && (
              <Text fontSize="xs" color="var(--prism-text-faint)" mb={2}>
                {q.data.unplaced_runs} run(s) missing hw/platform tags are not shown.
              </Text>
            )}
            <MatrixGrid data={q.data} />
          </>
        )}
      </Box>
    </AppShell>
  );
}
