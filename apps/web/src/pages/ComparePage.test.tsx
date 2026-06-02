import { ChakraProvider } from '@chakra-ui/react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

import { system } from '../theme';

vi.mock('../api/queries', () => ({
  useCompare: () => ({ data: undefined, isLoading: false, isError: false }),
}));
vi.mock('../components/AppShell', () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));
// Keep Plotly (pulled in via the overlay plot components) out of jsdom.
vi.mock('plotly.js-basic-dist', () => ({ default: {} }));
vi.mock('react-plotly.js/factory', () => ({ default: () => () => null }));

import { ComparePage } from './ComparePage';

function renderAt(query: string) {
  return render(
    <ChakraProvider value={system}>
      <MemoryRouter initialEntries={[`/compare?runs=${query}`]}>
        <ComparePage />
      </MemoryRouter>
    </ChakraProvider>,
  );
}

describe('ComparePage export PDF', () => {
  it('links to the multi-run PDF with the selected run ids', () => {
    renderAt('r1,r2,r3');
    const link = screen.getByText('Export PDF').closest('a');
    expect(link).toHaveAttribute('href', '/api/v1/compare/report.pdf?runs=r1,r2,r3');
  });

  it('hides the export link when fewer than two runs are selected', () => {
    renderAt('r1');
    expect(screen.queryByText('Export PDF')).toBeNull();
  });
});
