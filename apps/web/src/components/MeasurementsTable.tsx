import { Box, Flex, Text } from '@chakra-ui/react';

import type { Measurement } from '../api/types';
import { formatEng, measurementStatus, STATUS_GLYPH } from '../lib/measurement';

const STATUS_BG: Record<string, string> = {
  pass: 'var(--prism-status-pass-bg)',
  warn: 'var(--prism-status-warn-bg)',
  fail: 'var(--prism-status-fail-bg)',
  none: 'var(--prism-bg-hover)',
};
const STATUS_FG: Record<string, string> = {
  pass: 'var(--prism-status-pass-fg)',
  warn: 'var(--prism-status-warn-fg)',
  fail: 'var(--prism-status-fail-fg)',
  none: 'var(--prism-text-faint)',
};

function specText(m: Measurement): string {
  if (m.spec_min !== null && m.spec_max !== null) {
    return `${formatEng(m.spec_min, m.unit)} … ${formatEng(m.spec_max, m.unit)}`;
  }
  if (m.spec_max !== null) return `≤ ${formatEng(m.spec_max, m.unit)}`;
  if (m.spec_min !== null) return `≥ ${formatEng(m.spec_min, m.unit)}`;
  return '—';
}

export function MarginChip({ measurement }: { measurement: Measurement }) {
  const status = measurementStatus(measurement);
  const label =
    measurement.margin === null
      ? 'no spec'
      : `${measurement.margin >= 0 ? '+' : ''}${formatEng(measurement.margin, measurement.unit)}`;
  return (
    <Flex
      align="center"
      gap={1}
      px={2}
      py="1px"
      borderRadius="sm"
      bg={STATUS_BG[status]}
      color={STATUS_FG[status]}
      fontSize="xs"
      fontWeight="600"
      display="inline-flex"
      fontFamily="mono"
    >
      <Text as="span" aria-hidden="true">
        {STATUS_GLYPH[status]}
      </Text>
      <Text as="span">{label}</Text>
    </Flex>
  );
}

export function MeasurementsTable({ measurements }: { measurements: Measurement[] }) {
  if (measurements.length === 0) return null;
  return (
    <Box>
      <Text
        fontSize="10px"
        textTransform="uppercase"
        letterSpacing="1px"
        color="var(--prism-text-faint)"
        mb={1}
      >
        Measurements
      </Text>
      <Box
        borderWidth={1}
        borderColor="var(--prism-border)"
        borderRadius="md"
        bg="var(--prism-bg-surface)"
        overflow="hidden"
      >
        {measurements.map((m, i) => (
          <Flex
            key={m.name}
            align="center"
            gap={3}
            px={3}
            py={1.5}
            borderTopWidth={i === 0 ? 0 : 1}
            borderColor="var(--prism-border)"
            fontSize="sm"
          >
            <Text flex="1" minW={0} color="var(--prism-text-muted)" fontWeight="600" truncate>
              {m.name}
            </Text>
            <Text
              fontFamily="mono"
              color="var(--prism-text)"
              minW={{ base: '70px', md: '110px' }}
              textAlign="right"
            >
              {formatEng(m.value, m.unit)}
            </Text>
            <Text
              fontFamily="mono"
              color="var(--prism-text-faint)"
              minW="160px"
              textAlign="right"
              fontSize="xs"
              display={{ base: 'none', md: 'block' }}
            >
              {specText(m)}
            </Text>
            <Box minW={{ base: 'auto', md: '100px' }} textAlign="right">
              <MarginChip measurement={m} />
            </Box>
          </Flex>
        ))}
      </Box>
    </Box>
  );
}
