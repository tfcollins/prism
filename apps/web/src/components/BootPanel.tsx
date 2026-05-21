// apps/web/src/components/BootPanel.tsx
import { Box, Flex, Text } from '@chakra-ui/react';

import { useRunLogs } from '../api/queries';
import type { BootSummary } from '../api/types';

const SEV_FG: Record<string, string> = {
  panic: 'var(--prism-status-fail-fg)',
  error: 'var(--prism-status-fail-fg)',
  probe_fail: 'var(--prism-status-warn-fg)',
  warn: 'var(--prism-status-warn-fg)',
};

function CommitLine({ label, commit, url, shared }: {
  label: string; commit: string | null; url: string | null; shared: number;
}) {
  if (!commit) return null;
  return (
    <Flex align="center" gap={2} fontSize="sm">
      <Text color="var(--prism-text-faint)" minW="48px">{label}</Text>
      {url ? (
        <a href={url} target="_blank" rel="noreferrer" style={{ color: 'var(--prism-link)', fontFamily: 'monospace' }}>
          {commit.slice(0, 12)}
        </a>
      ) : (
        <Text fontFamily="mono">{commit.slice(0, 12)}</Text>
      )}
      {shared > 0 && (
        <Text fontSize="xs" color="var(--prism-text-faint)">· {shared} other run{shared === 1 ? '' : 's'}</Text>
      )}
    </Flex>
  );
}

export function BootPanel({ runId, boot }: { runId: string; boot: BootSummary }) {
  const logs = useRunLogs(runId);
  return (
    <Box borderWidth={1} borderColor="var(--prism-border)" borderRadius="md" p={3} bg="var(--prism-bg-surface)">
      <Text fontSize="10px" textTransform="uppercase" letterSpacing="1px" color="var(--prism-text-faint)" mb={2}>
        Boot
      </Text>
      {boot.has_panic && (
        <Box mb={2} px={2} py={1} borderRadius="sm" bg="var(--prism-status-fail-bg)" color="var(--prism-status-fail-fg)" fontSize="sm" fontWeight="600">
          ✕ kernel panic detected
        </Box>
      )}
      {boot.kernel_version && <Text fontSize="sm">{boot.kernel_version}</Text>}
      {boot.board && <Text fontSize="xs" color="var(--prism-text-subtle)">{boot.board}</Text>}
      <Box mt={2}>
        <CommitLine label="kernel" commit={boot.kernel_commit} url={boot.kernel_commit_url} shared={boot.shared_kernel_count} />
        <CommitLine label="hdl" commit={boot.hdl_commit} url={boot.hdl_commit_url} shared={boot.shared_hdl_count} />
      </Box>
      <Text fontSize="xs" color="var(--prism-text-subtle)" mt={2}>
        {boot.error_count} errors · {boot.warn_count} warnings
      </Text>
      {logs.data && logs.data.some((r) => r.findings.length > 0) && (
        <Box mt={2} maxH="220px" overflowY="auto" fontFamily="mono" fontSize="xs">
          {logs.data.flatMap((r) => r.findings).map((f, i) => (
            <Text key={i} color={SEV_FG[f.severity] ?? 'var(--prism-text-muted)'} truncate>
              [{f.severity}] {f.text}
            </Text>
          ))}
        </Box>
      )}
    </Box>
  );
}
