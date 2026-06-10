import { Box, Button, Heading, Stack, Text } from '@chakra-ui/react';

import { useMatrixPrefs, useUpsertMatrixPrefs } from '../api/queries';

export function MatrixSettingsCard() {
  const prefs = useMatrixPrefs();
  const upsert = useUpsertMatrixPrefs();
  const enabled = prefs.data?.enabled ?? false;

  const toggle = () =>
    upsert.mutate({ ...(prefs.data ?? { enabled: false }), enabled: !enabled });

  return (
    <Box mt={10} maxW="900px">
      <Heading size="lg" mb={2}>
        Matrix dashboard
      </Heading>
      <Text color="var(--prism-text-subtle)" mb={4} fontSize="sm">
        A glanceable coverage wall of board/platform status. Enabling it adds a{' '}
        <strong>Matrix</strong> entry to your navigation.
      </Text>
      <Stack direction="row" align="center" gap={3}>
        <Button
          colorPalette={enabled ? 'red' : 'blue'}
          onClick={toggle}
          loading={upsert.isPending}
        >
          {enabled ? 'Disable' : 'Enable'} matrix dashboard
        </Button>
        <Text fontSize="sm" color="var(--prism-text-muted)">
          Currently {enabled ? 'enabled' : 'disabled'}.
        </Text>
      </Stack>
    </Box>
  );
}
