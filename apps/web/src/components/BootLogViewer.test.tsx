import { ChakraProvider } from '@chakra-ui/react';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { system } from '../theme';

const RAW = [
  'Linux version 6.1.0-g1a2b3c4',
  '<4> spi-nor: flash warning',
  'ad9361 spi0.0: probe failed -110',
  '<3> mmc0: error reading sector',
  'Kernel panic - not syncing: oops',
].join('\n');

vi.mock('../api/queries', () => ({
  useRunLogs: () => ({ data: [] }),
  useArtifactRaw: () => ({ data: RAW, isLoading: false, isError: false }),
}));

import { BootLogBody } from './BootLogViewer';

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
