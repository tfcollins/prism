import { ChakraProvider, defaultSystem } from '@chakra-ui/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { AuthProvider } from '../src/auth/AuthProvider';
import { useAuth } from '../src/auth/useAuth';

const mockGet = vi.hoisted(() => vi.fn());

vi.mock('../src/api/client', () => ({
  api: {
    get: mockGet,
    post: vi.fn(),
    defaults: { withCredentials: true },
  },
}));

const Probe = () => {
  const { user, status } = useAuth();
  return (
    <div>
      <span data-testid="status">{status}</span>
      <span data-testid="email">{user?.email ?? 'none'}</span>
    </div>
  );
};

describe('AuthProvider', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    mockGet.mockResolvedValue({ data: { id: '1', email: 'a@b.com' } });
  });

  it('loads the current user on mount', async () => {
    const qc = new QueryClient();
    render(
      <ChakraProvider value={defaultSystem}>
        <QueryClientProvider client={qc}>
          <AuthProvider>
            <Probe />
          </AuthProvider>
        </QueryClientProvider>
      </ChakraProvider>,
    );
    await waitFor(() => {
      expect(screen.getByTestId('status').textContent).toBe('authenticated');
    });
    expect(screen.getByTestId('email').textContent).toBe('a@b.com');
  });
});
