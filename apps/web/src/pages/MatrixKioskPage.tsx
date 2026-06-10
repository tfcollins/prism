import { Box, Flex, Text } from '@chakra-ui/react';
import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';

import { useMatrix, useMatrixConfig } from '../api/queries';
import { MatrixGrid } from '../components/MatrixGrid';

export function MatrixKioskPage() {
  const [params] = useSearchParams();
  const scope = params.get('scope') ?? 'global';
  const config = useMatrixConfig(scope);
  const cfg = config.data?.config;
  const refreshMs = (cfg?.refresh_seconds ?? 30) * 1000;
  const rotateFilters = cfg?.rotate_filters ?? [];
  const queryBootFiles = params.getAll('boot_file');

  // Auto-rotate through configured boot-file filters (always on in kiosk).
  // Rotation is skipped when explicit boot_file query params are present.
  const [rotIdx, setRotIdx] = useState(0);
  useEffect(() => {
    if (rotateFilters.length < 2 || queryBootFiles.length > 0) return;
    const t = setInterval(() => setRotIdx((i) => (i + 1) % rotateFilters.length), refreshMs);
    return () => clearInterval(t);
  }, [rotateFilters.length, refreshMs, queryBootFiles.length]);

  const activeBoot =
    queryBootFiles.length > 0
      ? queryBootFiles
      : rotateFilters.length > 0
        ? [rotateFilters[rotIdx % rotateFilters.length]]
        : [];
  const q = useMatrix(scope, activeBoot, refreshMs);

  return (
    <Box minH="100vh" bg="var(--prism-bg-canvas)" p={6}>
      <Flex justify="space-between" align="baseline" mb={4}>
        <Text fontSize="2xl" fontWeight="800" color="var(--prism-text)">
          Kuiper Linux — {scope === 'global' ? 'All releases' : scope.replace('project:', '')}
        </Text>
        <Text fontSize="sm" color="var(--prism-text-muted)">
          {activeBoot.length > 0 ? `showing: ${activeBoot.join(', ')} · ` : ''}
          {q.isFetching ? 'refreshing…' : 'live'}
        </Text>
      </Flex>
      {q.data ? (
        <MatrixGrid data={q.data} />
      ) : q.isError ? (
        <Text color="red.400">Error loading matrix data. Retrying…</Text>
      ) : (
        <Text color="var(--prism-text-muted)">Loading…</Text>
      )}
    </Box>
  );
}
