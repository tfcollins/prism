import { Box, Flex, Text } from '@chakra-ui/react';

import type { MatrixCell, MatrixResponse, RunStatus } from '../api/types';

// Bold wall palette (approved mockup). Saturated, glow on fail.
const CELL_STYLE: Record<RunStatus, { bg: string; glow?: string }> = {
  pass: { bg: 'linear-gradient(150deg,#238636,#1a6e2e)' },
  fail: { bg: 'linear-gradient(150deg,#da3633,#a8201d)', glow: '0 0 22px -6px rgba(218,54,51,.7)' },
  mixed: { bg: 'linear-gradient(150deg,#bb8009,#8a5e00)' },
  error: { bg: 'linear-gradient(150deg,#8957e5,#6e40c9)' },
  pending: { bg: '#21262d' },
};

function ageLabel(seconds: number): string {
  if (seconds < 90) return `${seconds}s`;
  if (seconds < 5400) return `${Math.round(seconds / 60)}m`;
  if (seconds < 172800) return `${Math.round(seconds / 3600)}h`;
  return `${Math.round(seconds / 86400)}d`;
}

const ICON: Record<RunStatus, string> = {
  pass: '✓', fail: '✕', mixed: '~', error: '!', pending: '·',
};

function Cell({ cell }: { cell: MatrixCell | undefined }) {
  if (!cell) {
    return (
      <Box
        minH="78px"
        borderRadius="10px"
        border="1px dashed var(--prism-border)"
        bg="var(--prism-bg-surface)"
        color="var(--prism-text-faint)"
        display="flex"
        alignItems="center"
        justifyContent="center"
        fontSize="11px"
      >
        no run
      </Box>
    );
  }
  const style = CELL_STYLE[cell.status];
  return (
    <Box
      minH="78px"
      borderRadius="10px"
      position="relative"
      color="#fff"
      backgroundImage={style.bg}
      boxShadow={style.glow ? `${style.glow}, 0 0 0 1px rgba(255,255,255,.06) inset` : undefined}
      display="flex"
      flexDirection="column"
      alignItems="center"
      justifyContent="center"
      gap="2px"
    >
      {cell.stale && (
        <Box
          position="absolute"
          top="6px"
          left="8px"
          fontSize="8.5px"
          fontWeight="800"
          letterSpacing=".08em"
          bg="#d29922"
          color="#1a1205"
          px="5px"
          borderRadius="4px"
        >
          STALE
        </Box>
      )}
      <Text fontSize="18px" lineHeight="1">{ICON[cell.status]}</Text>
      <Text fontSize="12px" fontWeight="800" letterSpacing=".06em">
        {cell.status.toUpperCase()}
      </Text>
      <Text fontSize="11px" opacity={0.92}>{cell.passed}/{cell.total}</Text>
      <Text position="absolute" bottom="6px" right="8px" fontSize="10px" opacity={0.7}>
        {ageLabel(cell.age_seconds)}
      </Text>
    </Box>
  );
}

function Kpi({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <Flex
      aria-label={`${label} count: ${value}`}
      align="center"
      gap="7px"
      bg="var(--prism-bg-surface)"
      border="1px solid var(--prism-border)"
      borderRadius="10px"
      px="12px"
      py="6px"
      fontSize="13px"
      fontWeight="700"
    >
      <Text fontSize="16px" color={color}>{value}</Text>
      <Text color="var(--prism-text-muted)">{label}</Text>
    </Flex>
  );
}

export function MatrixGrid({ data }: { data: MatrixResponse }) {
  const { rows, cols, cells, summary } = data;
  const template = `160px repeat(${cols.length}, 1fr)`;
  return (
    <Box>
      <Flex gap="8px" mb="16px" wrap="wrap">
        <Kpi label="pass" value={summary.pass ?? 0} color="#3fb950" />
        <Kpi label="fail" value={summary.fail ?? 0} color="#ff7b72" />
        <Kpi label="mixed" value={summary.mixed ?? 0} color="#e3b341" />
        <Kpi label="error" value={summary.error ?? 0} color="#a371f7" />
        <Kpi label="no run" value={summary.no_run ?? 0} color="var(--prism-text-muted)" />
      </Flex>
      <Box display="grid" gridTemplateColumns={template} gap="8px">
        <Box />
        {cols.map((c) => (
          <Text key={c} textAlign="center" fontSize="12px" fontWeight="700"
                color="var(--prism-text-muted)" py="6px">
            {c}
          </Text>
        ))}
        {rows.map((r) => (
          <Box key={r} display="contents">
            <Flex align="center" fontSize="14px" fontWeight="700" color="var(--prism-text)" pr="8px">
              {r}
            </Flex>
            {cols.map((c) => (
              <Cell key={`${r}|${c}`} cell={cells[`${r}|${c}`]} />
            ))}
          </Box>
        ))}
      </Box>
    </Box>
  );
}
