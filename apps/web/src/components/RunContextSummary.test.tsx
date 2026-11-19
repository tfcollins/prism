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

  it('shows the tested commit, branch and runner from hw-test uploads', () => {
    const sha = 'd9382d8a0123456789abcdef0123456789abcdef';
    render(
      <ChakraProvider value={system}>
        <RunContextSummary
          ci={{
            provider: 'github',
            run_id: '44473740498',
            run_number: '89',
            branch: 'dev/washington/feature',
            event: 'pull_request',
            runner: 'adsy1100-hw-1',
            sha,
            commit_url: `https://github.com/org/repo/commit/${sha}`,
            job_url: 'https://github.com/org/repo/actions/runs/44473740498/job/135395215459',
          }}
        />
      </ChakraProvider>,
    );
    expect(screen.getByText('44473740498 (#89)')).toBeInTheDocument();
    expect(screen.getByText('dev/washington/feature')).toBeInTheDocument();
    expect(screen.getByText('adsy1100-hw-1')).toBeInTheDocument();
    expect(screen.getByText('pull_request')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'd9382d8a0123' })).toHaveAttribute(
      'href',
      `https://github.com/org/repo/commit/${sha}`,
    );
    expect(screen.getByRole('link', { name: /open ci job/i })).toHaveAttribute(
      'href',
      'https://github.com/org/repo/actions/runs/44473740498/job/135395215459',
    );
  });

  it('shows an unlinked commit when its URL is missing or unsafe', () => {
    render(
      <ChakraProvider value={system}>
        <RunContextSummary ci={{ sha: 'abc1234', commit_url: 'javascript:alert(1)' }} />
      </ChakraProvider>,
    );
    expect(screen.getByText('abc1234')).toBeInTheDocument();
    expect(screen.queryByRole('link')).toBeNull();
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
