import { Box, Flex, Grid, Table, Text } from '@chakra-ui/react';
import { useMemo, useState } from 'react';

import { useChannelMetrics, useMasks, useSpectrum, useSpurs } from '../api/queries';
import { findMaskViolations } from '../lib/mask';
import { formatEng } from '../lib/measurement';
import { SpectrumPlot } from './SpectrumPlot';

const CHANNEL_COLOR = '#34d399';
const ADJACENT_COLOR = '#fbbf24';

function NumField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <Box>
      <Text
        fontSize="10px"
        textTransform="uppercase"
        letterSpacing="1px"
        color="var(--prism-text-faint)"
      >
        {label}
      </Text>
      <input
        className="chakra-input"
        value={value}
        inputMode="decimal"
        onChange={(e) => onChange(e.target.value)}
        style={{
          width: '100%',
          padding: '2px 6px',
          borderRadius: 4,
          borderWidth: 1,
          fontFamily: 'monospace',
          fontSize: 13,
        }}
      />
    </Box>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <Box>
      <Text
        fontSize="10px"
        textTransform="uppercase"
        letterSpacing="1px"
        color="var(--prism-text-faint)"
      >
        {label}
      </Text>
      <Text fontFamily="mono" color="var(--prism-text)">
        {value}
      </Text>
    </Box>
  );
}

export function SpectrumAnalysis({
  artifactId,
  projectSlug,
}: {
  artifactId: string;
  projectSlug?: string;
}) {
  const spec = useSpectrum(artifactId);
  const masksQuery = useMasks(projectSlug);
  const [maskId, setMaskId] = useState<string | null>(null);
  const selectedMask = masksQuery.data?.find((m) => m.id === maskId) ?? null;

  // Sensible defaults from the spectrum's metadata / extent.
  const defaults = useMemo(() => {
    const meta = spec.data?.metadata ?? {};
    const freqs = spec.data?.frequencies ?? [];
    const center =
      typeof meta.center === 'number'
        ? meta.center
        : freqs.length
          ? (freqs[0] + freqs[freqs.length - 1]) / 2
          : 0;
    const span =
      typeof meta.span === 'number'
        ? meta.span
        : freqs.length
          ? freqs[freqs.length - 1] - freqs[0]
          : 0;
    return { center, channelBw: span / 10, offset: span / 5, adjacentBw: span / 10 };
  }, [spec.data]);

  const [center, setCenter] = useState('');
  const [channelBw, setChannelBw] = useState('');
  const [offset, setOffset] = useState('');
  const [adjacentBw, setAdjacentBw] = useState('');
  const [showSpurs, setShowSpurs] = useState(false);

  const num = (s: string, fallback: number) => {
    const v = parseFloat(s);
    return Number.isFinite(v) ? v : fallback;
  };
  const c = num(center, defaults.center);
  const cbw = num(channelBw, defaults.channelBw);
  const off = num(offset, defaults.offset);
  const abw = num(adjacentBw, defaults.adjacentBw);

  const metricsParams =
    cbw > 0
      ? {
          center: c,
          channel_bw: cbw,
          offset: off > 0 ? off : undefined,
          adjacent_bw: abw > 0 ? abw : undefined,
        }
      : null;
  const metrics = useChannelMetrics(artifactId, metricsParams);
  const spurs = useSpurs(artifactId, 20, showSpurs);

  const bands = useMemo(() => {
    const m = metrics.data;
    if (!m) return [];
    const out = [{ lo: m.channel_band[0], hi: m.channel_band[1], color: CHANNEL_COLOR }];
    if (m.lower_band) out.push({ lo: m.lower_band[0], hi: m.lower_band[1], color: ADJACENT_COLOR });
    if (m.upper_band) out.push({ lo: m.upper_band[0], hi: m.upper_band[1], color: ADJACENT_COLOR });
    return out;
  }, [metrics.data]);

  const unit = spec.data?.unit ?? 'dBm';
  const fmtP = (v: number | null) => (v === null ? '—' : formatEng(v, unit));
  const fmtDbc = (v: number | null) => (v === null ? '—' : `${v.toFixed(1)} dBc`);

  const violationCount = useMemo(() => {
    if (!selectedMask || !spec.data) return 0;
    return findMaskViolations(spec.data.frequencies, spec.data.powers, selectedMask.segments)
      .length;
  }, [selectedMask, spec.data]);

  return (
    <Box>
      <SpectrumPlot
        artifactId={artifactId}
        bands={bands}
        markers={showSpurs ? (spurs.data?.spurs ?? []) : []}
        maskSegments={selectedMask?.segments}
      />
      {projectSlug && masksQuery.data && masksQuery.data.length > 0 && (
        <Flex gap={2} mt={2} align="center" wrap="wrap">
          <Text fontSize="xs" color="var(--prism-text-faint)">
            Mask:
          </Text>
          <Box
            as="button"
            onClick={() => setMaskId(null)}
            px={2}
            py="2px"
            borderRadius="sm"
            borderWidth={1}
            fontSize="xs"
            cursor="pointer"
            bg={maskId === null ? 'var(--prism-sidebar-active-bg)' : 'var(--prism-bg-surface)'}
            color={maskId === null ? 'var(--prism-sidebar-active-fg)' : 'var(--prism-text-muted)'}
            borderColor="var(--prism-border)"
          >
            none
          </Box>
          {masksQuery.data.map((m) => (
            <Box
              as="button"
              key={m.id}
              onClick={() => setMaskId(m.id)}
              px={2}
              py="2px"
              borderRadius="sm"
              borderWidth={1}
              fontSize="xs"
              cursor="pointer"
              bg={maskId === m.id ? 'var(--prism-sidebar-active-bg)' : 'var(--prism-bg-surface)'}
              color={maskId === m.id ? 'var(--prism-sidebar-active-fg)' : 'var(--prism-text-muted)'}
              borderColor="var(--prism-border)"
            >
              {m.name}
            </Box>
          ))}
          {selectedMask && (
            <Text
              fontSize="xs"
              fontFamily="mono"
              color={
                violationCount === 0 ? 'var(--prism-status-pass-fg)' : 'var(--prism-status-fail-fg)'
              }
            >
              {violationCount === 0
                ? '✓ within mask'
                : `✕ ${violationCount} point${violationCount === 1 ? '' : 's'} over mask`}
            </Text>
          )}
        </Flex>
      )}
      <Grid templateColumns="repeat(4, 1fr)" gap={2} mt={2}>
        <NumField label="Center (Hz)" value={center} onChange={setCenter} />
        <NumField label="Channel BW (Hz)" value={channelBw} onChange={setChannelBw} />
        <NumField label="ACPR offset (Hz)" value={offset} onChange={setOffset} />
        <NumField label="Adjacent BW (Hz)" value={adjacentBw} onChange={setAdjacentBw} />
      </Grid>
      <Flex gap={6} mt={3} wrap="wrap" align="center">
        <Stat label="Channel power" value={fmtP(metrics.data?.channel_power_dbm ?? null)} />
        <Stat label="ACPR lower" value={fmtDbc(metrics.data?.acpr_lower_dbc ?? null)} />
        <Stat label="ACPR upper" value={fmtDbc(metrics.data?.acpr_upper_dbc ?? null)} />
        <Stat
          label="OBW"
          value={metrics.data?.obw_hz != null ? formatEng(metrics.data.obw_hz, 'Hz') : '—'}
        />
        <Box
          as="button"
          onClick={() => setShowSpurs((s) => !s)}
          px={3}
          py={1}
          mt={3}
          borderRadius="md"
          borderWidth={1}
          fontSize="sm"
          cursor="pointer"
          bg={showSpurs ? 'var(--prism-sidebar-active-bg)' : 'var(--prism-bg-surface)'}
          color={showSpurs ? 'var(--prism-sidebar-active-fg)' : 'var(--prism-text-muted)'}
          borderColor="var(--prism-border)"
        >
          {showSpurs ? '✓ spurs' : 'detect spurs'}
        </Box>
      </Flex>
      {showSpurs && spurs.data && (
        <Box mt={3}>
          <Text fontSize="xs" color="var(--prism-text-faint)" mb={1}>
            {spurs.data.spurs.length} spur{spurs.data.spurs.length === 1 ? '' : 's'} ≥{' '}
            {spurs.data.margin_db} dB above a {formatEng(spurs.data.noise_floor_dbm, unit)} floor
          </Text>
          {spurs.data.spurs.length > 0 && (
            <Table.Root variant="outline" size="sm">
              <Table.Header>
                <Table.Row>
                  <Table.ColumnHeader>#</Table.ColumnHeader>
                  <Table.ColumnHeader textAlign="end">Frequency</Table.ColumnHeader>
                  <Table.ColumnHeader textAlign="end">Power</Table.ColumnHeader>
                  <Table.ColumnHeader textAlign="end">Above floor</Table.ColumnHeader>
                </Table.Row>
              </Table.Header>
              <Table.Body>
                {spurs.data.spurs.map((s, i) => (
                  <Table.Row key={`${s.frequency}:${s.power}`}>
                    <Table.Cell color="var(--prism-text-faint)">{i + 1}</Table.Cell>
                    <Table.Cell textAlign="end" fontFamily="mono">
                      {formatEng(s.frequency, 'Hz')}
                    </Table.Cell>
                    <Table.Cell textAlign="end" fontFamily="mono">
                      {formatEng(s.power, unit)}
                    </Table.Cell>
                    <Table.Cell textAlign="end" fontFamily="mono" color="var(--prism-text-muted)">
                      +{(s.power - spurs.data!.noise_floor_dbm).toFixed(1)} dB
                    </Table.Cell>
                  </Table.Row>
                ))}
              </Table.Body>
            </Table.Root>
          )}
        </Box>
      )}
    </Box>
  );
}
