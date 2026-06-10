import { ChakraProvider } from '@chakra-ui/react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

import { system } from '../theme';

vi.mock('../components/AppShell', () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));
vi.mock('../api/queries', () => ({
  useMatrix: () => ({
    data: {
      scope: 'project:kuiper-linux', generated_at: new Date().toISOString(),
      row_key: 'hw', col_key: 'platform', rows: ['ad9081'], cols: ['zcu102'],
      boot_files: ['zynqmp-common'], stale_after_hours: 48,
      summary: { pass: 1, fail: 0, mixed: 0, error: 0, no_run: 0 }, unplaced_runs: 0,
      cells: { 'ad9081|zcu102': { status: 'pass', run_id: 'r1', passed: 5, total: 5,
        finished_at: new Date().toISOString(), age_seconds: 60, stale: false } },
    },
    isLoading: false, isError: false,
  }),
  useMatrixConfig: () => ({ data: { scope: 'project:kuiper-linux', config: {
    row_key: 'hw', col_key: 'platform', filter_key: 'boot_file', curated_rows: [],
    curated_cols: [], stale_after_hours: 48, refresh_seconds: 30, rotate_filters: [] } } }),
}));

import { MatrixDashboardPage } from './MatrixDashboardPage';

describe('MatrixDashboardPage', () => {
  it('renders the grid for a project scope', () => {
    render(
      <ChakraProvider value={system}>
        <MemoryRouter initialEntries={['/projects/kuiper-linux/matrix']}>
          <MatrixDashboardPage />
        </MemoryRouter>
      </ChakraProvider>,
    );
    expect(screen.getByText('ad9081')).toBeInTheDocument();
    expect(screen.getByText('PASS')).toBeInTheDocument();
  });
});
