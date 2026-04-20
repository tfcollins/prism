import { useQuery } from '@tanstack/react-query';
import axios from 'axios';
import { type ReactNode } from 'react';

import { api } from '../api/client';
import type { User } from '../api/types';
import { AuthContext, type AuthStatus } from './AuthContext';

export function AuthProvider({ children }: { children: ReactNode }) {
  const query = useQuery({
    queryKey: ['auth', 'me'],
    queryFn: async () => {
      const res = await api.get<User>('/auth/me');
      return res.data;
    },
    retry: false,
    staleTime: 60_000,
  });

  let status: AuthStatus;
  if (query.isLoading) {
    status = 'loading';
  } else if (query.data) {
    status = 'authenticated';
  } else if (axios.isAxiosError(query.error) && query.error.response?.status === 401) {
    status = 'anonymous';
  } else if (query.error) {
    status = 'unreachable';
  } else {
    status = 'anonymous';
  }

  return (
    <AuthContext.Provider value={{ user: query.data ?? null, status, refresh: query.refetch }}>
      {children}
    </AuthContext.Provider>
  );
}
