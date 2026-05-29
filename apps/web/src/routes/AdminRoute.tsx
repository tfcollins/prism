import { Navigate } from 'react-router-dom';

import { useAuth } from '../auth/useAuth';

/**
 * Gate admin-only routes. Assumes it's nested inside <ProtectedRoute> for the
 * auth check; here we only enforce the admin flag (the bootstrap admin).
 * Non-admins are bounced to the projects view.
 */
export function AdminRoute({ children }: { children: React.ReactNode }) {
  const { user, status } = useAuth();
  if (status === 'loading') return null;
  if (!user?.is_admin) return <Navigate to="/projects" replace />;
  return <>{children}</>;
}
