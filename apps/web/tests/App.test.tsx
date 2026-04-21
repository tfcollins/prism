import { ChakraProvider, defaultSystem } from '@chakra-ui/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { App } from '../src/App';
import { AuthProvider } from '../src/auth/AuthProvider';

const mockGet = vi.hoisted(() => vi.fn());

vi.mock('../src/api/client', () => ({
  api: {
    get: mockGet,
    post: vi.fn(),
    defaults: { withCredentials: true },
  },
}));

describe('App', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    mockGet.mockRejectedValue(new Error('401'));
  });

  it('redirects unauthenticated users to /login', async () => {
    const qc = new QueryClient();
    render(
      <ChakraProvider value={defaultSystem}>
        <QueryClientProvider client={qc}>
          <AuthProvider>
            <MemoryRouter initialEntries={['/']}>
              <App />
            </MemoryRouter>
          </AuthProvider>
        </QueryClientProvider>
      </ChakraProvider>,
    );
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /sign in to prism/i })).toBeInTheDocument();
    });
  });
});
