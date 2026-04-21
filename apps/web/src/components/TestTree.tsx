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
  /** When true, the per-suite name header is omitted and cases render directly
   *  as one flat list. Useful when a Test Suite Run contains a single
   *  `<testsuite>` (the suite name is shown once by the parent page instead). */
  flatten?: boolean;
}

export function TestTree({ suites, selectedCaseId, onSelectCase, flatten = false }: Props) {
  return (
    <Stack gap={flatten ? 0 : 2}>
      {suites.map((s) => (
        <SuiteNode
          key={s.id}
          suite={s}
          selectedCaseId={selectedCaseId}
          onSelectCase={onSelectCase}
          hideHeader={flatten}
        />
      ))}
    </Stack>
  );
}

function SuiteNode({
  suite,
  selectedCaseId,
  onSelectCase,
  hideHeader,
}: {
  suite: SuiteSummary;
  selectedCaseId: string | null;
  onSelectCase: (caseId: string) => void;
  hideHeader: boolean;
}) {
  const q = useSuiteCases(suite.id);
  return (
    <Box>
      {!hideHeader && (
        <Text fontSize="sm" fontWeight="600" color="var(--prism-text-muted)" mb={1}>
          {suite.name}
        </Text>
      )}
      <Stack gap={0} pl={hideHeader ? 0 : 2}>
        {q.data?.map((c) => (
          <Box
            key={c.id}
            onClick={() => onSelectCase(c.id)}
            cursor="pointer"
            px={2}
            py={1}
            borderRadius="4px"
            bg={selectedCaseId === c.id ? 'var(--prism-bg-sel)' : 'transparent'}
            _hover={{
              bg:
                selectedCaseId === c.id
                  ? 'var(--prism-bg-sel)'
                  : 'var(--prism-bg-hover)',
            }}
            fontSize="xs"
            color={
              selectedCaseId === c.id
                ? 'var(--prism-sidebar-active-fg)'
                : 'var(--prism-text-muted)'
            }
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
