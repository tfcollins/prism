import { ChakraProvider, defaultSystem } from '@chakra-ui/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

import { Breadcrumbs } from '../src/components/Breadcrumbs';

vi.mock('../src/api/queries', () => ({
  useProjects: () => ({ data: [] }),
  useRun: () => ({ data: undefined }),
}));

function renderAt(path: string) {
  const qc = new QueryClient();
  return render(
    <ChakraProvider value={defaultSystem}>
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={[path]}>
          <Breadcrumbs />
        </MemoryRouter>
      </QueryClientProvider>
    </ChakraProvider>,
  );
}

describe('Breadcrumbs', () => {
  it('shows Overview at the root', () => {
    renderAt('/');
    expect(screen.getByText('Overview')).toBeInTheDocument();
  });

  it('shows Projects on the projects list', () => {
    renderAt('/projects');
    expect(screen.getByText('Projects')).toBeInTheDocument();
  });

  it('shows Admin on the admin page', () => {
    renderAt('/admin');
    expect(screen.getByText('Admin')).toBeInTheDocument();
  });

  it('shows Compare on the compare page', () => {
    renderAt('/compare');
    expect(screen.getByText('Compare')).toBeInTheDocument();
  });
});
