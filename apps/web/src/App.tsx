import { Route, Routes } from 'react-router-dom';

import { AdminPage } from './pages/AdminPage';
import { ComparePage } from './pages/ComparePage';
import { LoginPage } from './pages/LoginPage';
import { MatrixDashboardPage } from './pages/MatrixDashboardPage';
import { MatrixKioskPage } from './pages/MatrixKioskPage';
import { OverviewPage } from './pages/OverviewPage';
import { ProjectDashboardPage } from './pages/ProjectDashboardPage';
import { ProjectsPage } from './pages/ProjectsPage';
import { RunDetailPage } from './pages/RunDetailPage';
import { SearchResultsPage } from './pages/SearchResultsPage';
import { TokensPage } from './pages/TokensPage';
import { AdminRoute } from './routes/AdminRoute';
import { ProtectedRoute } from './routes/ProtectedRoute';

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <OverviewPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/projects"
        element={
          <ProtectedRoute>
            <ProjectsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/projects/:slug"
        element={
          <ProtectedRoute>
            <ProjectDashboardPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/projects/:slug/matrix"
        element={
          <ProtectedRoute>
            <MatrixDashboardPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/matrix"
        element={
          <ProtectedRoute>
            <MatrixDashboardPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/kiosk/matrix"
        element={
          <ProtectedRoute>
            <MatrixKioskPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/runs/:id"
        element={
          <ProtectedRoute>
            <RunDetailPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/search"
        element={
          <ProtectedRoute>
            <SearchResultsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/compare"
        element={
          <ProtectedRoute>
            <ComparePage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin"
        element={
          <ProtectedRoute>
            <AdminRoute>
              <AdminPage />
            </AdminRoute>
          </ProtectedRoute>
        }
      />
      <Route
        path="/tokens"
        element={
          <ProtectedRoute>
            <TokensPage />
          </ProtectedRoute>
        }
      />
    </Routes>
  );
}
