import { ChakraProvider } from '@chakra-ui/react';
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { MatrixResponse } from '../api/types';
import { system } from '../theme';
import { MatrixGrid } from './MatrixGrid';

const DATA: MatrixResponse = {
  scope: 'project:kuiper-linux',
  generated_at: new Date().toISOString(),
  row_key: 'hw',
  col_key: 'platform',
  rows: ['ad9081', 'ad9371'],
  cols: ['zcu102', 'zed'],
  boot_files: ['zynqmp-common'],
  stale_after_hours: 48,
  summary: { pass: 1, fail: 1, mixed: 0, error: 0, no_run: 2 },
  unplaced_runs: 0,
  cells: {
    'ad9081|zcu102': {
      status: 'pass',
      run_id: 'r1',
      passed: 12,
      total: 12,
      finished_at: new Date().toISOString(),
      age_seconds: 120,
      stale: false,
    },
    'ad9371|zed': {
      status: 'fail',
      run_id: 'r2',
      passed: 8,
      total: 12,
      finished_at: new Date().toISOString(),
      age_seconds: 99999,
      stale: true,
    },
  },
};

function renderGrid(data: MatrixResponse = DATA) {
  return render(
    <ChakraProvider value={system}>
      <MatrixGrid data={data} />
    </ChakraProvider>,
  );
}

describe('MatrixGrid', () => {
  it('renders row and column headers', () => {
    renderGrid();
    expect(screen.getByText('ad9081')).toBeInTheDocument();
    expect(screen.getByText('zcu102')).toBeInTheDocument();
  });

  it('renders a PASS cell and a no-run cell', () => {
    renderGrid();
    expect(screen.getByText('PASS')).toBeInTheDocument();
    // ad9081|zed has no cell => no-run marker rendered
    expect(screen.getAllByText('no run')).toHaveLength(3);
  });

  it('marks a stale cell', () => {
    renderGrid();
    expect(screen.getByText(/stale/i)).toBeInTheDocument();
  });

  it('renders the KPI summary counts', () => {
    renderGrid();
    expect(screen.getByLabelText('pass count: 1')).toBeInTheDocument();
    expect(screen.getByLabelText('fail count: 1')).toBeInTheDocument();
    expect(screen.getByLabelText('error count: 0')).toBeInTheDocument();
    expect(screen.getByLabelText('no run count: 2')).toBeInTheDocument();
  });
});
