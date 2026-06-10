import { ChakraProvider } from '@chakra-ui/react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { system } from '../theme';

vi.mock('../api/queries', () => ({
  useProjects: () => ({ data: [] }),
  useMatrixPrefs: () => ({ data: { enabled: false } }),
}));
vi.mock('../auth/useAuth', () => ({
  useAuth: () => ({ user: { is_admin: false } }),
}));

import { Sidebar } from './Sidebar';

beforeEach(() => {
  // The Sidebar reads sidebar-collapsed state from localStorage on mount;
  // jsdom here has no working localStorage, so provide a minimal in-memory stub.
  const store: Record<string, string> = {};
  vi.stubGlobal('localStorage', {
    getItem: (k: string) => store[k] ?? null,
    setItem: (k: string, v: string) => {
      store[k] = v;
    },
    removeItem: (k: string) => {
      delete store[k];
    },
    clear: () => {
      for (const k of Object.keys(store)) delete store[k];
    },
  });
});

describe('Sidebar', () => {
  it('shows the version with the build commit', () => {
    render(
      <ChakraProvider value={system}>
        <MemoryRouter>
          <Sidebar />
        </MemoryRouter>
      </ChakraProvider>,
    );
    // __GIT_COMMIT__ resolves to 'dev' under Vitest (see vitest.config define).
    expect(screen.getByText('v0.4 · dev')).toBeInTheDocument();
  });
});
