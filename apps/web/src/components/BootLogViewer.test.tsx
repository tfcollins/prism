import { ChakraProvider } from '@chakra-ui/react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { system } from '../theme';

const RAW = [
  'Linux version 6.1.0-g1a2b3c4',
  '<4> spi-nor: flash warning',
  'ad9361 spi0.0: probe failed -110',
  '<3> mmc0: error reading sector',
  'Kernel panic - not syncing: oops',
].join('\n');

const queries = vi.hoisted(() => ({
  raw: { data: undefined as string | undefined, isLoading: false, isError: false },
  logs: { data: [] as (typeof REPORT)[], isLoading: false, isError: false },
  fetchRaw: vi.fn(),
}));
vi.mock('../api/queries', () => ({
  useRunLogs: () => queries.logs,
  useArtifactRaw: (id: string | null, enabled: boolean) => {
    queries.fetchRaw(id, enabled);
    return queries.raw;
  },
}));

import { BootLogBody, BootLogViewer, CapturedOutputViewer } from './BootLogViewer';

const REPORT = {
  source: 'boot.log',
  artifact_id: 'a1',
  kernel_version: null,
  board: null,
  kernel_commit: null,
  hdl_commit: null,
  kernel_commit_url: null,
  hdl_commit_url: null,
  error_count: 1,
  warn_count: 1,
  has_panic: true,
  findings: [],
};

function renderBody() {
  return render(
    <ChakraProvider value={system}>
      <BootLogBody report={REPORT} open={true} />
    </ChakraProvider>,
  );
}

beforeEach(() => {
  queries.raw = { data: RAW, isLoading: false, isError: false };
  queries.logs = { data: [], isLoading: false, isError: false };
  queries.fetchRaw.mockClear();
});

describe('BootLogBody', () => {
  it('shows every line under the All filter (default)', () => {
    renderBody();
    expect(screen.getByText('Linux version 6.1.0-g1a2b3c4')).toBeInTheDocument();
    expect(screen.getByText('Kernel panic - not syncing: oops')).toBeInTheDocument();
  });

  it('Errors filter shows only error/probe/panic lines', () => {
    renderBody();
    fireEvent.click(screen.getByRole('button', { name: /errors/i }));
    expect(screen.queryByText('Linux version 6.1.0-g1a2b3c4')).toBeNull();
    expect(screen.queryByText('<4> spi-nor: flash warning')).toBeNull();
    expect(screen.getByText('ad9361 spi0.0: probe failed -110')).toBeInTheDocument();
    expect(screen.getByText('<3> mmc0: error reading sector')).toBeInTheDocument();
    expect(screen.getByText('Kernel panic - not syncing: oops')).toBeInTheDocument();
  });

  it('Warnings filter shows only warn lines', () => {
    renderBody();
    fireEvent.click(screen.getByRole('button', { name: /warnings/i }));
    expect(screen.getByText('<4> spi-nor: flash warning')).toBeInTheDocument();
    expect(screen.queryByText('<3> mmc0: error reading sector')).toBeNull();
  });

  it('offers a download link to the raw artifact', () => {
    renderBody();
    const link = screen.getByRole('link', { name: /download/i });
    expect(link).toHaveAttribute('href', '/api/v1/artifacts/a1/raw');
    expect(link).toHaveAttribute('download', 'boot.log');
  });
});

describe('log access', () => {
  it('progressively reveals every line beyond the first batch and preserves full download', () => {
    queries.raw.data = Array.from({ length: 5002 }, (_, i) => `message ${i + 1}`).join('\n');
    renderBody();
    expect(screen.getByText('message 5000')).toBeInTheDocument();
    expect(screen.queryByText('message 5001')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: /show more lines/i }));
    expect(screen.getByText('message 5002')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /show more lines/i })).toBeNull();
    expect(screen.getByRole('link', { name: /download/i })).toHaveAttribute(
      'href',
      '/api/v1/artifacts/a1/raw',
    );
  });

  it('defers raw log access until a dmesg accordion is expanded', async () => {
    queries.logs.data = [REPORT];
    render(
      <ChakraProvider value={system}>
        <BootLogViewer runId="run1" />
      </ChakraProvider>,
    );
    expect(queries.fetchRaw.mock.calls.some((call) => call[1] === true)).toBe(false);
    await act(async () => {
      screen.getByRole('button', { name: /boot.log/i }).focus();
    });
    fireEvent.click(screen.getByRole('button', { name: /boot.log/i }));
    await waitFor(() => expect(queries.fetchRaw).toHaveBeenCalledWith('a1', true));
    expect(screen.getByText('Linux version 6.1.0-g1a2b3c4')).toBeInTheDocument();
  });

  it('shows unavailable and request failures explicitly', () => {
    const result = render(
      <ChakraProvider value={system}>
        <BootLogBody report={{ ...REPORT, artifact_id: null }} open />
      </ChakraProvider>,
    );
    expect(screen.getByText(/raw log unavailable/i)).toBeInTheDocument();
    queries.raw = { data: undefined, isLoading: false, isError: true };
    result.rerender(
      <ChakraProvider value={system}>
        <BootLogBody report={REPORT} open />
      </ChakraProvider>,
    );
    expect(screen.getByText(/failed to load log/i)).toBeInTheDocument();
  });

  it('shows captured pytest logs inline only after expansion', async () => {
    render(
      <ChakraProvider value={system}>
        <CapturedOutputViewer
          artifacts={[
            {
              id: 'a1',
              filename: 'captured/case/call-system-out.log',
              kind: 'log_text',
              manifest_kind: null,
              size_bytes: 100,
            },
          ]}
        />
      </ChakraProvider>,
    );
    expect(screen.getByText('Captured output')).toBeInTheDocument();
    expect(screen.queryByText('Linux version 6.1.0-g1a2b3c4')).toBeNull();
    await act(async () => {
      screen.getByRole('button', { name: /call-system-out.log/i }).focus();
    });
    fireEvent.click(screen.getByRole('button', { name: /call-system-out.log/i }));
    await waitFor(() =>
      expect(screen.getByText('Linux version 6.1.0-g1a2b3c4')).toBeInTheDocument(),
    );
  });
});
