import { ChakraProvider } from '@chakra-ui/react';
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { system } from '../theme';
import { RunContextSummary } from './RunContextSummary';

describe('RunContextSummary', () => {
  it('shows originating CI links and hardware metadata for the selected case', () => {
    render(
      <ChakraProvider value={system}>
        <RunContextSummary
          inherited
          ci={{
            provider: 'github',
            repository: 'org/repo',
            workflow: 'Hardware CI',
            run_id: '42',
            attempt: '2',
            job_name: 'board-test',
            run_url: 'https://github.com/org/repo/actions/runs/42',
            job_url: 'https://github.com/org/repo/actions/runs/42/job/1',
            matrix: { board: 'ad9361' },
          }}
          hardware={{
            place: 'rig-1',
            board: 'ad9361',
            carrier: 'carrier-a',
            exporters: ['exporter-a'],
            tags: { revision: 'B' },
            metadata_status: 'available',
          }}
        />
      </ChakraProvider>,
    );
    expect(screen.getByText(/inherited from run/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /open ci run/i })).toHaveAttribute(
      'href',
      'https://github.com/org/repo/actions/runs/42',
    );
    expect(screen.getByRole('link', { name: /open ci job/i })).toHaveAttribute(
      'href',
      'https://github.com/org/repo/actions/runs/42/job/1',
    );
    expect(screen.getByText(/rig-1/)).toBeInTheDocument();
    expect(screen.getByText(/carrier-a/)).toBeInTheDocument();
    expect(screen.getByText(/exporter-a/)).toBeInTheDocument();
    expect(screen.getByText(/revision/)).toBeInTheDocument();
  });

  it('states missing context for old uploads', () => {
    render(
      <ChakraProvider value={system}>
        <RunContextSummary />
      </ChakraProvider>,
    );
    expect(screen.getByText(/ci context unavailable/i)).toBeInTheDocument();
    expect(screen.getByText(/hardware context unavailable/i)).toBeInTheDocument();
  });

  it('exposes collection errors and ignores unsafe CI URLs', () => {
    render(
      <ChakraProvider value={system}>
        <RunContextSummary
          ci={{ run_url: 'javascript:alert(1)', collection_errors: ['CI lookup failed'] }}
          hardware={{
            metadata_status: 'partial',
            metadata_error: 'Exporter unavailable',
            collection_errors: ['dmesg denied'],
          }}
        />
      </ChakraProvider>,
    );
    expect(screen.queryByRole('link')).toBeNull();
    expect(screen.getByText(/ci lookup failed/i)).toBeInTheDocument();
    expect(screen.getByText(/exporter unavailable/i)).toBeInTheDocument();
    expect(screen.getByText(/dmesg denied/i)).toBeInTheDocument();
  });
});
