import { Box, Stack, Text } from '@chakra-ui/react';
import { useMemo, useState } from 'react';

import { useSuiteCases } from '../api/queries';
import type { CaseListItem, SuiteSummary } from '../api/types';
import { parseTestId, summarizeParams } from '../lib/parseTestId';

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

interface CaseGroup {
  baseName: string;
  cases: Array<CaseListItem & { paramsLabel: string }>;
}

function groupByBaseName(cases: CaseListItem[]): CaseGroup[] {
  const groups = new Map<string, CaseGroup>();
  for (const c of cases) {
    const parsed = parseTestId(c.name);
    const label = summarizeParams(parsed.params, 60);
    let g = groups.get(parsed.baseName);
    if (!g) {
      g = { baseName: parsed.baseName, cases: [] };
      groups.set(parsed.baseName, g);
    }
    g.cases.push({ ...c, paramsLabel: label });
  }
  return Array.from(groups.values());
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
  const groups = useMemo(() => (q.data ? groupByBaseName(q.data) : []), [q.data]);
  return (
    <Box>
      {!hideHeader && (
        <Text fontSize="sm" fontWeight="600" color="var(--prism-text-muted)" mb={1}>
          {suite.name}
        </Text>
      )}
      <Stack gap={0} pl={hideHeader ? 0 : 2}>
        {groups.map((g) =>
          g.cases.length === 1 ? (
            <CaseRow
              key={g.cases[0].id}
              c={g.cases[0]}
              label={g.baseName}
              selectedCaseId={selectedCaseId}
              onSelectCase={onSelectCase}
            />
          ) : (
            <CaseGroupNode
              key={g.baseName}
              group={g}
              selectedCaseId={selectedCaseId}
              onSelectCase={onSelectCase}
            />
          ),
        )}
      </Stack>
    </Box>
  );
}

function CaseGroupNode({
  group,
  selectedCaseId,
  onSelectCase,
}: {
  group: CaseGroup;
  selectedCaseId: string | null;
  onSelectCase: (caseId: string) => void;
}) {
  const containsSelected = group.cases.some((c) => c.id === selectedCaseId);
  const [open, setOpen] = useState<boolean>(containsSelected);
  const summary = aggregateStatus(group.cases);
  return (
    <Box>
      <Box
        onClick={() => setOpen((v) => !v)}
        cursor="pointer"
        px={2}
        py={1}
        borderRadius="4px"
        _hover={{ bg: 'var(--prism-bg-hover)' }}
        fontSize="xs"
        color="var(--prism-text-muted)"
        display="flex"
        alignItems="center"
      >
        <Box
          as="span"
          display="inline-block"
          w="10px"
          fontSize="10px"
          color="var(--prism-text-faint)"
          mr={1}
        >
          {open ? '▾' : '▸'}
        </Box>
        <Box
          as="span"
          display="inline-block"
          w="6px"
          h="6px"
          borderRadius="full"
          bg={STATUS_DOT[summary] ?? STATUS_DOT.pass}
          mr={2}
        />
        <Box as="span" flex="1" overflow="hidden" textOverflow="ellipsis" whiteSpace="nowrap">
          {group.baseName}
        </Box>
        <Text as="span" fontSize="10px" color="var(--prism-text-faint)" ml={2}>
          {group.cases.length}
        </Text>
      </Box>
      {open && (
        <Stack gap={0} pl={5}>
          {group.cases.map((c, i) => (
            <CaseRow
              key={c.id}
              c={c}
              label={c.paramsLabel || `[${i}]`}
              selectedCaseId={selectedCaseId}
              onSelectCase={onSelectCase}
            />
          ))}
        </Stack>
      )}
    </Box>
  );
}

function CaseRow({
  c,
  label,
  selectedCaseId,
  onSelectCase,
}: {
  c: CaseListItem;
  label: string;
  selectedCaseId: string | null;
  onSelectCase: (caseId: string) => void;
}) {
  return (
    <Box
      onClick={() => onSelectCase(c.id)}
      cursor="pointer"
      px={2}
      py={1}
      borderRadius="4px"
      bg={selectedCaseId === c.id ? 'var(--prism-bg-sel)' : 'transparent'}
      _hover={{
        bg: selectedCaseId === c.id ? 'var(--prism-bg-sel)' : 'var(--prism-bg-hover)',
      }}
      fontSize="xs"
      color={
        selectedCaseId === c.id
          ? 'var(--prism-sidebar-active-fg)'
          : 'var(--prism-text-muted)'
      }
      title={c.name}
      display="flex"
      alignItems="center"
    >
      <Box
        as="span"
        display="inline-block"
        w="6px"
        h="6px"
        borderRadius="full"
        bg={STATUS_DOT[c.status]}
        mr={2}
        flexShrink={0}
      />
      <Box as="span" overflow="hidden" textOverflow="ellipsis" whiteSpace="nowrap">
        {label}
      </Box>
    </Box>
  );
}

function aggregateStatus(cases: CaseListItem[]): string {
  if (cases.some((c) => c.status === 'fail' || c.status === 'error')) return 'fail';
  if (cases.every((c) => c.status === 'skip')) return 'skip';
  return 'pass';
}
