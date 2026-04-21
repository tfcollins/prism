import { Box, Stack, Text } from '@chakra-ui/react';

import { useSuiteCases } from '../api/queries';
import type { SuiteSummary } from '../api/types';

const STATUS_DOT: Record<string, string> = {
  pass: '#48bb78',
  fail: '#f56565',
  error: '#f56565',
  skip: '#a0aec0',
};

interface Props {
  suites: SuiteSummary[];
  selectedCaseId: string | null;
  onSelectCase: (caseId: string) => void;
}

export function TestTree({ suites, selectedCaseId, onSelectCase }: Props) {
  return (
    <Stack gap={2}>
      {suites.map((s) => (
        <SuiteNode key={s.id} suite={s} selectedCaseId={selectedCaseId} onSelectCase={onSelectCase} />
      ))}
    </Stack>
  );
}

function SuiteNode({
  suite,
  selectedCaseId,
  onSelectCase,
}: {
  suite: SuiteSummary;
  selectedCaseId: string | null;
  onSelectCase: (caseId: string) => void;
}) {
  const q = useSuiteCases(suite.id);
  return (
    <Box>
      <Text fontSize="sm" fontWeight="600" color="gray.300" mb={1}>
        {suite.name}
      </Text>
      <Stack gap={0} pl={2}>
        {q.data?.map((c) => (
          <Box
            key={c.id}
            onClick={() => onSelectCase(c.id)}
            cursor="pointer"
            px={2}
            py={1}
            borderRadius="4px"
            bg={selectedCaseId === c.id ? '#2c5282' : 'transparent'}
            _hover={{ bg: selectedCaseId === c.id ? '#2c5282' : '#2d3748' }}
            fontSize="xs"
            color={selectedCaseId === c.id ? 'white' : '#cbd5e0'}
          >
            <Box
              as="span"
              display="inline-block"
              w="6px"
              h="6px"
              borderRadius="full"
              bg={STATUS_DOT[c.status]}
              mr={2}
            />
            {c.name}
          </Box>
        ))}
      </Stack>
    </Box>
  );
}
