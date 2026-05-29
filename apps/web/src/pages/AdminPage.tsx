import { Badge, Box, Heading, Stack, Table, Tabs, Text } from '@chakra-ui/react';
import { useState } from 'react';

import { useAdminAccounts, useAdminActivity, useAdminBackups, useAdminLogs } from '../api/queries';
import { AppShell } from '../components/AppShell';

const LOG_SERVICES = ['api', 'worker', 'web', 'postgres', 'redis', 'minio'];

function fmtBytes(n: number | null): string {
  if (n === null || n === undefined) return '—';
  if (n < 1024) return `${n} B`;
  const units = ['KB', 'MB', 'GB', 'TB'];
  let v = n / 1024;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i += 1;
  }
  return `${v.toFixed(1)} ${units[i]}`;
}

function fmtTime(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString();
}

function StatusBadge({ value }: { value: string }) {
  const palette = value === 'ok' || value === 'pushed' ? 'green' : value === 'error' ? 'red' : 'gray';
  return (
    <Badge colorPalette={palette} variant="subtle">
      {value}
    </Badge>
  );
}

function AccountsTab() {
  const q = useAdminAccounts();
  if (q.isLoading) return <Text>Loading…</Text>;
  if (q.isError) return <Text color="red.400">Failed to load accounts.</Text>;
  return (
    <Table.Root variant="outline">
      <Table.Header>
        <Table.Row>
          <Table.ColumnHeader>Email</Table.ColumnHeader>
          <Table.ColumnHeader>Auth</Table.ColumnHeader>
          <Table.ColumnHeader>Role</Table.ColumnHeader>
          <Table.ColumnHeader>Created</Table.ColumnHeader>
        </Table.Row>
      </Table.Header>
      <Table.Body>
        {q.data?.map((a) => (
          <Table.Row key={a.id}>
            <Table.Cell>{a.email}</Table.Cell>
            <Table.Cell>
              <Badge variant="subtle" colorPalette={a.auth_provider === 'ldap' ? 'purple' : 'blue'}>
                {a.auth_provider}
              </Badge>
            </Table.Cell>
            <Table.Cell>{a.is_admin ? <Badge colorPalette="orange">admin</Badge> : '—'}</Table.Cell>
            <Table.Cell>{fmtTime(a.created_at)}</Table.Cell>
          </Table.Row>
        ))}
      </Table.Body>
    </Table.Root>
  );
}

function BackupsTab() {
  const q = useAdminBackups();
  if (q.isLoading) return <Text>Loading…</Text>;
  if (q.isError) return <Text color="red.400">Failed to load backups.</Text>;
  if (!q.data || q.data.length === 0)
    return <Text color="var(--prism-text-subtle)">No backups recorded yet.</Text>;
  return (
    <Table.Root variant="outline">
      <Table.Header>
        <Table.Row>
          <Table.ColumnHeader>When (UTC)</Table.ColumnHeader>
          <Table.ColumnHeader>Status</Table.ColumnHeader>
          <Table.ColumnHeader>Postgres</Table.ColumnHeader>
          <Table.ColumnHeader>MinIO</Table.ColumnHeader>
          <Table.ColumnHeader>Cloudsmith</Table.ColumnHeader>
        </Table.Row>
      </Table.Header>
      <Table.Body>
        {q.data.map((b) => (
          <Table.Row key={b.timestamp}>
            <Table.Cell>{b.timestamp}</Table.Cell>
            <Table.Cell>
              <StatusBadge value={b.status} />
            </Table.Cell>
            <Table.Cell>{fmtBytes(b.postgres_bytes)}</Table.Cell>
            <Table.Cell>{b.minio_included ? fmtBytes(b.minio_bytes) : 'excluded'}</Table.Cell>
            <Table.Cell>
              <StatusBadge value={b.cloudsmith} />
            </Table.Cell>
          </Table.Row>
        ))}
      </Table.Body>
    </Table.Root>
  );
}

function ActivityTab() {
  const q = useAdminActivity();
  if (q.isLoading) return <Text>Loading…</Text>;
  if (q.isError) return <Text color="red.400">Failed to load activity.</Text>;
  if (!q.data || q.data.length === 0)
    return <Text color="var(--prism-text-subtle)">No activity recorded yet.</Text>;
  return (
    <Table.Root variant="outline">
      <Table.Header>
        <Table.Row>
          <Table.ColumnHeader>When</Table.ColumnHeader>
          <Table.ColumnHeader>Action</Table.ColumnHeader>
          <Table.ColumnHeader>Actor</Table.ColumnHeader>
          <Table.ColumnHeader>Target</Table.ColumnHeader>
        </Table.Row>
      </Table.Header>
      <Table.Body>
        {q.data.map((e, i) => (
          <Table.Row key={`${e.created_at}-${i}`}>
            <Table.Cell>{fmtTime(e.created_at)}</Table.Cell>
            <Table.Cell>
              <Badge variant="subtle">{e.action}</Badge>
            </Table.Cell>
            <Table.Cell>{e.user_email ?? '—'}</Table.Cell>
            <Table.Cell>{e.target_type ? `${e.target_type}:${e.target_id ?? ''}` : '—'}</Table.Cell>
          </Table.Row>
        ))}
      </Table.Body>
    </Table.Root>
  );
}

function LogsTab() {
  const [service, setService] = useState('api');
  const q = useAdminLogs(service);
  return (
    <Stack gap={3}>
      <Stack direction="row" gap={2} wrap="wrap">
        {LOG_SERVICES.map((s) => (
          <Badge
            key={s}
            as="button"
            onClick={() => setService(s)}
            colorPalette={s === service ? 'blue' : 'gray'}
            variant={s === service ? 'solid' : 'subtle'}
            cursor="pointer"
            px={3}
            py={1}
          >
            {s}
          </Badge>
        ))}
      </Stack>
      {q.isLoading && <Text>Loading…</Text>}
      {q.data && !q.data.available && (
        <Text color="var(--prism-text-subtle)">{q.data.message ?? 'Logs unavailable.'}</Text>
      )}
      {q.data?.available && (
        <Box
          as="pre"
          bg="black"
          color="var(--prism-text-subtle)"
          p={3}
          borderRadius="6px"
          fontSize="12px"
          fontFamily="monospace"
          overflowX="auto"
          maxH="60vh"
          overflowY="auto"
          whiteSpace="pre-wrap"
        >
          {q.data.lines.length ? q.data.lines.join('\n') : '(no log output)'}
        </Box>
      )}
    </Stack>
  );
}

export function AdminPage() {
  return (
    <AppShell>
      <Box p={8}>
        <Heading size="xl" mb={6}>
          Admin
        </Heading>
        <Tabs.Root defaultValue="accounts">
          <Tabs.List>
            <Tabs.Trigger value="accounts">Accounts</Tabs.Trigger>
            <Tabs.Trigger value="backups">Backups</Tabs.Trigger>
            <Tabs.Trigger value="activity">Activity</Tabs.Trigger>
            <Tabs.Trigger value="logs">Container logs</Tabs.Trigger>
          </Tabs.List>
          <Tabs.Content value="accounts">
            <AccountsTab />
          </Tabs.Content>
          <Tabs.Content value="backups">
            <BackupsTab />
          </Tabs.Content>
          <Tabs.Content value="activity">
            <ActivityTab />
          </Tabs.Content>
          <Tabs.Content value="logs">
            <LogsTab />
          </Tabs.Content>
        </Tabs.Root>
      </Box>
    </AppShell>
  );
}
