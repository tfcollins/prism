import { Box, Flex, Grid, Heading, Stack, Text } from '@chakra-ui/react';
import { isValidElement } from 'react';

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
              {isValidElement(value)
                ? value
                : typeof value === 'object'
                  ? JSON.stringify(value)
                  : String(value)}
            </Text>
          </Flex>
        ))}
    </Box>
  );
}

function safeUrl(url?: string): string | undefined {
  return url && /^https?:\/\//i.test(url) ? url : undefined;
}

function Commit({ sha, url }: { sha?: string; url?: string }) {
  if (!sha) return null;
  const label = /^[0-9a-f]{12,}$/i.test(sha) ? sha.slice(0, 12) : sha;
  const href = safeUrl(url);
  return href ? (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      title={sha}
      style={{ color: 'var(--prism-link)' }}
    >
      {label}
    </a>
  ) : (
    <span title={sha}>{label}</span>
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
  const runUrl = safeUrl(ci?.run_url);
  const jobUrl = safeUrl(ci?.job_url);
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
                  Run: ci.run_number ? `${ci.run_id} (#${ci.run_number})` : ci.run_id,
                  Attempt: ci.attempt,
                  Job: ci.job_name,
                  Event: ci.event,
                  Branch: ci.branch,
                  Commit: ci.sha ? <Commit sha={ci.sha} url={ci.commit_url} /> : undefined,
                  Runner: ci.runner,
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
