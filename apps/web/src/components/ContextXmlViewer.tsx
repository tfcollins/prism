// apps/web/src/components/ContextXmlViewer.tsx
//
// Viewer for libiio context XML artifacts. A collapsible section (one accordion
// item per context artifact) that lazily fetches the raw XML on expand and lets
// the user drill into a device → channel → attribute tree, view the raw source,
// and download it. Used both in the test case view and at the run level.
import { Accordion, Box, Button, Flex, Text } from '@chakra-ui/react';
import { useMemo, useState } from 'react';

import { useArtifactRaw } from '../api/queries';
import { type CtxAttr, type CtxChannel, type CtxDevice, parseContext } from '../lib/iioContext';

type ContextArtifact = { id: string; kind: string; filename: string };

function AttrList({ attrs }: { attrs: CtxAttr[] }) {
  if (attrs.length === 0) return null;
  return (
    <Box pl={2}>
      {attrs.map((a) => (
        <Text key={a.name} fontFamily="mono" fontSize="xs" color="var(--prism-text-muted)">
          {a.name} = {a.value}
        </Text>
      ))}
    </Box>
  );
}

function TreeButton({
  open,
  label,
  onClick,
}: {
  open: boolean;
  label: string;
  onClick: () => void;
}) {
  return (
    <Button
      size="xs"
      variant="ghost"
      justifyContent="flex-start"
      w="full"
      fontFamily="mono"
      onClick={onClick}
    >
      {open ? '▾' : '▸'} {label}
    </Button>
  );
}

function ChannelNode({ channel }: { channel: CtxChannel }) {
  const [open, setOpen] = useState(false);
  const label = `${channel.id} · ${channel.type}${channel.name ? ` (${channel.name})` : ''}`;
  return (
    <Box>
      <TreeButton open={open} label={label} onClick={() => setOpen((o) => !o)} />
      {open && (
        <Box pl={4}>
          {channel.attributes.length === 0 ? (
            <Text pl={2} fontSize="xs" color="var(--prism-text-faint)">
              no attributes
            </Text>
          ) : (
            <AttrList attrs={channel.attributes} />
          )}
        </Box>
      )}
    </Box>
  );
}

function DeviceNode({ device }: { device: CtxDevice }) {
  const [open, setOpen] = useState(false);
  const title = device.name ? `${device.name} (${device.id})` : device.id;
  const label = `${title} · ${device.channels.length} ch`;
  return (
    <Box>
      <TreeButton open={open} label={label} onClick={() => setOpen((o) => !o)} />
      {open && (
        <Box pl={4}>
          <AttrList attrs={device.attributes} />
          {device.channels.map((c) => (
            <ChannelNode key={c.id} channel={c} />
          ))}
        </Box>
      )}
    </Box>
  );
}

/**
 * The body of one context artifact: a Tree / Raw toggle, the rendered content,
 * and a download link. `open` gates the raw fetch. Exported for unit testing.
 */
export function ContextXmlBody({
  artifactId,
  filename,
  open,
}: {
  artifactId: string;
  filename: string;
  open: boolean;
}) {
  const [view, setView] = useState<'tree' | 'raw'>('tree');
  const raw = useArtifactRaw(artifactId, open);
  const parsed = useMemo(() => (raw.data ? parseContext(raw.data) : null), [raw.data]);

  const download = (
    <a
      href={`/api/v1/artifacts/${artifactId}/raw`}
      download={filename}
      style={{ color: 'var(--prism-link)', fontSize: '0.75rem' }}
    >
      Download
    </a>
  );

  let content;
  if (raw.isLoading) {
    content = <Text fontSize="xs">Loading context…</Text>;
  } else if (raw.isError || raw.data == null) {
    content = (
      <Text fontSize="xs" color="var(--prism-status-fail-fg)">
        Failed to load context.
      </Text>
    );
  } else if (view === 'raw' || !parsed) {
    content = (
      <Box>
        {!parsed && (
          <Text fontSize="xs" color="var(--prism-text-faint)" mb={1}>
            Not a recognized libiio context — showing raw XML.
          </Text>
        )}
        <Box
          maxH="360px"
          overflow="auto"
          fontFamily="mono"
          fontSize="xs"
          whiteSpace="pre"
          bg="var(--prism-bg-canvas)"
          borderWidth={1}
          borderColor="var(--prism-border)"
          borderRadius="sm"
          p={2}
        >
          {raw.data}
        </Box>
      </Box>
    );
  } else {
    content = (
      <Box>
        {(parsed.name || parsed.description) && (
          <Text fontSize="xs" color="var(--prism-text-subtle)" mb={1}>
            {parsed.name}
            {parsed.description ? ` — ${parsed.description}` : ''} · {parsed.devices.length} device
            {parsed.devices.length === 1 ? '' : 's'}
          </Text>
        )}
        <AttrList attrs={parsed.contextAttributes} />
        {parsed.devices.map((d) => (
          <DeviceNode key={d.id} device={d} />
        ))}
      </Box>
    );
  }

  return (
    <Box>
      <Flex align="center" justify="space-between" mb={2} gap={2}>
        <Flex gap={1}>
          <Button
            size="xs"
            variant={view === 'tree' ? 'solid' : 'outline'}
            colorPalette={view === 'tree' ? 'blue' : 'gray'}
            onClick={() => setView('tree')}
          >
            Tree
          </Button>
          <Button
            size="xs"
            variant={view === 'raw' ? 'solid' : 'outline'}
            colorPalette={view === 'raw' ? 'blue' : 'gray'}
            onClick={() => setView('raw')}
          >
            Raw
          </Button>
        </Flex>
        {download}
      </Flex>
      {content}
    </Box>
  );
}

/**
 * Collapsible "Context" section listing every libiio context XML artifact in the
 * given set (run-scoped or case-scoped). Renders nothing when there are none.
 */
export function ContextSection({ artifacts }: { artifacts: ReadonlyArray<ContextArtifact> }) {
  const contexts = artifacts.filter((a) => a.kind === 'iio_context_xml');
  const [open, setOpen] = useState<string[]>([]);
  if (contexts.length === 0) return null;

  return (
    <Box mb={6}>
      <Text
        fontSize="10px"
        textTransform="uppercase"
        letterSpacing="1px"
        color="var(--prism-text-faint)"
        mb={1}
      >
        Context
      </Text>
      <Accordion.Root
        multiple
        value={open}
        onValueChange={(e) => setOpen(e.value)}
        variant="outline"
      >
        {contexts.map((a, i) => {
          const value = String(i);
          return (
            <Accordion.Item key={a.id} value={value}>
              <Accordion.ItemTrigger>
                <Flex flex="1" textAlign="left">
                  <Text fontFamily="mono" fontSize="sm">
                    {a.filename}
                  </Text>
                </Flex>
                <Accordion.ItemIndicator />
              </Accordion.ItemTrigger>
              <Accordion.ItemContent>
                <Accordion.ItemBody>
                  <ContextXmlBody
                    artifactId={a.id}
                    filename={a.filename}
                    open={open.includes(value)}
                  />
                </Accordion.ItemBody>
              </Accordion.ItemContent>
            </Accordion.Item>
          );
        })}
      </Accordion.Root>
    </Box>
  );
}
