import { ChakraProvider } from '@chakra-ui/react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';

import type { RunListItem } from '../api/types';
import { system } from '../theme';
import { RunSelectionActions, RunsTable } from './RunsTable';

function renderActions(ids: string[]) {
  return render(
    <ChakraProvider value={system}>
      <MemoryRouter>
        <RunSelectionActions ids={ids} />
      </MemoryRouter>
    </ChakraProvider>,
  );
}

function makeRun(overrides: Partial<RunListItem>): RunListItem {
  return {
    id: 'r1',
    project_id: 'p1',
    name: 'run',
    status: 'pass',
    started_at: null,
    finished_at: null,
    created_at: '2026-06-24T00:00:00Z',
    pass_count: 1,
    fail_count: 0,
    error_count: 0,
    skip_count: 0,
    suite_names: ['dsp'],
    tags: [],
    has_figures: false,
    has_boot_log: false,
    ...overrides,
  };
}

function renderTable(runs: RunListItem[]) {
  return render(
    <ChakraProvider value={system}>
      <MemoryRouter>
        <RunsTable runs={runs} />
      </MemoryRouter>
    </ChakraProvider>,
  );
}

describe('RunSelectionActions', () => {
  it('renders nothing with no selection', () => {
    const { container } = renderActions([]);
    expect(container.textContent).toBe('');
  });

  it('exports a single run as a combined report, with no compare', () => {
    renderActions(['r1']);
    const link = screen.getByText(/Export PDF/).closest('a');
    expect(link).toHaveAttribute('href', '/api/v1/runs/report.pdf?runs=r1');
    expect(screen.getByText('Export PDF (1)')).toBeInTheDocument();
    // Compare requires >=2 runs.
    expect(screen.queryByText(/Compare/)).toBeNull();
  });

  it('exports a combined report (not a comparison) and offers compare for >=2', () => {
    renderActions(['r1', 'r2', 'r3']);
    const link = screen.getByText(/Export PDF/).closest('a');
    // The combined report endpoint — NOT /compare/report.pdf.
    expect(link).toHaveAttribute('href', '/api/v1/runs/report.pdf?runs=r1,r2,r3');
    expect(screen.getByText('Compare 3 runs')).toBeInTheDocument();
  });
});

describe('RunsTable artifact labels', () => {
  it('shows a Figures badge when the run has figures', () => {
    renderTable([makeRun({ id: 'a', name: 'wave', has_figures: true })]);
    expect(screen.getByText('Figures')).toBeInTheDocument();
    expect(screen.queryByText('Boot log')).toBeNull();
  });

  it('shows a Boot log badge when the run has a boot log', () => {
    renderTable([makeRun({ id: 'b', name: 'boot', has_boot_log: true })]);
    expect(screen.getByText('Boot log')).toBeInTheDocument();
    expect(screen.queryByText('Figures')).toBeNull();
  });

  it('shows both badges when the run has figures and a boot log', () => {
    renderTable([makeRun({ id: 'c', name: 'both', has_figures: true, has_boot_log: true })]);
    expect(screen.getByText('Figures')).toBeInTheDocument();
    expect(screen.getByText('Boot log')).toBeInTheDocument();
  });

  it('shows neither badge when the run has no figures or boot log', () => {
    renderTable([makeRun({ id: 'd', name: 'plain' })]);
    expect(screen.queryByText('Figures')).toBeNull();
    expect(screen.queryByText('Boot log')).toBeNull();
  });
});
