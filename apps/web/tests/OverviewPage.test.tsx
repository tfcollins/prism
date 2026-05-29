import { ChakraProvider, defaultSystem } from '@chakra-ui/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { OverviewPage } from '../src/pages/OverviewPage';

const mockGet = vi.hoisted(() => vi.fn());

vi.mock('../src/api/client', () => ({
  api: { get: mockGet, post: vi.fn(), defaults: { withCredentials: true } },
}));
vi.mock('../src/components/AppShell', () => ({
  AppShell: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));
// Avoid pulling Plotly (and WebGL/canvas) into jsdom.
vi.mock('plotly.js-basic-dist', () => ({ default: {} }));
vi.mock('react-plotly.js/factory', () => ({ default: () => () => null }));
vi.mock('../src/colorMode', () => ({
  useColorMode: () => ({ colorMode: 'dark', setColorMode: vi.fn(), toggleColorMode: vi.fn() }),
}));

const OVERVIEW = {
  stats: {
    total_projects: 2,
    total_runs: 5,
    total_tests: 40,
    total_failures: 3,
    pass_rate: 0.9,
  },
  recent_runs: [
    {
      id: 'r1',
      name: 'nightly-1',
      project_slug: 'audio',
      project_name: 'Audio',
      status: 'mixed',
      created_at: '2026-05-29T00:00:00Z',
      pass_count: 8,
      fail_count: 1,
    },
  ],
  daily: [{ date: '2026-05-29', runs: 1, failures: 1 }],
};

describe('OverviewPage', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    mockGet.mockResolvedValue({ data: OVERVIEW });
  });

  it('shows stats and recent runs', async () => {
    const qc = new QueryClient();
    render(
      <ChakraProvider value={defaultSystem}>
        <QueryClientProvider client={qc}>
          <MemoryRouter>
            <OverviewPage />
          </MemoryRouter>
        </QueryClientProvider>
      </ChakraProvider>,
    );
    expect(screen.getByRole('heading', { name: /^overview$/i })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText('90.0%')).toBeInTheDocument());
    expect(screen.getByText('nightly-1')).toBeInTheDocument();
    expect(screen.getByText('Audio')).toBeInTheDocument();
  });
});
