import { Box, Button, Flex, Text } from '@chakra-ui/react';

import { useProject, useUpdateProject } from '../api/queries';
import { useAuth } from '../auth/useAuth';

/**
 * Admin-only per-project toggle for genalyzer auto-analysis. When enabled, ingest
 * records SNR/SFDR/SINAD/THD/ENOB as `genalyzer.*` measurements for each waveform
 * case (a run's `genalyzer` tag overrides this per run).
 */
export function GenalyzerSettingCard({ slug }: { slug: string }) {
  const { user } = useAuth();
  const project = useProject(slug);
  const update = useUpdateProject(slug);
  if (!user?.is_admin) return null;
  const on = project.data?.genalyzer_auto ?? false;
  return (
    <Box
      mb={4}
      borderWidth={1}
      borderColor="var(--prism-border)"
      borderRadius="md"
      p={3}
      bg="var(--prism-bg-surface)"
    >
      <Flex align="center" justify="space-between" gap={3} wrap="wrap">
        <Box>
          <Text fontWeight="600" fontSize="sm">
            Genalyzer auto-analysis
          </Text>
          <Text fontSize="xs" color="var(--prism-text-subtle)">
            Record SNR / SFDR / SINAD / THD / ENOB as <code>genalyzer.*</code> measurements for each
            waveform on ingest. A run&apos;s <code>genalyzer</code> tag overrides this per run.
          </Text>
        </Box>
        <Button
          size="sm"
          colorPalette={on ? 'red' : 'blue'}
          loading={update.isPending}
          onClick={() => update.mutate({ genalyzer_auto: !on })}
        >
          {on ? 'Disable' : 'Enable'}
        </Button>
      </Flex>
    </Box>
  );
}
