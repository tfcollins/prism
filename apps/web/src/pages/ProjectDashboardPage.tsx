import { Box, Flex, Heading, Table, Tabs, Text } from '@chakra-ui/react';
import { useEffect, useState } from 'react';
import { Link as RouterLink, useParams } from 'react-router-dom';

import {
  useAudit,
  useDeleteSpec,
  useDeleteView,
  useMeasurementNames,
  useRegressions,
  useRuns,
  useRunsByTag,
  useSpecs,
  useTagKeys,
  useTagValues,
  useUpsertSpec,
  useUpsertView,
  useViews,
} from '../api/queries';
import type { DashboardViewConfig, RunListItem, SpecDefinition } from '../api/types';
import { AppShell } from '../components/AppShell';
import { RunsTable } from '../components/RunsTable';
import { TrendPlot } from '../components/TrendPlot';
import { formatEng } from '../lib/measurement';

export function ProjectDashboardPage() {
  const { slug } = useParams<{ slug: string }>();
  const runsQuery = useRuns(slug);

  const [tab, setTab] = useState('runs');
  const [measurement, setMeasurement] = useState<string | null>(null);
  const [tagFilters, setTagFilters] = useState<Record<string, string>>({});

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
          <Tabs.Trigger value="duts">DUTs</Tabs.Trigger>
          <Tabs.Trigger value="trends">Trends</Tabs.Trigger>
          <Tabs.Trigger value="regressions">Regressions</Tabs.Trigger>
          <Tabs.Trigger value="specs">Specs</Tabs.Trigger>
          <Tabs.Trigger value="audit">Audit</Tabs.Trigger>
        </Tabs.List>
        <Tabs.Content value="runs">
          {runsQuery.isLoading && <Text>Loading…</Text>}
          {runsQuery.isError && (
            <Text color="red.400">Could not load runs — {String(runsQuery.error)}</Text>
          )}
          {runsQuery.data && (
            <RunsTab runs={runsQuery.data} tagFilters={tagFilters} onTagFilters={setTagFilters} />
          )}
        </Tabs.Content>
        <Tabs.Content value="duts">{slug && <DutsTab slug={slug} />}</Tabs.Content>
        <Tabs.Content value="trends">
          {slug && <TrendsTab slug={slug} selected={measurement} onSelect={setMeasurement} />}
        </Tabs.Content>
        <Tabs.Content value="regressions">{slug && <RegressionsTab slug={slug} />}</Tabs.Content>
        <Tabs.Content value="specs">{slug && <SpecsTab slug={slug} />}</Tabs.Content>
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
        <select
          className="chakra-input"
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
      </Flex>
      <Flex wrap="wrap" gap={2} mb={4}>
        {(valuesQuery.data ?? []).map((v) => (
          <Box
            as="button"
            key={v.value}
            onClick={() => setValue(v.value)}
            px={3}
            py={1}
            borderRadius="md"
            borderWidth={1}
            fontSize="sm"
            cursor="pointer"
            bg={value === v.value ? 'var(--prism-sidebar-active-bg)' : 'var(--prism-bg-surface)'}
            color={value === v.value ? 'var(--prism-sidebar-active-fg)' : 'var(--prism-text-muted)'}
            borderColor="var(--prism-border)"
          >
            {v.value}{' '}
            <Text as="span" color="var(--prism-text-faint)">
              ({v.run_count})
            </Text>
          </Box>
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
          <Text fontSize="xs" color="var(--prism-text-faint)" alignSelf="center">
            Filter by tag:
          </Text>
          {tagPairs(runs).map((pair) => (
            <Box
              as="button"
              key={pair}
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
          ))}
        </Flex>
      )}
      <RunsTable runs={filtered} />
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
      <select
        className="chakra-input"
        value={selected}
        onChange={(e) => {
          setSelected(e.target.value);
          const v = views.find((x) => x.name === e.target.value);
          if (v) onApply(v.config);
        }}
        style={{ padding: '2px 6px', borderRadius: 4, borderWidth: 1, fontSize: 13, minWidth: 140 }}
      >
        <option value="">— none —</option>
        {views.map((v) => (
          <option key={v.name} value={v.name}>
            {v.name}
          </option>
        ))}
      </select>
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
      {selected && (
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
