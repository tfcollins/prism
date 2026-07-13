import { Badge, Box, Button, Checkbox, Flex, Table, Text } from '@chakra-ui/react';
import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import type { RunListItem } from '../api/types';
import { absoluteTime, relativeTime } from '../util/relativeTime';
import { Tooltip } from './Tooltip';

const STATUS_COLOR: Record<string, string> = {
  pass: '#48bb78',
  fail: '#f56565',
  mixed: '#ed8936',
  error: '#f56565',
  pending: '#a0aec0',
};

export function RunsTable({ runs }: { runs: RunListItem[] }) {
  const [selected, setSelected] = useState<Set<string>>(new Set());

  function toggle(id: string) {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSelected(next);
  }

  if (runs.length === 0) {
    return <Text color="var(--prism-text-subtle)">No runs yet.</Text>;
  }

  return (
    <Box>
      <Box overflowX="auto">
        <Table.Root variant="outline" size="sm">
          <Table.Header>
            <Table.Row>
              <Table.ColumnHeader></Table.ColumnHeader>
              <Table.ColumnHeader>Status</Table.ColumnHeader>
              <Table.ColumnHeader>Run</Table.ColumnHeader>
              <Table.ColumnHeader>Suite</Table.ColumnHeader>
              <Table.ColumnHeader>Artifacts</Table.ColumnHeader>
              <Table.ColumnHeader>Pass</Table.ColumnHeader>
              <Table.ColumnHeader>Fail</Table.ColumnHeader>
              <Table.ColumnHeader>When</Table.ColumnHeader>
              <Table.ColumnHeader>Tags</Table.ColumnHeader>
            </Table.Row>
          </Table.Header>
          <Table.Body>
            {runs.map((r) => (
              <Table.Row key={r.id}>
                <Table.Cell>
                  <Checkbox.Root
                    checked={selected.has(r.id)}
                    onCheckedChange={() => toggle(r.id)}
                    aria-label={`Select ${r.name}`}
                  >
                    <Checkbox.HiddenInput />
                    <Checkbox.Control>
                      <Checkbox.Indicator />
                    </Checkbox.Control>
                  </Checkbox.Root>
                </Table.Cell>
                <Table.Cell>
                  <Box
                    display="inline-block"
                    w="8px"
                    h="8px"
                    borderRadius="50%"
                    bg={STATUS_COLOR[r.status] ?? '#a0aec0'}
                    mr={2}
                  />
                  {r.status}
                </Table.Cell>
                <Table.Cell>
                  <Link to={`/runs/${r.id}`} style={{ color: 'var(--prism-brand)' }}>
                    {r.name}
                  </Link>
                </Table.Cell>
                <Table.Cell>
                  {r.suite_names.length === 0 && (
                    <Text as="span" fontSize="xs" color="var(--prism-text-faint)">
                      —
                    </Text>
                  )}
                  {r.suite_names.length === 1 && (
                    <Badge variant="subtle" colorPalette="blue">
                      {r.suite_names[0]}
                    </Badge>
                  )}
                  {r.suite_names.length > 1 && (
                    <Flex gap={1} wrap="wrap">
                      {r.suite_names.map((n) => (
                        <Badge key={n} variant="subtle" colorPalette="blue">
                          {n}
                        </Badge>
                      ))}
                    </Flex>
                  )}
                </Table.Cell>
                <Table.Cell>
                  <ArtifactLabels run={r} />
                </Table.Cell>
                <Table.Cell>{r.pass_count}</Table.Cell>
                <Table.Cell>{r.fail_count}</Table.Cell>
                <Table.Cell>
                  <Text
                    as="span"
                    fontSize="xs"
                    color="var(--prism-text-subtle)"
                    title={absoluteTime(r.created_at)}
                    whiteSpace="nowrap"
                  >
                    {relativeTime(r.created_at)}
                  </Text>
                </Table.Cell>
                <Table.Cell>
                  {r.tags.map((t) => (
                    <Text
                      as="span"
                      key={`${t.key}:${t.value}`}
                      mr={2}
                      fontFamily="mono"
                      fontSize="xs"
                    >
                      {t.key}={t.value}
                    </Text>
                  ))}
                </Table.Cell>
              </Table.Row>
            ))}
          </Table.Body>
        </Table.Root>
      </Box>
      <RunSelectionActions ids={Array.from(selected)} />
    </Box>
  );
}

/**
 * Compact badges flagging whether a run carries plottable figures and/or a
 * parsed boot log, so the list is scannable without opening each run. Renders a
 * faint em-dash when the run has neither.
 */
function ArtifactLabels({ run }: { run: RunListItem }) {
  if (!run.has_figures && !run.has_boot_log && !run.has_terminal_log) {
    return (
      <Text as="span" fontSize="xs" color="var(--prism-text-faint)">
        —
      </Text>
    );
  }
  return (
    <Flex gap={1} wrap="wrap">
      {run.has_figures && (
        <Tooltip content="Run has plottable artifacts (waveforms, spectra, images).">
          <Badge variant="subtle" colorPalette="purple" aria-label="Has figures">
            Figures
          </Badge>
        </Tooltip>
      )}
      {run.has_boot_log && (
        <Tooltip content="Run has a parsed boot/dmesg log.">
          <Badge variant="subtle" colorPalette="gray" aria-label="Has boot log">
            Boot log
          </Badge>
        </Tooltip>
      )}
      {run.has_terminal_log && (
        <Tooltip content="Run has terminal execution logs.">
          <Badge variant="subtle" colorPalette="cyan" aria-label="Has terminal log">
            Terminal log
          </Badge>
        </Tooltip>
      )}
    </Flex>
  );
}


/**
 * Action bar shown when run rows are selected. "Export PDF" downloads a combined
 * test-results report (flat tables, not a comparison) for the selected run(s) —
 * available for a single run too. "Compare" needs at least two runs.
 */
export function RunSelectionActions({ ids }: { ids: string[] }) {
  const navigate = useNavigate();
  if (ids.length === 0) return null;
  const runs = ids.join(',');
  return (
    <Flex mt={3} justify="flex-end" gap={2} align="center">
      <Button asChild size="sm" variant="outline">
        {/* Plain download anchor (no target=_blank): the response is an
            attachment, so it downloads in place without opening a blank tab —
            which some browsers/popup-blockers would otherwise cancel. */}
        <a href={`/api/v1/runs/report.pdf?runs=${runs}`} download="combined-report.pdf">
          Export PDF ({ids.length})
        </a>
      </Button>
      {ids.length >= 2 && (
        <Button colorPalette="blue" size="sm" onClick={() => navigate(`/compare?runs=${runs}`)}>
          Compare {ids.length} runs
        </Button>
      )}
    </Flex>
  );
}
