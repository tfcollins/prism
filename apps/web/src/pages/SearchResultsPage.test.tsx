import { ChakraProvider } from '@chakra-ui/react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

import type { SearchHit } from '../api/types';
import { system } from '../theme';

const useSearch = vi.fn();

vi.mock('../api/queries', () => ({ useSearch: (q: string) => useSearch(q) }));
vi.mock('../components/AppShell', () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

import { SearchResultsPage } from './SearchResultsPage';

function renderAt(query: string) {
  return render(
    <ChakraProvider value={system}>
      <MemoryRouter initialEntries={[`/search?q=${query}`]}>
        <SearchResultsPage />
      </MemoryRouter>
    </ChakraProvider>,
  );
}

describe('SearchResultsPage', () => {
  it('groups hits by kind and links to the target', () => {
    const hits: SearchHit[] = [
      { kind: 'project', title: 'Acme', subtitle: 'acme', project_slug: 'acme', run_id: null },
      {
        kind: 'run',
        title: 'nightly-1',
        subtitle: 'acme · mixed',
        project_slug: 'acme',
        run_id: 'r1',
      },
    ];
    useSearch.mockReturnValue({ data: hits, isLoading: false, isError: false });
    renderAt('acme');

    expect(screen.getByText('Projects (1)')).toBeInTheDocument();
    expect(screen.getByText('Runs (1)')).toBeInTheDocument();
    // run hit links to the run; project hit links to the project dashboard
    expect(screen.getByText('nightly-1').closest('a')).toHaveAttribute('href', '/runs/r1');
    expect(screen.getByText('Acme').closest('a')).toHaveAttribute('href', '/projects/acme');
  });

  it('shows an empty state when there are no matches', () => {
    useSearch.mockReturnValue({ data: [], isLoading: false, isError: false });
    renderAt('zzz');
    expect(screen.getByText('No matches found.')).toBeInTheDocument();
  });

  it('prompts for input when the query is too short', () => {
    useSearch.mockReturnValue({ data: undefined, isLoading: false, isError: false });
    renderAt('a');
    expect(screen.getByText(/at least two characters/i)).toBeInTheDocument();
  });
});
