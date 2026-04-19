import { useQuery } from '@tanstack/react-query';
import { createContext, type ReactNode } from 'react';

import { api } from '../api/client';
import type { User } from '../api/types';

export type AuthStatus = 'loading' | 'authenticated' | 'anonymous';

export interface AuthContextValue {
  user: User | null;
  status: AuthStatus;
  refresh: () => Promise<unknown>;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const query = useQuery({
    queryKey: ['auth', 'me'],
    queryFn: async () => {
      try {
        const res = await api.get<User>('/auth/me');
        return res.data;
      } catch {
        return null;
      }
    },
    staleTime: 60_000,
  });

  const status: AuthStatus = query.isLoading ? 'loading' : query.data ? 'authenticated' : 'anonymous';

  return (
    <AuthContext.Provider value={{ user: query.data ?? null, status, refresh: query.refetch }}>
      {children}
    </AuthContext.Provider>
  );
}
