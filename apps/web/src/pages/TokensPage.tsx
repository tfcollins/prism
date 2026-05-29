import { Box, Button, Heading, Input, Stack, Table, Text } from '@chakra-ui/react';
import { useState } from 'react';

import { useCreateToken, useRevokeToken, useTokens } from '../api/queries';
import type { TokenCreated } from '../api/types';
import { AppShell } from '../components/AppShell';
import { CopyButton } from '../components/CopyButton';

function fmt(iso: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString();
}

export function TokensPage() {
  const tokens = useTokens();
  const create = useCreateToken();
  const revoke = useRevokeToken();

  const [name, setName] = useState('');
  const [days, setDays] = useState('');
  const [justCreated, setJustCreated] = useState<TokenCreated | null>(null);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    create.mutate(
      { name: name.trim(), expires_in_days: days ? Number(days) : null },
      {
        onSuccess: (t) => {
          setJustCreated(t);
          setName('');
          setDays('');
        },
      },
    );
  };

  return (
    <AppShell>
      <Box p={8} maxW="900px">
        <Heading size="xl" mb={2}>
          API tokens
        </Heading>
        <Text color="var(--prism-text-subtle)" mb={6} fontSize="sm">
          Tokens authenticate scripts and CI with an <code>Authorization: Bearer</code> header — use
          one instead of your password in <code>upload_run.py</code> / <code>pytest-prism</code>.
        </Text>

        <Stack as="form" direction={{ base: 'column', sm: 'row' }} gap={2} mb={4} onSubmit={submit}>
          <Input
            placeholder="Token name (e.g. ci-nightly)"
            aria-label="Token name"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <Input
            placeholder="Expires in days (optional)"
            aria-label="Expires in days"
            type="number"
            min={1}
            max={3650}
            value={days}
            onChange={(e) => setDays(e.target.value)}
            maxW={{ base: 'full', sm: '220px' }}
          />
          <Button type="submit" colorPalette="blue" loading={create.isPending}>
            Create token
          </Button>
        </Stack>
        {create.isError && (
          <Text color="red.400" mb={4} fontSize="sm">
            Could not create token.
          </Text>
        )}

        {justCreated && (
          <Box
            mb={6}
            p={4}
            borderWidth={1}
            borderColor="var(--prism-border)"
            borderRadius="md"
            bg="var(--prism-bg-surface)"
          >
            <Text fontSize="sm" mb={2}>
              Token <strong>{justCreated.name}</strong> created. Copy it now — it won't be shown
              again.
            </Text>
            <Stack direction="row" align="center" gap={2}>
              <Box
                as="code"
                flex="1"
                px={3}
                py={2}
                bg="black"
                borderRadius="6px"
                fontSize="13px"
                fontFamily="monospace"
                overflowX="auto"
                whiteSpace="nowrap"
              >
                {justCreated.token}
              </Box>
              <CopyButton value={justCreated.token} label="copy" />
            </Stack>
          </Box>
        )}

        <Heading size="md" mb={3}>
          Your tokens
        </Heading>
        {tokens.isLoading && <Text>Loading…</Text>}
        {tokens.data && tokens.data.length === 0 && (
          <Text color="var(--prism-text-subtle)">No tokens yet.</Text>
        )}
        {tokens.data && tokens.data.length > 0 && (
          <Table.Root variant="outline" size="sm">
            <Table.Header>
              <Table.Row>
                <Table.ColumnHeader>Name</Table.ColumnHeader>
                <Table.ColumnHeader>Prefix</Table.ColumnHeader>
                <Table.ColumnHeader>Created</Table.ColumnHeader>
                <Table.ColumnHeader>Last used</Table.ColumnHeader>
                <Table.ColumnHeader>Expires</Table.ColumnHeader>
                <Table.ColumnHeader></Table.ColumnHeader>
              </Table.Row>
            </Table.Header>
            <Table.Body>
              {tokens.data.map((t) => (
                <Table.Row key={t.id}>
                  <Table.Cell>{t.name}</Table.Cell>
                  <Table.Cell>
                    <Text as="code" fontFamily="monospace" fontSize="xs">
                      {t.prefix}…
                    </Text>
                  </Table.Cell>
                  <Table.Cell>{fmt(t.created_at)}</Table.Cell>
                  <Table.Cell>{fmt(t.last_used_at)}</Table.Cell>
                  <Table.Cell>{fmt(t.expires_at)}</Table.Cell>
                  <Table.Cell>
                    <Button
                      size="xs"
                      variant="outline"
                      colorPalette="red"
                      loading={revoke.isPending}
                      onClick={() => revoke.mutate(t.id)}
                    >
                      Revoke
                    </Button>
                  </Table.Cell>
                </Table.Row>
              ))}
            </Table.Body>
          </Table.Root>
        )}
      </Box>
    </AppShell>
  );
}
