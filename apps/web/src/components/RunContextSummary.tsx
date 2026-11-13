import { Box, Flex, Grid, Heading, Stack, Text } from '@chakra-ui/react';

import type { CIContext, HardwareContext } from '../api/types';

function ContextFields({ values }: { values: Record<string, unknown> }) {
  return (
    <Box as="dl" fontSize="xs">
      {Object.entries(values)
        .filter(([, value]) => value != null && value !== '')
        .map(([label, value]) => (
          <Flex key={label} gap={2} align="baseline" wrap="wrap">
            <Text as="dt" color="var(--prism-text-subtle)">
              {label}
            </Text>
            <Text as="dd" overflowWrap="anywhere" fontFamily="mono">
              {typeof value === 'object' ? JSON.stringify(value) : String(value)}
            </Text>
          </Flex>
        ))}
    </Box>
  );
}

function CollectionErrors({ errors }: { errors: (string | undefined)[] }) {
  return (
    <>
      {errors.filter(Boolean).map((error, index) => (
        <Text key={index} fontSize="xs" color="var(--prism-status-fail-fg)" overflowWrap="anywhere">
          {error}
        </Text>
      ))}
    </>
  );
}

export function RunContextSummary({
  ci,
  hardware,
  inherited = false,
}: {
  ci?: CIContext | null;
  hardware?: HardwareContext | null;
  inherited?: boolean;
}) {
  const runUrl = ci?.run_url && /^https?:\/\//i.test(ci.run_url) ? ci.run_url : undefined;
  const jobUrl = ci?.job_url && /^https?:\/\//i.test(ci.job_url) ? ci.job_url : undefined;
  const hardwareErrors = [
    ...(hardware?.collection_errors ?? []),
    hardware?.metadata_error,
    hardware?.dmesg_pre_error,
    hardware?.dmesg_post_error,
    ...Object.entries(hardware?.dmesg ?? {})
      .filter(([key]) => key.endsWith('error'))
      .map(([, value]) => (typeof value === 'string' ? value : undefined)),
  ];
  return (
    <Box
      borderWidth={1}
      borderColor="var(--prism-border)"
      borderRadius="md"
      p={3}
      mb={3}
      bg="var(--prism-bg-surface)"
    >
      {inherited && (
        <Text fontSize="xs" color="var(--prism-text-subtle)" mb={2}>
          Inherited from run
        </Text>
      )}
      <Grid templateColumns={{ base: '1fr', md: '1fr 1fr' }} gap={4}>
        <Stack gap={1}>
          <Heading size="xs">CI</Heading>
          {ci ? (
            <>
              <ContextFields
                values={{
                  Provider: ci.provider,
                  Repository: ci.repository,
                  Workflow: ci.workflow,
                  Run: ci.run_id,
                  Attempt: ci.attempt,
                  Job: ci.job_name,
                  Matrix: ci.matrix,
                }}
              />
              <Flex gap={3} fontSize="xs" wrap="wrap">
                {runUrl && (
                  <a
                    href={runUrl}
                    target="_blank"
                    rel="noreferrer"
                    style={{ color: 'var(--prism-link)' }}
                  >
                    Open CI run
                  </a>
                )}
                {jobUrl && (
                  <a
                    href={jobUrl}
                    target="_blank"
                    rel="noreferrer"
                    style={{ color: 'var(--prism-link)' }}
                  >
                    Open CI job
                  </a>
                )}
                {!runUrl && !jobUrl && (
                  <Text color="var(--prism-text-faint)">CI link unavailable.</Text>
                )}
              </Flex>
              <CollectionErrors errors={ci.collection_errors ?? []} />
            </>
          ) : (
            <Text fontSize="xs" color="var(--prism-text-faint)">
              CI context unavailable.
            </Text>
          )}
        </Stack>
        <Stack gap={1}>
          <Heading size="xs">Hardware</Heading>
          {hardware ? (
            <>
              <ContextFields
                values={{
                  Place: hardware.place,
                  Board: hardware.board,
                  Carrier: hardware.carrier,
                  Exporters: hardware.exporters?.join(', '),
                  Status: hardware.metadata_status,
                  Tags: hardware.tags,
                }}
              />
              <CollectionErrors errors={hardwareErrors} />
            </>
          ) : (
            <Text fontSize="xs" color="var(--prism-text-faint)">
              Hardware context unavailable.
            </Text>
          )}
        </Stack>
      </Grid>
    </Box>
  );
}
