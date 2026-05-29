import { ChakraProvider, defaultSystem } from '@chakra-ui/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ProjectDashboardPage } from '../src/pages/ProjectDashboardPage';

const mockGet = vi.hoisted(() => vi.fn());

vi.mock('../src/api/client', () => ({
  api: { get: mockGet, post: vi.fn(), put: vi.fn(), delete: vi.fn(), defaults: {} },
}));
vi.mock('../src/components/AppShell', () => ({
  AppShell: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));
// Keep Plotly (pulled in transitively via TrendPlot) out of jsdom.
vi.mock('plotly.js-basic-dist', () => ({ default: {} }));
vi.mock('react-plotly.js/factory', () => ({ default: () => () => null }));
vi.mock('../src/colorMode', () => ({
  useColorMode: () => ({ colorMode: 'dark', setColorMode: vi.fn(), toggleColorMode: vi.fn() }),
}));

function routeData(url: string) {
  // All dashboard tabs mount; give object-shaped endpoints their shape.
  if (url.endsWith('/regressions')) return { data: { events: [] } };
  if (url.endsWith('/tests'))
    return {
      data: [
        {
          classname: 'c',
          name: 't_flaky',
          runs: 3,
          pass_count: 2,
          fail_count: 1,
          skip_count: 0,
          fail_rate: 0.3333,
          flaky_score: 2,
          last_status: 'pass',
          avg_duration_ms: 12,
          last_duration_ms: 10,
          recent_statuses: ['pass', 'fail', 'pass'],
        },
      ],
    };
  return { data: [] };
}

describe('Tests tab', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    mockGet.mockImplementation((url: string) => Promise.resolve(routeData(url)));
  });

  it('lists tests with a flaky score when the Tests tab is opened', async () => {
    const qc = new QueryClient();
    render(
      <ChakraProvider value={defaultSystem}>
        <QueryClientProvider client={qc}>
          <MemoryRouter initialEntries={['/projects/audio']}>
            <Routes>
              <Route path="/projects/:slug" element={<ProjectDashboardPage />} />
            </Routes>
          </MemoryRouter>
        </QueryClientProvider>
      </ChakraProvider>,
    );
    fireEvent.click(screen.getByRole('tab', { name: /tests/i }));
    await waitFor(() => expect(screen.getByText('t_flaky')).toBeInTheDocument());
  });
});
