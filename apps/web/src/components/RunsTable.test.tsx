import { ChakraProvider } from '@chakra-ui/react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';

import { system } from '../theme';
import { RunSelectionActions } from './RunsTable';

function renderActions(ids: string[]) {
  return render(
    <ChakraProvider value={system}>
      <MemoryRouter>
        <RunSelectionActions ids={ids} />
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
