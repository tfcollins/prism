import { Box, Flex, Heading, Table, Tabs, Text } from '@chakra-ui/react';
import { useEffect, useState } from 'react';
import { Link as RouterLink, useParams } from 'react-router-dom';

import {
  useAudit,
  useCommits,
  useDeleteSpec,
  useDeleteView,
  useMeasurementNames,
  useProjectTests,
  useRegressions,
  useRuns,
  useRunsByCommit,
  useRunsByTag,
  useSpecs,
  useTagKeys,
  useTagValues,
  useTestHistory,
  useUpsertSpec,
  useUpsertView,
  useViews,
} from '../api/queries';
import type { DashboardViewConfig, RunListItem, SpecDefinition } from '../api/types';
import { AppShell } from '../components/AppShell';
import { RunsTable } from '../components/RunsTable';
import { Tooltip } from '../components/Tooltip';
import { TrendPlot } from '../components/TrendPlot';
import { formatEng } from '../lib/measurement';

export function ProjectDashboardPage() {
  const { slug } = useParams<{ slug: string }>();
  const runsQuery = useRuns(slug);

  const [tab, setTab] = useState('runs');
  const [measurement, setMeasurement] = useState<string | null>(null);
  const [tagFilters, setTagFilters] = useState<Record<string, string>>({});
  const [commitFilter, setCommitFilter] = useState<{
    field: 'kernel_commit' | 'hdl_commit';
    commit: string;
  } | null>(null);

  const applyView = (config: DashboardViewConfig) => {
    if (config.tab) setTab(config.tab);
    setMeasurement(config.measurement ?? null);
    setTagFilters(config.tagFilters ?? {});
  };

  return (
    <AppShell>
      <Heading size="lg" mb={4}>
        {slug}
      </Heading>
      {slug && (
        <SavedViewsBar
          slug={slug}
          currentConfig={{ tab, measurement, tagFilters }}
          onApply={applyView}
        />
      )}
      <Tabs.Root value={tab} onValueChange={(e) => setTab(e.value)}>
        <Tabs.List mb={3}>
          <Tabs.Trigger value="runs">Runs</Tabs.Trigger>
          <Tabs.Trigger value="tests">Tests</Tabs.Trigger>
          <Tabs.Trigger value="duts">DUTs</Tabs.Trigger>
          <Tabs.Trigger value="trends">Trends</Tabs.Trigger>
          <Tabs.Trigger value="regressions">Regressions</Tabs.Trigger>
          <Tabs.Trigger value="specs">Specs</Tabs.Trigger>
          <Tabs.Trigger value="commits">Commits</Tabs.Trigger>
          <Tabs.Trigger value="audit">Audit</Tabs.Trigger>
        </Tabs.List>
        <Tabs.Content value="runs">
          {commitFilter ? (
            <CommitFilteredRuns
              slug={slug ?? ''}
              field={commitFilter.field}
              commit={commitFilter.commit}
              onClear={() => setCommitFilter(null)}
            />
          ) : (
            <>
              {runsQuery.isLoading && <Text>Loading…</Text>}
              {runsQuery.isError && (
                <Text color="red.400">Could not load runs — {String(runsQuery.error)}</Text>
              )}
              {runsQuery.data && (
                <RunsTab
                  runs={runsQuery.data}
                  tagFilters={tagFilters}
                  onTagFilters={setTagFilters}
                />
              )}
            </>
          )}
        </Tabs.Content>
        <Tabs.Content value="tests">{slug && <TestsTab slug={slug} />}</Tabs.Content>
        <Tabs.Content value="duts">{slug && <DutsTab slug={slug} />}</Tabs.Content>
        <Tabs.Content value="trends">
          {slug && <TrendsTab slug={slug} selected={measurement} onSelect={setMeasurement} />}
        </Tabs.Content>
        <Tabs.Content value="regressions">{slug && <RegressionsTab slug={slug} />}</Tabs.Content>
        <Tabs.Content value="specs">{slug && <SpecsTab slug={slug} />}</Tabs.Content>
        <Tabs.Content value="commits">
          {slug && (
            <CommitsTab
              slug={slug}
              onFilter={(field, commit) => {
                setCommitFilter({ field, commit });
                setTab('runs');
              }}
            />
          )}
        </Tabs.Content>
        <Tabs.Content value="audit">{slug && <AuditTab slug={slug} />}</Tabs.Content>
      </Tabs.Root>
    </AppShell>
  );
}

const DEFAULT_DUT_KEYS = ['device_serial', 'dut', 'serial', 'sn'];

function DutsTab({ slug }: { slug: string }) {
  const keysQuery = useTagKeys(slug);
  const [tagKey, setTagKey] = useState<string | null>(null);
  const [value, setValue] = useState<string | null>(null);

  const keys = keysQuery.data ?? [];
  const effectiveKey = tagKey ?? DEFAULT_DUT_KEYS.find((k) => keys.includes(k)) ?? keys[0] ?? null;

  const valuesQuery = useTagValues(slug, effectiveKey ?? undefined);
  const runsQuery = useRunsByTag(slug, effectiveKey ?? undefined, value ?? undefined);

  if (keysQuery.isLoading) return <Text>Loading…</Text>;
  if (keys.length === 0) {
    return (
      <Text color="var(--prism-text-subtle)" fontSize="sm">
        No run tags yet. Tag uploads with a DUT identifier (e.g. <code>device_serial</code>) to
        browse runs per device.
      </Text>
    );
  }

  return (
    <Box>
      <Flex align="center" gap={2} mb={3} wrap="wrap" fontSize="sm">
        <Text
          fontSize="10px"
          textTransform="uppercase"
          letterSpacing="1px"
          color="var(--prism-text-faint)"
        >
          DUT tag
        </Text>
        <Tooltip content="Choose which run tag identifies the device under test (DUT).">
          <select
            className="chakra-input"
            aria-label="DUT tag"
            value={effectiveKey ?? ''}
            onChange={(e) => {
              setTagKey(e.target.value);
              setValue(null);
            }}
            style={{ padding: '2px 6px', borderRadius: 4, borderWidth: 1, fontSize: 13 }}
          >
            {keys.map((k) => (
              <option key={k} value={k}>
                {k}
              </option>
            ))}
          </select>
        </Tooltip>
      </Flex>
      <Flex wrap="wrap" gap={2} mb={4}>
        {(valuesQuery.data ?? []).map((v) => (
          <Tooltip
            key={v.value}
            content={`Show runs tagged ${effectiveKey}=${v.value} (${v.run_count} run${
              v.run_count === 1 ? '' : 's'
            }).`}
          >
            <Box
              as="button"
              onClick={() => setValue(v.value)}
              px={3}
              py={1}
              borderRadius="md"
              borderWidth={1}
              fontSize="sm"
              cursor="pointer"
              bg={value === v.value ? 'var(--prism-sidebar-active-bg)' : 'var(--prism-bg-surface)'}
              color={
                value === v.value ? 'var(--prism-sidebar-active-fg)' : 'var(--prism-text-muted)'
              }
              borderColor="var(--prism-border)"
            >
              {v.value}{' '}
              <Text as="span" color="var(--prism-text-faint)">
                ({v.run_count})
              </Text>
            </Box>
          </Tooltip>
        ))}
      </Flex>
      {value && runsQuery.data && <RunsByDate runs={runsQuery.data} />}
      {!value && (
        <Text color="var(--prism-text-subtle)" fontSize="sm">
          Select a {effectiveKey} above to see its runs.
        </Text>
      )}
    </Box>
  );
}

function RunsByDate({ runs }: { runs: RunListItem[] }) {
  const groups = new Map<string, RunListItem[]>();
  for (const r of runs) {
    const day = (r.created_at ?? '').slice(0, 10) || 'unknown';
    const bucket = groups.get(day);
    if (bucket) bucket.push(r);
    else groups.set(day, [r]);
  }
  const days = [...groups.keys()].sort((a, b) => b.localeCompare(a));
  return (
    <Box>
      {days.map((day) => (
        <Box key={day} mb={4}>
          <Text fontSize="xs" fontWeight="600" color="var(--prism-text-subtle)" mb={1}>
            {day}
          </Text>
          <RunsTable runs={groups.get(day)!} />
        </Box>
      ))}
    </Box>
  );
}

function CommitFilteredRuns({
  slug,
  field,
  commit,
  onClear,
}: {
  slug: string;
  field: 'kernel_commit' | 'hdl_commit';
  commit: string;
  onClear: () => void;
}) {
  const q = useRunsByCommit(slug, field, commit);
  return (
    <Box>
      <Flex align="center" gap={2} mb={3}>
        <Tooltip content="Clear the commit filter and show all runs.">
          <Box
            as="button"
            onClick={onClear}
            px={2}
            py="2px"
            borderRadius="sm"
            borderWidth={1}
            fontSize="xs"
            cursor="pointer"
            bg="var(--prism-sidebar-active-bg)"
            color="var(--prism-sidebar-active-fg)"
            borderColor="var(--prism-border)"
          >
            filtered by {field} {commit.slice(0, 12)} ✕
          </Box>
        </Tooltip>
      </Flex>
      {q.isLoading && <Text>Loading…</Text>}
      {q.isError && <Text color="red.400">Could not load runs — {String(q.error)}</Text>}
      {q.data && <RunsTable runs={q.data} />}
    </Box>
  );
}

function CommitsTab({
  slug,
  onFilter,
}: {
  slug: string;
  onFilter: (field: 'kernel_commit' | 'hdl_commit', commit: string) => void;
}) {
  const kernel = useCommits(slug, 'kernel');
  const hdl = useCommits(slug, 'hdl');
  const section = (
    title: string,
    field: 'kernel_commit' | 'hdl_commit',
    data: { commit: string; run_count: number }[] | undefined,
  ) => (
    <Box mb={4}>
      <Text
        fontSize="10px"
        textTransform="uppercase"
        letterSpacing="1px"
        color="var(--prism-text-faint)"
        mb={1}
      >
        {title}
      </Text>
      {(!data || data.length === 0) && (
        <Text fontSize="sm" color="var(--prism-text-subtle)">
          none
        </Text>
      )}
      <Flex wrap="wrap" gap={2}>
        {(data ?? []).map((c) => (
          <Tooltip
            key={c.commit}
            content={`Show the ${c.run_count} run${c.run_count === 1 ? '' : 's'} built from ${
              field === 'kernel_commit' ? 'kernel' : 'HDL'
            } commit ${c.commit}`}
          >
            <Box
              as="button"
              onClick={() => onFilter(field, c.commit)}
              px={2}
              py="2px"
              borderRadius="sm"
              borderWidth={1}
              fontSize="xs"
              fontFamily="mono"
              cursor="pointer"
              bg="var(--prism-bg-surface)"
              color="var(--prism-text-muted)"
              borderColor="var(--prism-border)"
            >
              {c.commit.slice(0, 12)}{' '}
              <Text as="span" color="var(--prism-text-faint)">
                ({c.run_count})
              </Text>
            </Box>
          </Tooltip>
        ))}
      </Flex>
    </Box>
  );
  return (
    <Box>
      {section('Kernel commits', 'kernel_commit', kernel.data)}
      {section('HDL commits', 'hdl_commit', hdl.data)}
    </Box>
  );
}

function tagPairs(runs: RunListItem[]): string[] {
  const set = new Set<string>();
  for (const r of runs) for (const t of r.tags) set.add(`${t.key}=${t.value}`);
  return [...set].sort();
}

function RunsTab({
  runs,
  tagFilters,
  onTagFilters,
}: {
  runs: RunListItem[];
  tagFilters: Record<string, string>;
  onTagFilters: (f: Record<string, string>) => void;
}) {
  const filtered = runs.filter((r) =>
    Object.entries(tagFilters).every((entry) =>
      r.tags.some((t) => t.key === entry[0] && t.value === entry[1]),
    ),
  );
  const toggle = (pair: string) => {
    const [k, v] = pair.split('=');
    const next = { ...tagFilters };
    if (next[k] === v) delete next[k];
    else next[k] = v;
    onTagFilters(next);
  };
  const active = (pair: string) => {
    const [k, v] = pair.split('=');
    return tagFilters[k] === v;
  };
  return (
    <Box>
      {tagPairs(runs).length > 0 && (
        <Flex wrap="wrap" gap={2} mb={3}>
          <Tooltip content="Show only runs carrying every selected tag. Click a tag to toggle it.">
            <Text fontSize="xs" color="var(--prism-text-faint)" alignSelf="center">
              Filter by tag:
            </Text>
          </Tooltip>
          {tagPairs(runs).map((pair) => (
            <Tooltip
              key={pair}
              content={active(pair) ? `Remove filter ${pair}` : `Filter to runs tagged ${pair}`}
            >
              <Box
                as="button"
                onClick={() => toggle(pair)}
                px={2}
                py="2px"
                borderRadius="sm"
                borderWidth={1}
                fontSize="xs"
                cursor="pointer"
                bg={active(pair) ? 'var(--prism-sidebar-active-bg)' : 'var(--prism-bg-surface)'}
                color={active(pair) ? 'var(--prism-sidebar-active-fg)' : 'var(--prism-text-muted)'}
                borderColor="var(--prism-border)"
              >
                {pair}
              </Box>
            </Tooltip>
          ))}
        </Flex>
      )}
      <RunsTable runs={filtered} />
    </Box>
  );
}

const TEST_STATUS_COLOR: Record<string, string> = {
  pass: '#48bb78',
  fail: '#f56565',
  error: '#f56565',
  skip: '#a0aec0',
};

function StatusDot({ status }: { status: string }) {
  return (
    <Box
      display="inline-block"
      w="8px"
      h="8px"
      borderRadius="50%"
      bg={TEST_STATUS_COLOR[status] ?? '#a0aec0'}
      mr={2}
    />
  );
}

function StatusSparkline({ statuses }: { statuses: string[] }) {
  return (
    <Flex gap="2px">
      {statuses.map((s, i) => (
        <Box
          key={`${i}-${s}`}
          w="9px"
          h="9px"
          borderRadius="2px"
          bg={TEST_STATUS_COLOR[s] ?? '#a0aec0'}
          title={s}
        />
      ))}
    </Flex>
  );
}

function TestTimeline({
  slug,
  classname,
  name,
}: {
  slug: string;
  classname: string;
  name: string;
}) {
  const q = useTestHistory(slug, classname, name);
  if (q.isLoading) return <Text fontSize="sm">Loading…</Text>;
  if (!q.data) return null;
  return (
    <Box mt={4}>
      <Text
        fontSize="10px"
        textTransform="uppercase"
        letterSpacing="1px"
        color="var(--prism-text-faint)"
        mb={1}
      >
        {classname} · {name} — per-run history
      </Text>
      <Box overflowX="auto">
        <Table.Root variant="outline" size="sm">
          <Table.Header>
            <Table.Row>
              <Table.ColumnHeader>Status</Table.ColumnHeader>
              <Table.ColumnHeader>Run</Table.ColumnHeader>
              <Table.ColumnHeader>Duration</Table.ColumnHeader>
            </Table.Row>
          </Table.Header>
          <Table.Body>
            {q.data.map((p) => (
              <Table.Row key={p.run_id}>
                <Table.Cell>
                  <StatusDot status={p.status} />
                  {p.status}
                </Table.Cell>
                <Table.Cell>
                  <RouterLink to={`/runs/${p.run_id}`} style={{ color: 'var(--prism-brand)' }}>
                    {p.run_name}
                  </RouterLink>
                </Table.Cell>
                <Table.Cell>{p.duration_ms} ms</Table.Cell>
              </Table.Row>
            ))}
          </Table.Body>
        </Table.Root>
      </Box>
    </Box>
  );
}

function TestsTab({ slug }: { slug: string }) {
  const q = useProjectTests(slug);
  const [sel, setSel] = useState<{ classname: string; name: string } | null>(null);

  if (q.isLoading) return <Text>Loading…</Text>;
  if (q.isError) return <Text color="red.400">Could not load tests.</Text>;
  if (!q.data || q.data.length === 0) {
    return (
      <Text color="var(--prism-text-subtle)" fontSize="sm">
        No test results yet.
      </Text>
    );
  }

  return (
    <Box>
      <Box overflowX="auto">
        <Table.Root variant="outline" size="sm">
          <Table.Header>
            <Table.Row>
              <Table.ColumnHeader>Test</Table.ColumnHeader>
              <Table.ColumnHeader>Runs</Table.ColumnHeader>
              <Table.ColumnHeader>Fail rate</Table.ColumnHeader>
              <Table.ColumnHeader>
                <Tooltip content="Pass⇄fail flips across the run history — higher means flakier.">
                  <Box as="span">Flaky</Box>
                </Tooltip>
              </Table.ColumnHeader>
              <Table.ColumnHeader>Last</Table.ColumnHeader>
              <Table.ColumnHeader>Avg</Table.ColumnHeader>
              <Table.ColumnHeader>Recent</Table.ColumnHeader>
            </Table.Row>
          </Table.Header>
          <Table.Body>
            {q.data.map((t) => {
              const active = sel?.classname === t.classname && sel?.name === t.name;
              return (
                <Table.Row
                  key={`${t.classname}/${t.name}`}
                  onClick={() => setSel(active ? null : { classname: t.classname, name: t.name })}
                  cursor="pointer"
                  bg={active ? 'var(--prism-sidebar-active-bg)' : undefined}
                >
                  <Table.Cell>
                    <Text as="span" fontSize="sm">
                      {t.name}
                    </Text>{' '}
                    <Text as="span" fontSize="xs" color="var(--prism-text-faint)">
                      {t.classname}
                    </Text>
                  </Table.Cell>
                  <Table.Cell>{t.runs}</Table.Cell>
                  <Table.Cell>{(t.fail_rate * 100).toFixed(0)}%</Table.Cell>
                  <Table.Cell>{t.flaky_score}</Table.Cell>
                  <Table.Cell>
                    <StatusDot status={t.last_status} />
                    {t.last_status}
                  </Table.Cell>
                  <Table.Cell>{Math.round(t.avg_duration_ms)} ms</Table.Cell>
                  <Table.Cell>
                    <StatusSparkline statuses={t.recent_statuses} />
                  </Table.Cell>
                </Table.Row>
              );
            })}
          </Table.Body>
        </Table.Root>
      </Box>
      {sel && <TestTimeline slug={slug} classname={sel.classname} name={sel.name} />}
    </Box>
  );
}

function SavedViewsBar({
  slug,
  currentConfig,
  onApply,
}: {
  slug: string;
  currentConfig: DashboardViewConfig;
  onApply: (config: DashboardViewConfig) => void;
}) {
  const viewsQuery = useViews(slug);
  const upsert = useUpsertView(slug);
  const del = useDeleteView(slug);
  const [selected, setSelected] = useState('');
  const views = viewsQuery.data ?? [];

  return (
    <Flex align="center" gap={2} mb={3} fontSize="sm" wrap="wrap">
      <Text
        fontSize="10px"
        textTransform="uppercase"
        letterSpacing="1px"
        color="var(--prism-text-faint)"
      >
        View
      </Text>
      <Tooltip content="Apply a saved view — restores its tab, tag filters, and selection.">
        <select
          className="chakra-input"
          aria-label="Saved view"
          value={selected}
          onChange={(e) => {
            setSelected(e.target.value);
            const v = views.find((x) => x.name === e.target.value);
            if (v) onApply(v.config);
          }}
          style={{
            padding: '2px 6px',
            borderRadius: 4,
            borderWidth: 1,
            fontSize: 13,
            minWidth: 140,
          }}
        >
          <option value="">— none —</option>
          {views.map((v) => (
            <option key={v.name} value={v.name}>
              {v.name}
            </option>
          ))}
        </select>
      </Tooltip>
      <Tooltip content="Save the current tab and tag filters as a named view you can re-apply later.">
        <Box
          as="button"
          onClick={() => {
            const name = window.prompt('Save current view as:');
            if (name) {
              upsert.mutate({ name, config: currentConfig });
              setSelected(name);
            }
          }}
          px={2}
          py="2px"
          borderRadius="sm"
          borderWidth={1}
          fontSize="xs"
          cursor="pointer"
          bg="var(--prism-sidebar-active-bg)"
          color="var(--prism-sidebar-active-fg)"
          borderColor="var(--prism-border)"
        >
          save current
        </Box>
      </Tooltip>
      {selected && (
        <Tooltip content="Delete the selected saved view.">
          <Box
            as="button"
            onClick={() => {
              del.mutate(selected);
              setSelected('');
            }}
            px={2}
            py="2px"
            borderRadius="sm"
            borderWidth={1}
            fontSize="xs"
            cursor="pointer"
            bg="var(--prism-bg-surface)"
            color="var(--prism-text-muted)"
            borderColor="var(--prism-border)"
          >
            delete
          </Box>
        </Tooltip>
      )}
    </Flex>
  );
}

function RegressionsTab({ slug }: { slug: string }) {
  const q = useRegressions(slug);
  if (q.isLoading) return <Text>Loading…</Text>;
  if (!q.data || q.data.events.length === 0) {
    return (
      <Text color="var(--prism-text-subtle)" fontSize="sm">
        No spec regressions — every measurement with a limit is within spec across all runs.
      </Text>
    );
  }
  return (
    <Box overflowX="auto">
      <Table.Root variant="outline" size="sm">
        <Table.Header>
          <Table.Row>
            <Table.ColumnHeader>Run</Table.ColumnHeader>
            <Table.ColumnHeader>Measurement</Table.ColumnHeader>
            <Table.ColumnHeader textAlign="end">Value</Table.ColumnHeader>
            <Table.ColumnHeader textAlign="end">Previous</Table.ColumnHeader>
            <Table.ColumnHeader>Status</Table.ColumnHeader>
          </Table.Row>
        </Table.Header>
        <Table.Body>
          {q.data.events.map((e) => (
            <Table.Row key={`${e.run_id}:${e.measurement_name}`}>
              <Table.Cell>
                <RouterLink to={`/runs/${e.run_id}`} style={{ color: 'var(--prism-link)' }}>
                  {e.run_name}
                </RouterLink>
              </Table.Cell>
              <Table.Cell fontWeight="600">{e.measurement_name}</Table.Cell>
              <Table.Cell textAlign="end" fontFamily="mono">
                {formatEng(e.value, e.unit)}
              </Table.Cell>
              <Table.Cell textAlign="end" fontFamily="mono" color="var(--prism-text-faint)">
                {e.previous_value === null ? '—' : formatEng(e.previous_value, e.unit)}
              </Table.Cell>
              <Table.Cell>
                <Text
                  as="span"
                  fontSize="xs"
                  fontWeight="600"
                  px={2}
                  py="1px"
                  borderRadius="sm"
                  bg={
                    e.kind === 'crossed_out'
                      ? 'var(--prism-status-fail-bg)'
                      : 'var(--prism-status-warn-bg)'
                  }
                  color={
                    e.kind === 'crossed_out'
                      ? 'var(--prism-status-fail-fg)'
                      : 'var(--prism-status-warn-fg)'
                  }
                >
                  {e.kind === 'crossed_out' ? '✕ crossed out of spec' : '△ still out'}
                </Text>
              </Table.Cell>
            </Table.Row>
          ))}
        </Table.Body>
      </Table.Root>
    </Box>
  );
}

function AuditTab({ slug }: { slug: string }) {
  const q = useAudit(slug);
  if (q.isLoading) return <Text>Loading…</Text>;
  if (!q.data || q.data.length === 0) {
    return (
      <Text color="var(--prism-text-subtle)" fontSize="sm">
        No activity recorded yet.
      </Text>
    );
  }
  return (
    <Box overflowX="auto">
      <Table.Root variant="outline" size="sm">
        <Table.Header>
          <Table.Row>
            <Table.ColumnHeader>When</Table.ColumnHeader>
            <Table.ColumnHeader>Who</Table.ColumnHeader>
            <Table.ColumnHeader>Action</Table.ColumnHeader>
            <Table.ColumnHeader>Target</Table.ColumnHeader>
          </Table.Row>
        </Table.Header>
        <Table.Body>
          {q.data.map((e, i) => (
            <Table.Row key={`${e.created_at}:${i}`}>
              <Table.Cell fontFamily="mono" fontSize="xs" color="var(--prism-text-muted)">
                {e.created_at.replace('T', ' ').slice(0, 19)}
              </Table.Cell>
              <Table.Cell fontSize="sm">{e.user_email ?? '—'}</Table.Cell>
              <Table.Cell fontFamily="mono" fontSize="xs">
                {e.action}
              </Table.Cell>
              <Table.Cell fontSize="xs" color="var(--prism-text-muted)">
                {e.target_type ? `${e.target_type}:${e.target_id ?? ''}` : '—'}
              </Table.Cell>
            </Table.Row>
          ))}
        </Table.Body>
      </Table.Root>
    </Box>
  );
}

function SpecsTab({ slug }: { slug: string }) {
  const specsQuery = useSpecs(slug);
  const namesQuery = useMeasurementNames(slug);

  if (specsQuery.isLoading || namesQuery.isLoading) return <Text>Loading…</Text>;

  const specByName = new Map((specsQuery.data ?? []).map((s) => [s.measurement_name, s]));
  const names = [...new Set([...(namesQuery.data ?? []), ...specByName.keys()])].sort((a, b) =>
    a.localeCompare(b),
  );

  if (names.length === 0) {
    return (
      <Text color="var(--prism-text-subtle)" fontSize="sm">
        No measurements yet. Once runs report measurements, set per-name limits here; they apply at
        read time to any run whose measurement carried no embedded limits.
      </Text>
    );
  }

  return (
    <Box>
      <Text color="var(--prism-text-subtle)" fontSize="sm" mb={2}>
        Project limits fill in for measurements that arrived without their own. Limits embedded in a
        run at ingest always win, so editing here never rewrites historical pass/fail.
      </Text>
      <Box overflowX="auto">
        <Table.Root variant="outline" size="sm">
          <Table.Header>
            <Table.Row>
              <Table.ColumnHeader>Measurement</Table.ColumnHeader>
              <Table.ColumnHeader>Min</Table.ColumnHeader>
              <Table.ColumnHeader>Max</Table.ColumnHeader>
              <Table.ColumnHeader>Unit</Table.ColumnHeader>
              <Table.ColumnHeader />
            </Table.Row>
          </Table.Header>
          <Table.Body>
            {names.map((name) => (
              <SpecRow key={name} slug={slug} name={name} existing={specByName.get(name) ?? null} />
            ))}
          </Table.Body>
        </Table.Root>
      </Box>
    </Box>
  );
}

function numOrNull(s: string): number | null {
  const t = s.trim();
  if (t === '') return null;
  const v = Number(t);
  return Number.isFinite(v) ? v : null;
}

function SpecRow({
  slug,
  name,
  existing,
}: {
  slug: string;
  name: string;
  existing: SpecDefinition | null;
}) {
  const upsert = useUpsertSpec(slug);
  const del = useDeleteSpec(slug);
  const [min, setMin] = useState(existing?.spec_min != null ? String(existing.spec_min) : '');
  const [max, setMax] = useState(existing?.spec_max != null ? String(existing.spec_max) : '');
  const [unit, setUnit] = useState(existing?.unit ?? '');

  const inputStyle = {
    width: 90,
    padding: '2px 6px',
    borderRadius: 4,
    borderWidth: 1,
    fontFamily: 'monospace',
    fontSize: 13,
  } as const;

  return (
    <Table.Row>
      <Table.Cell fontWeight="600">{name}</Table.Cell>
      <Table.Cell>
        <input
          className="chakra-input"
          value={min}
          inputMode="decimal"
          onChange={(e) => setMin(e.target.value)}
          style={inputStyle}
        />
      </Table.Cell>
      <Table.Cell>
        <input
          className="chakra-input"
          value={max}
          inputMode="decimal"
          onChange={(e) => setMax(e.target.value)}
          style={inputStyle}
        />
      </Table.Cell>
      <Table.Cell>
        <input
          className="chakra-input"
          value={unit}
          onChange={(e) => setUnit(e.target.value)}
          style={{ ...inputStyle, width: 60 }}
        />
      </Table.Cell>
      <Table.Cell>
        <Flex gap={2}>
          <Box
            as="button"
            onClick={() =>
              upsert.mutate({
                measurement_name: name,
                spec_min: numOrNull(min),
                spec_max: numOrNull(max),
                unit: unit.trim() || null,
              })
            }
            px={2}
            py="2px"
            borderRadius="sm"
            borderWidth={1}
            fontSize="xs"
            cursor="pointer"
            bg="var(--prism-sidebar-active-bg)"
            color="var(--prism-sidebar-active-fg)"
            borderColor="var(--prism-border)"
          >
            save
          </Box>
          {existing && (
            <Box
              as="button"
              onClick={() => del.mutate(name)}
              px={2}
              py="2px"
              borderRadius="sm"
              borderWidth={1}
              fontSize="xs"
              cursor="pointer"
              bg="var(--prism-bg-surface)"
              color="var(--prism-text-muted)"
              borderColor="var(--prism-border)"
            >
              clear
            </Box>
          )}
        </Flex>
      </Table.Cell>
    </Table.Row>
  );
}

function TrendsTab({
  slug,
  selected,
  onSelect,
}: {
  slug: string;
  selected: string | null;
  onSelect: (name: string) => void;
}) {
  const namesQuery = useMeasurementNames(slug);

  useEffect(() => {
    if (selected === null && namesQuery.data && namesQuery.data.length > 0) {
      onSelect(namesQuery.data[0]);
    }
  }, [namesQuery.data, selected, onSelect]);

  if (namesQuery.isLoading) return <Text>Loading measurements…</Text>;
  if (!namesQuery.data || namesQuery.data.length === 0) {
    return (
      <Text color="var(--prism-text-subtle)" fontSize="sm">
        No measurements recorded yet. Emit them from your tests with pytest&apos;s{' '}
        <code>record_property(&quot;name&quot;, value)</code> (and <code>name__unit</code> /{' '}
        <code>name__min</code> / <code>name__max</code> for units and limits).
      </Text>
    );
  }

  return (
    <Box>
      <Flex wrap="wrap" gap={2} mb={3}>
        {namesQuery.data.map((name) => (
          <Box
            as="button"
            key={name}
            onClick={() => onSelect(name)}
            px={3}
            py={1}
            borderRadius="md"
            borderWidth={1}
            fontSize="sm"
            cursor="pointer"
            bg={selected === name ? 'var(--prism-sidebar-active-bg)' : 'var(--prism-bg-surface)'}
            color={selected === name ? 'var(--prism-sidebar-active-fg)' : 'var(--prism-text-muted)'}
            borderColor="var(--prism-border)"
          >
            {name}
          </Box>
        ))}
      </Flex>
      {selected && <TrendPlot projectSlug={slug} measurementName={selected} />}
    </Box>
  );
}
