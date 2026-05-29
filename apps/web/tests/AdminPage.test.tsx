import { ChakraProvider, defaultSystem } from '@chakra-ui/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { AdminPage } from '../src/pages/AdminPage';

const mockGet = vi.hoisted(() => vi.fn());

vi.mock('../src/api/client', () => ({
  api: { get: mockGet, post: vi.fn(), defaults: { withCredentials: true } },
}));

// The page wraps content in AppShell (sidebar/topbar chrome) which needs the
// color-mode + router context; stub it so the test focuses on admin content.
vi.mock('../src/components/AppShell', () => ({
  AppShell: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

function routeData(url: string) {
  if (url === '/admin/accounts')
    return {
      data: [
        {
          id: '1',
          email: 'admin@x.com',
          auth_provider: 'local',
          is_admin: true,
          created_at: '2026-01-01T00:00:00Z',
        },
      ],
    };
  return { data: [] };
}

describe('AdminPage', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    mockGet.mockImplementation((url: string) => Promise.resolve(routeData(url)));
  });

  it('renders the Accounts tab with account rows', async () => {
    const qc = new QueryClient();
    render(
      <ChakraProvider value={defaultSystem}>
        <QueryClientProvider client={qc}>
          <AdminPage />
        </QueryClientProvider>
      </ChakraProvider>,
    );
    expect(screen.getByRole('heading', { name: /^admin$/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /backups/i })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText('admin@x.com')).toBeInTheDocument());
  });
});
