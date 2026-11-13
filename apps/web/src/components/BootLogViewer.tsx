// apps/web/src/components/BootLogViewer.tsx
//
// Full-width, collapsible boot-log viewer. One accordion item per parsed log
// report; expanding an item lazily fetches the full raw dmesg and lets the user
// filter it (Errors / Warnings / All) and download it.
import { Accordion, Badge, Box, Button, Flex, Text } from '@chakra-ui/react';
import { useMemo, useState } from 'react';

import { useArtifactRaw, useRunLogs } from '../api/queries';
import type { CaseArtifact, LogReport } from '../api/types';
import {
  classifyLines,
  isCapturedOutput,
  isTerminalLog,
  type LogFilter,
  matchesFilter,
} from '../lib/dmesg';
import { severityColor } from '../lib/logFindings';

const LINE_BATCH = 5000;
type LogSource = Pick<LogReport, 'source' | 'artifact_id'> & Partial<LogReport>;
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
export function BootLogBody({ report, open }: { report: LogSource; open: boolean }) {
  const [filter, setFilter] = useState<LogFilter>('all');
  const [visibleLines, setVisibleLines] = useState(LINE_BATCH);
  const raw = useArtifactRaw(report.artifact_id, open);
  const lines = useMemo(
    () => classifyLines(raw.data ?? '').filter((line) => matchesFilter(line.severity, filter)),
    [raw.data, filter],
  );

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
  if (!open) {
    content = null;
  } else if (!report.artifact_id) {
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
    const shown = lines.slice(0, visibleLines);
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
            <div key={l.lineNo} style={{ display: 'flex', gap: 8, whiteSpace: 'pre-wrap' }}>
              <span
                style={{
                  color: 'var(--prism-text-faint)',
                  minWidth: 44,
                  textAlign: 'right',
                  flexShrink: 0,
                }}
              >
                {l.lineNo}
              </span>
              <span
                style={{
                  color: l.severity ? severityColor(l.severity) : 'var(--prism-text)',
                  overflowWrap: 'anywhere',
                  minWidth: 0,
                }}
              >
                {l.text}
              </span>
            </div>
          ))}
          {lines.length > visibleLines && (
            <Button
              mt={2}
              size="xs"
              variant="outline"
              onClick={() => setVisibleLines((count) => count + LINE_BATCH)}
            >
              Show more lines ({lines.length - visibleLines} remaining)
            </Button>
          )}
        </Box>
      );
  }

  return (
    <Box>
      <Flex align="center" justify="space-between" mb={2} gap={2}>
        <FilterControl
          value={filter}
          onChange={(next) => {
            setFilter(next);
            setVisibleLines(LINE_BATCH);
          }}
        />
        {download}
      </Flex>
      {content}
    </Box>
  );
}

function ItemHeader({ report }: { report: LogSource }) {
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
      {report.error_count != null && (
        <Text fontSize="xs" color="var(--prism-text-subtle)">
          {report.error_count} errors · {report.warn_count} warnings
        </Text>
      )}
    </Flex>
  );
}

interface GenericLogViewerProps {
  runId: string;
  title: string;
  filterFn: (source: string) => boolean;
}

export function GenericLogViewer({ runId, title, filterFn }: GenericLogViewerProps) {
  const logs = useRunLogs(runId);
  const reports = (logs.data ?? []).filter((report) => filterFn(report.source));
  if (logs.isLoading) return <Text fontSize="xs">Loading {title}…</Text>;
  if (logs.isError)
    return (
      <Text fontSize="xs" color="var(--prism-status-fail-fg)">
        Failed to load {title}.
      </Text>
    );
  return <LogAccordion title={title} reports={reports} />;
}

function LogAccordion({ title, reports }: { title: string; reports: LogSource[] }) {
  const [openItems, setOpenItems] = useState<string[]>([]);
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
      {reports.length === 0 && (
        <Text fontSize="xs" color="var(--prism-text-faint)">
          {title} unavailable.
        </Text>
      )}
      <Accordion.Root
        multiple
        value={openItems}
        onValueChange={(e) => setOpenItems(e.value)}
        variant="outline"
      >
        {reports.map((report) => {
          const value = report.artifact_id ?? report.source;
          return (
            <Accordion.Item key={value} value={value}>
              <Accordion.ItemTrigger>
                <ItemHeader report={report} />
                <Accordion.ItemIndicator />
              </Accordion.ItemTrigger>
              <Accordion.ItemContent>
                <Accordion.ItemBody>
                  {openItems.includes(value) && <BootLogBody key={value} report={report} open />}
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
    <GenericLogViewer runId={runId} title="dmesg" filterFn={(source) => !isTerminalLog(source)} />
  );
}

export function TerminalLogViewer({ runId }: { runId: string }) {
  return (
    <GenericLogViewer
      runId={runId}
      title="Pytest output"
      filterFn={(source) => isTerminalLog(source)}
    />
  );
}

export function CapturedOutputViewer({ artifacts }: { artifacts: CaseArtifact[] }) {
  const reports = artifacts.filter(isCapturedOutput).map((artifact) => ({
    source: artifact.filename,
    artifact_id: artifact.id,
  }));
  return <LogAccordion title="Captured output" reports={reports} />;
}
