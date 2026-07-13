import { Badge, Box, Flex, Grid, Heading, Stack, Tabs, Text } from '@chakra-ui/react';
import { useEffect, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';

import { useCase, useRun, useRunArtifacts, useRuns, useSetCalibration } from '../api/queries';
import type { RunDetail } from '../api/types';
import { AppShell } from '../components/AppShell';
import { BootLogViewer, TerminalLogViewer } from '../components/BootLogViewer';
import { BootPanel } from '../components/BootPanel';
import { ContextSection } from '../components/ContextXmlViewer';

import { CopyButton } from '../components/CopyButton';
import { FFTPlot } from '../components/FFTPlot';
import { InlinePlotlyFigure } from '../components/InlinePlotlyFigure';
import { Logo } from '../components/Logo';
import { MeasurementsTable } from '../components/MeasurementsTable';
import { SpectrogramPlot } from '../components/SpectrogramPlot';
import { SpectrumAnalysis } from '../components/SpectrumAnalysis';
import { TagsEditor } from '../components/TagsEditor';
import { TestTree } from '../components/TestTree';
import { Toast } from '../components/Toast';
import { Tooltip } from '../components/Tooltip';
import { WaveformPlot } from '../components/WaveformPlot';
import { pickInlineArtifact } from '../lib/inlineKinds';
import { parseTestId } from '../lib/parseTestId';

export function RunDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null);

  const runQuery = useRun(id);
  const runArtifactsQuery = useRunArtifacts(id);
  const caseQuery = useCase(selectedCaseId ?? undefined);
  const [rightOpen, setRightOpen] = useState(true);

  // Toast when ingest finishes: detect a pending → terminal transition.
  const prevStatus = useRef<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const status = runQuery.data?.status;
  useEffect(() => {
    if (!status) return;
    if (prevStatus.current === 'pending' && status !== 'pending') {
      const d = runQuery.data;
      const summary = d
        ? `${d.suites.reduce((a, s) => a + s.pass_count, 0)} pass, ${d.suites.reduce((a, s) => a + s.fail_count, 0)} fail`
        : '';
      setToast(`Ingest complete: ${status}${summary ? ` — ${summary}` : ''}`);
    }
    prevStatus.current = status;
  }, [status, runQuery.data]);

  const waveform = caseQuery.data?.artifacts.find((a) => a.kind.startsWith('waveform'));
  const spectrogram = caseQuery.data?.artifacts.find((a) => a.kind === 'spectrogram');
  const spectrum = caseQuery.data?.artifacts.find(
    (a) => a.kind.startsWith('spectrum') && a.kind !== 'spectrogram',
  );
  // Plotly figure JSON: render inline via react-plotly. Match by filename
  // since `kind` for *.json comes through as log_text from the detector.
  const figureJson = caseQuery.data?.artifacts.find(
    (a) =>
      a.filename.toLowerCase().endsWith('.json') && a.filename.toLowerCase().includes('spectrum'),
  );
  const inlineArtifact = pickInlineArtifact(caseQuery.data?.artifacts ?? []);
  const otherArtifacts = (caseQuery.data?.artifacts ?? []).filter(
    (a) =>
      a !== waveform &&
      a !== figureJson &&
      a !== inlineArtifact &&
      a !== spectrum &&
      a !== spectrogram &&
      a.kind !== 'iio_context_xml',
  );

  return (
    <AppShell>
      {toast && <Toast message={toast} onClose={() => setToast(null)} />}
      {runQuery.isLoading && <Text>Loading run…</Text>}
      {runQuery.isError && <Text color="red.400">Failed to load run</Text>}
      {runQuery.data && (
        <Box>
          <Flex align="center" justify="space-between" mb={3} gap={2}>
            <Heading size="lg">{runQuery.data.name}</Heading>
            <Tooltip content="Show or hide the run details panel (status, tags, calibration, report).">
              <Box
                as="button"
                onClick={() => setRightOpen((o) => !o)}
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
                {rightOpen ? 'hide details ›' : '‹ show details'}
              </Box>
            </Tooltip>
          </Flex>

          {runArtifactsQuery.data && runArtifactsQuery.data.length > 0 && (
            <RunFilesSection artifacts={runArtifactsQuery.data} />
          )}
          <BootLogViewer runId={runQuery.data.id} />
          <TerminalLogViewer runId={runQuery.data.id} />
          {runArtifactsQuery.data && <ContextSection artifacts={runArtifactsQuery.data} />}

          <Grid
            templateColumns={{
              base: '1fr',
              md: '220px 1fr',
              lg: rightOpen ? '240px 1fr 280px' : '240px 1fr',
            }}
            gap={4}
            minH={{ base: 'auto', md: '500px' }}
          >
            <Box
              borderWidth={1}
              borderColor="var(--prism-border)"
              borderRadius="lg"
              p={3}
              bg="var(--prism-bg-surface)"
              boxShadow="var(--prism-shadow-card)"
              overflowY="auto"
            >
              {runQuery.data.suites.length === 1 && (
                <Flex
                  align="center"
                  gap={2}
                  mb={2}
                  pb={2}
                  borderBottomWidth={1}
                  borderColor="var(--prism-border)"
                >
                  <Text
                    fontSize="10px"
                    textTransform="uppercase"
                    letterSpacing="1px"
                    color="var(--prism-text-faint)"
                  >
                    Suite
                  </Text>
                  <Badge variant="subtle" colorPalette="blue">
                    {runQuery.data.suites[0].name}
                  </Badge>
                </Flex>
              )}
              <TestTree
                suites={runQuery.data.suites}
                selectedCaseId={selectedCaseId}
                onSelectCase={setSelectedCaseId}
                flatten={runQuery.data.suites.length === 1}
              />
            </Box>
            <Box
              borderWidth={1}
              borderColor="var(--prism-border)"
              borderRadius="lg"
              p={3}
              bg="var(--prism-bg-surface)"
              boxShadow="var(--prism-shadow-card)"
            >
              {!selectedCaseId && (
                <Flex
                  direction="column"
                  align="center"
                  justify="center"
                  minH={{ base: '180px', md: '440px' }}
                  gap={3}
                  textAlign="center"
                >
                  <Logo size="md" showWordmark={false} />
                  <Text color="var(--prism-text-subtle)" fontSize="sm">
                    Select a case from the tree to inspect
                  </Text>
                  <Text
                    fontFamily="var(--prism-font-mono)"
                    fontSize="11px"
                    color="var(--prism-text-faint)"
                    letterSpacing="0.06em"
                  >
                    measurements · waveforms · spectra
                  </Text>
                </Flex>
              )}
              {selectedCaseId && caseQuery.isLoading && <Text>Loading case…</Text>}
              {caseQuery.data && (
                <Stack gap={3}>
                  <CaseHeader caseData={caseQuery.data} />
                  <MeasurementsTable measurements={caseQuery.data.measurements} />
                  <CaseParamsTable name={caseQuery.data.name} />
                  {caseQuery.data.failure_message && (
                    <Box
                      bg="var(--prism-danger-bg)"
                      p={2}
                      borderRadius="md"
                      color="var(--prism-danger-fg)"
                      fontSize="sm"
                    >
                      {caseQuery.data.failure_message}
                    </Box>
                  )}
                  {inlineArtifact && (
                    <iframe
                      src={`/api/v1/artifacts/${inlineArtifact.id}/raw`}
                      title={inlineArtifact.filename}
                      style={{ width: '100%', height: 600, border: 0 }}
                    />
                  )}
                  {figureJson && <InlinePlotlyFigure artifactId={figureJson.id} />}
                  {spectrum && (
                    <SpectrumAnalysis
                      artifactId={spectrum.id}
                      projectSlug={runQuery.data.project_slug ?? undefined}
                    />
                  )}
                  {spectrogram && <SpectrogramPlot artifactId={spectrogram.id} />}
                  {waveform ? (
                    <Tabs.Root defaultValue="time">
                      <Tabs.List>
                        <Tabs.Trigger value="time">Time domain</Tabs.Trigger>
                        <Tabs.Trigger value="fft">FFT</Tabs.Trigger>
                      </Tabs.List>
                      <Tabs.Content value="time">
                        <WaveformPlot artifactId={waveform.id} />
                      </Tabs.Content>
                      <Tabs.Content value="fft">
                        <FFTPlot artifactId={waveform.id} />
                      </Tabs.Content>
                    </Tabs.Root>
                  ) : (
                    !figureJson &&
                    !spectrum &&
                    !spectrogram &&
                    !inlineArtifact && (
                      <Text color="var(--prism-text-subtle)" fontSize="sm">
                        No plottable artifact attached to this case.
                      </Text>
                    )
                  )}
                  {caseQuery.data && <ContextSection artifacts={caseQuery.data.artifacts} />}
                  {otherArtifacts.length > 0 && (
                    <Box>
                      <Text
                        fontSize="10px"
                        textTransform="uppercase"
                        letterSpacing="1px"
                        color="var(--prism-text-faint)"
                        mt={2}
                        mb={1}
                      >
                        Attached files
                      </Text>
                      <Stack gap={1}>
                        {otherArtifacts.map((a) => (
                          <Flex key={a.id} align="center" gap={2} fontSize="sm">
                            <a
                              href={`/api/v1/artifacts/${a.id}/raw`}
                              target="_blank"
                              rel="noreferrer"
                              style={{ color: 'var(--prism-link)' }}
                            >
                              {a.filename}
                            </a>
                            <Text fontSize="xs" color="var(--prism-text-faint)">
                              ({a.kind} · {Math.round(a.size_bytes / 1024)} KB)
                            </Text>
                          </Flex>
                        ))}
                      </Stack>
                    </Box>
                  )}
                </Stack>
              )}
            </Box>
            {rightOpen && <RunMetaPane run={runQuery.data} />}
          </Grid>
        </Box>
      )}
    </AppShell>
  );
}

const STATUS_PALETTE: Record<string, string> = {
  pass: 'green',
  fail: 'red',
  error: 'red',
  mixed: 'orange',
  pending: 'gray',
};

const STATUS_HELP: Record<string, string> = {
  pass: 'All test cases passed.',
  fail: 'One or more test cases failed.',
  mixed: 'A mix of passing and failing cases.',
  error: 'The run errored during execution or ingest.',
  pending: 'Ingest is still in progress.',
};

function RunMetaPane({ run }: { run: RunDetail }) {
  const dut = run.tags.find((t) => ['device_serial', 'dut', 'serial', 'sn'].includes(t.key));
  const label = (text: string) => (
    <Text
      fontSize="10px"
      textTransform="uppercase"
      letterSpacing="1px"
      color="var(--prism-text-faint)"
      mt={3}
      mb={1}
    >
      {text}
    </Text>
  );
  return (
    <Box
      borderWidth={1}
      borderColor="var(--prism-border)"
      borderRadius="lg"
      p={3}
      bg="var(--prism-bg-surface)"
      boxShadow="var(--prism-shadow-card)"
      overflowY="auto"
    >
      {label('Status')}
      <Tooltip content={STATUS_HELP[run.status] ?? 'Overall run status.'}>
        <Badge colorPalette={STATUS_PALETTE[run.status] ?? 'gray'}>{run.status}</Badge>
      </Tooltip>

      {run.boot && (
        <Box mt={3}>
          <BootPanel boot={run.boot} />
        </Box>
      )}

      {label('Run ID')}
      <Flex align="center" gap={2}>
        <Text fontFamily="mono" fontSize="xs" color="var(--prism-text-muted)" truncate>
          {run.id}
        </Text>
        <CopyButton value={run.id} />
      </Flex>

      {dut && (
        <>
          {label('DUT')}
          <Text fontFamily="mono" fontSize="sm">
            {dut.value}
          </Text>
        </>
      )}

      {label('Tags')}
      <TagsEditor runId={run.id} tags={run.tags} />

      {label('Calibration')}
      <CalibrationControl run={run} />

      {label('Report')}
      <Tooltip content="Per-run compliance PDF: measurements, margins, pass/fail, and the source JUnit SHA.">
        <a
          href={`/api/v1/runs/${run.id}/report.pdf`}
          download={`${run.name}-report.pdf`}
          style={{ color: 'var(--prism-link)', fontSize: 13 }}
        >
          Download compliance PDF
        </a>
      </Tooltip>
    </Box>
  );
}

function CalibrationControl({ run }: { run: RunDetail }) {
  const runsQuery = useRuns(run.project_slug ?? undefined);
  const setCal = useSetCalibration(run.id);
  const candidates = (runsQuery.data ?? []).filter((r) => r.id !== run.id);

  return (
    <Flex align="center" gap={2} fontSize="sm">
      <Tooltip content="Link this run to a calibration run whose corrections apply to its measurements.">
        <select
          className="chakra-input"
          aria-label="Calibration run"
          value={run.calibration_run_id ?? ''}
          disabled={setCal.isPending}
          onChange={(e) => setCal.mutate(e.target.value === '' ? null : e.target.value)}
          style={{
            padding: '2px 6px',
            borderRadius: 4,
            borderWidth: 1,
            fontFamily: 'monospace',
            fontSize: 13,
            maxWidth: 240,
          }}
        >
          <option value="">— none —</option>
          {candidates.map((r) => (
            <option key={r.id} value={r.id}>
              {r.name}
            </option>
          ))}
        </select>
      </Tooltip>
    </Flex>
  );
}

function RunFilesSection({
  artifacts,
}: {
  artifacts: Array<{ id: string; filename: string; kind: string; size_bytes: number }>;
}) {
  // Filter out junit + manifest — those are housekeeping the UI already implies.
  const visible = artifacts.filter(
    (a) => a.filename !== 'junit.xml' && a.filename !== 'manifest.json',
  );
  if (visible.length === 0) return null;
  return (
    <Box mb={6}>
      <Text
        fontSize="10px"
        textTransform="uppercase"
        letterSpacing="1px"
        color="var(--prism-text-faint)"
        mb={1}
      >
        Run files
      </Text>
      <Box
        borderWidth={1}
        borderColor="var(--prism-border)"
        borderRadius="md"
        bg="var(--prism-bg-surface)"
        px={3}
        py={2}
      >
        <Stack gap={1}>
          {visible.map((a) => (
            <Flex key={a.id} align="center" gap={2} fontSize="sm">
              <a
                href={`/api/v1/artifacts/${a.id}/raw`}
                target="_blank"
                rel="noreferrer"
                style={{ color: 'var(--prism-link)' }}
              >
                {a.filename}
              </a>
              <Text fontSize="xs" color="var(--prism-text-faint)">
                ({a.kind} · {Math.round(a.size_bytes / 1024)} KB)
              </Text>
            </Flex>
          ))}
        </Stack>
      </Box>
    </Box>
  );
}

function CaseHeader({
  caseData,
}: {
  caseData: { name: string; classname: string; status: string; duration_ms: number };
}) {
  const { baseName, params } = parseTestId(caseData.name);
  const hasParams = params.length > 0;
  return (
    <Box>
      <Heading size="sm">{baseName}</Heading>
      <Text fontSize="xs" color="var(--prism-text-subtle)">
        {caseData.classname} · {caseData.status} · {caseData.duration_ms} ms
        {hasParams && ` · instance ${params.length} param${params.length === 1 ? '' : 's'}`}
      </Text>
    </Box>
  );
}

function CaseParamsTable({ name }: { name: string }) {
  const { params } = parseTestId(name);
  if (params.length === 0) return null;
  return (
    <Box>
      <Text
        fontSize="10px"
        textTransform="uppercase"
        letterSpacing="1px"
        color="var(--prism-text-faint)"
        mb={1}
      >
        Parameters
      </Text>
      <Box
        borderWidth={1}
        borderColor="var(--prism-border)"
        borderRadius="md"
        bg="var(--prism-bg-surface)"
        px={3}
        py={2}
      >
        <Stack gap={1}>
          {params.map((p) => (
            <Flex key={p.key} align="baseline" gap={3}>
              <Text
                fontSize="xs"
                color="var(--prism-text-subtle)"
                fontWeight="600"
                minW="120px"
                flexShrink={0}
              >
                {p.key}
              </Text>
              <Text
                as="code"
                fontSize="xs"
                color="var(--prism-text-muted)"
                wordBreak="break-all"
                whiteSpace="pre-wrap"
              >
                {p.value}
              </Text>
            </Flex>
          ))}
        </Stack>
      </Box>
    </Box>
  );
}
