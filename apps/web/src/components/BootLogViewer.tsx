// apps/web/src/components/BootLogViewer.tsx
//
// Full-width, collapsible boot-log viewer. One accordion item per parsed log
// report; expanding an item lazily fetches the full raw dmesg and lets the user
// filter it (Errors / Warnings / All) and download it.
import { Accordion, Badge, Box, Button, Flex, Text } from '@chakra-ui/react';
import { useState } from 'react';

import { useArtifactRaw, useRunLogs } from '../api/queries';
import type { LogReport } from '../api/types';
import { classifyLines, type LogFilter, matchesFilter } from '../lib/dmesg';
import { severityColor } from '../lib/logFindings';

const MAX_LINES = 5000;
const FILTERS: { value: LogFilter; label: string }[] = [
  { value: 'errors', label: 'Errors' },
  { value: 'warnings', label: 'Warnings' },
  { value: 'all', label: 'All' },
];

function FilterControl({
  value,
  onChange,
}: {
  value: LogFilter;
  onChange: (f: LogFilter) => void;
}) {
  return (
    <Flex gap={1}>
      {FILTERS.map((f) => (
        <Button
          key={f.value}
          size="xs"
          variant={value === f.value ? 'solid' : 'outline'}
          colorPalette={value === f.value ? 'blue' : 'gray'}
          onClick={() => onChange(f.value)}
        >
          {f.label}
        </Button>
      ))}
    </Flex>
  );
}

/**
 * The body of one log report: the filter control, the (filtered) raw lines, and
 * a download link. `open` gates the raw fetch so closed accordion items don't
 * pull large logs. Exported for unit testing.
 */
export function BootLogBody({ report, open }: { report: LogReport; open: boolean }) {
  const [filter, setFilter] = useState<LogFilter>('all');
  const raw = useArtifactRaw(report.artifact_id, open);

  const download = report.artifact_id ? (
    <a
      href={`/api/v1/artifacts/${report.artifact_id}/raw`}
      download={report.source}
      style={{ color: 'var(--prism-link)', fontSize: '0.75rem' }}
    >
      Download
    </a>
  ) : null;

  let content;
  if (!report.artifact_id) {
    content = (
      <Text fontSize="xs" color="var(--prism-text-faint)">
        Raw log unavailable.
      </Text>
    );
  } else if (raw.isLoading) {
    content = <Text fontSize="xs">Loading log…</Text>;
  } else if (raw.isError || raw.data == null) {
    content = (
      <Text fontSize="xs" color="var(--prism-status-fail-fg)">
        Failed to load log.
      </Text>
    );
  } else {
    const all = classifyLines(raw.data);
    const lines = all.filter((l) => matchesFilter(l.severity, filter));
    const shown = lines.slice(0, MAX_LINES);
    content =
      lines.length === 0 ? (
        <Text fontSize="xs" color="var(--prism-text-faint)">
          No matching lines.
        </Text>
      ) : (
        <Box
          maxH="360px"
          overflow="auto"
          fontFamily="mono"
          fontSize="xs"
          bg="var(--prism-bg-canvas)"
          borderWidth={1}
          borderColor="var(--prism-border)"
          borderRadius="sm"
          p={2}
        >
          {shown.map((l) => (
            <Flex key={l.lineNo} gap={2} whiteSpace="pre-wrap">
              <Text as="span" color="var(--prism-text-faint)" minW="44px" textAlign="right">
                {l.lineNo}
              </Text>
              <Text as="span" color={l.severity ? severityColor(l.severity) : 'var(--prism-text)'}>
                {l.text}
              </Text>
            </Flex>
          ))}
          {lines.length > MAX_LINES && (
            <Text mt={1} color="var(--prism-text-faint)">
              … {lines.length - MAX_LINES} more lines truncated — download for the full log.
            </Text>
          )}
        </Box>
      );
  }

  return (
    <Box>
      <Flex align="center" justify="space-between" mb={2} gap={2}>
        <FilterControl value={filter} onChange={setFilter} />
        {download}
      </Flex>
      {content}
    </Box>
  );
}

function ItemHeader({ report }: { report: LogReport }) {
  return (
    <Flex align="center" gap={2} flex="1" textAlign="left">
      <Text fontFamily="mono" fontSize="sm">
        {report.source}
      </Text>
      {report.has_panic && (
        <Badge colorPalette="red" variant="solid">
          panic
        </Badge>
      )}
      <Text fontSize="xs" color="var(--prism-text-subtle)">
        {report.error_count} errors · {report.warn_count} warnings
      </Text>
    </Flex>
  );
}

export function isTerminalLog(source: string): boolean {
  const lowered = source.toLowerCase();
  return (
    lowered.includes('terminal') ||
    lowered.includes('console') ||
    lowered.includes('stdout') ||
    lowered.includes('stderr')
  );
}

interface GenericLogViewerProps {
  runId: string;
  title: string;
  filterFn: (source: string) => boolean;
}

export function GenericLogViewer({ runId, title, filterFn }: GenericLogViewerProps) {
  const logs = useRunLogs(runId);
  const [openItems, setOpenItems] = useState<string[]>([]);

  const reports = (logs.data ?? []).filter((report) => filterFn(report.source));
  if (reports.length === 0) return null;

  return (
    <Box mb={6}>
      <Text
        fontSize="10px"
        textTransform="uppercase"
        letterSpacing="1px"
        color="var(--prism-text-faint)"
        mb={1}
      >
        {title}
      </Text>
      <Accordion.Root
        multiple
        value={openItems}
        onValueChange={(e) => setOpenItems(e.value)}
        variant="outline"
      >
        {reports.map((report, i) => {
          const value = String(i);
          return (
            <Accordion.Item key={value} value={value}>
              <Accordion.ItemTrigger>
                <ItemHeader report={report} />
                <Accordion.ItemIndicator />
              </Accordion.ItemTrigger>
              <Accordion.ItemContent>
                <Accordion.ItemBody>
                  <BootLogBody report={report} open={openItems.includes(value)} />
                </Accordion.ItemBody>
              </Accordion.ItemContent>
            </Accordion.Item>
          );
        })}
      </Accordion.Root>
    </Box>
  );
}

export function BootLogViewer({ runId }: { runId: string }) {
  return (
    <GenericLogViewer
      runId={runId}
      title="Boot log"
      filterFn={(source) => !isTerminalLog(source)}
    />
  );
}

export function TerminalLogViewer({ runId }: { runId: string }) {
  return (
    <GenericLogViewer
      runId={runId}
      title="Terminal log"
      filterFn={(source) => isTerminalLog(source)}
    />
  );
}

