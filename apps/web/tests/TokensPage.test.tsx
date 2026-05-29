import { ChakraProvider, defaultSystem } from '@chakra-ui/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { TokensPage } from '../src/pages/TokensPage';

const mockGet = vi.hoisted(() => vi.fn());

vi.mock('../src/api/client', () => ({
  api: { get: mockGet, post: vi.fn(), delete: vi.fn(), defaults: { withCredentials: true } },
}));
vi.mock('../src/components/AppShell', () => ({
  AppShell: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

describe('TokensPage', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    mockGet.mockResolvedValue({
      data: [
        {
          id: 't1',
          name: 'ci-nightly',
          prefix: 'prism_AbCdEf',
          created_at: '2026-05-29T00:00:00Z',
          last_used_at: null,
          expires_at: null,
        },
      ],
    });
  });

  it('lists existing tokens with a create form', async () => {
    const qc = new QueryClient();
    render(
      <ChakraProvider value={defaultSystem}>
        <QueryClientProvider client={qc}>
          <TokensPage />
        </QueryClientProvider>
      </ChakraProvider>,
    );
    expect(screen.getByRole('heading', { name: /api tokens/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /create token/i })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText('ci-nightly')).toBeInTheDocument());
    expect(screen.getByText(/prism_AbCdEf/)).toBeInTheDocument();
  });
});
