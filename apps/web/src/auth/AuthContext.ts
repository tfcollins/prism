import { createContext } from 'react';

import type { User } from '../api/types';

export type AuthStatus = 'loading' | 'authenticated' | 'anonymous' | 'unreachable';

export interface AuthContextValue {
  user: User | null;
  status: AuthStatus;
  refresh: () => Promise<unknown>;
}

export const AuthContext = createContext<AuthContextValue | null>(null);
