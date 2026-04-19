import { Navigate } from 'react-router-dom';

import { useAuth } from '../auth/useAuth';

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { status } = useAuth();
  if (status === 'loading') return null;
  if (status === 'anonymous') return <Navigate to="/login" replace />;
  return <>{children}</>;
}
