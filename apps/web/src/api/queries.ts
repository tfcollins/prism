import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import axios from 'axios';

import { api } from './client';
import type {
  ActivityEvent,
  AdminAccount,
  AdminProject,
  ApiToken,
  AuditEvent,
  BackupRun,
  CaseArtifact,
  CaseDetail,
  CaseListItem,
  ChannelMetricsResponse,
  CommitCount,
  CompareResponse,
  ContainerLogs,
  CreateTokenRequest,
  FFTResponse,
  LogReport,
  Mask,
  MatrixConfig,
  MatrixConfigOut,
  MatrixDashboardPrefs,
  MatrixResponse,
  OverviewResponse,
  Project,
  ProjectDeleted,
  RegressionsResponse,
  RunDetail,
  RunListItem,
  SavedView,
  SearchHit,
  SpecDefinition,
  SpectrogramResponse,
  SpectrumResponse,
  SpursResponse,
  TestSummary,
  TestTimelinePoint,
  TokenCreated,
  TrendResponse,
  UserSettingOut,
  WaveformResponse,
} from './types';

export function useProjects() {
  return useQuery({
    queryKey: ['projects'],
    queryFn: async () => (await api.get<Project[]>('/projects')).data,
  });
}

export function useRuns(projectSlug: string | undefined, status?: string) {
  return useQuery({
    queryKey: ['runs', projectSlug, status ?? null],
    queryFn: async () => {
      const params: Record<string, string> = { project: projectSlug! };
      if (status) params.status = status;
      return (await api.get<RunListItem[]>('/runs', { params })).data;
    },
    enabled: Boolean(projectSlug),
  });
}

export function useRunsByTag(
  projectSlug: string | undefined,
  tagKey: string | undefined,
  tagValue: string | undefined,
) {
  return useQuery({
    queryKey: ['runs', projectSlug, 'by-tag', tagKey ?? null, tagValue ?? null],
    queryFn: async () =>
      (
        await api.get<RunListItem[]>('/runs', {
          params: { project: projectSlug!, tag_key: tagKey!, tag_value: tagValue! },
        })
      ).data,
    enabled: Boolean(projectSlug) && Boolean(tagKey) && Boolean(tagValue),
  });
}

export function useTagKeys(projectSlug: string | undefined) {
  return useQuery({
    queryKey: ['projects', projectSlug, 'tag-keys'],
    queryFn: async () => (await api.get<string[]>(`/projects/${projectSlug}/tag-keys`)).data,
    enabled: Boolean(projectSlug),
  });
}

export interface TagValueCount {
  value: string;
  run_count: number;
}

export function useTagValues(projectSlug: string | undefined, key: string | undefined) {
  return useQuery({
    queryKey: ['projects', projectSlug, 'tag-values', key ?? null],
    queryFn: async () =>
      (
        await api.get<TagValueCount[]>(`/projects/${projectSlug}/tag-values`, {
          params: { key: key! },
        })
      ).data,
    enabled: Boolean(projectSlug) && Boolean(key),
  });
}

export function useRun(runId: string | undefined) {
  return useQuery({
    queryKey: ['runs', 'detail', runId],
    queryFn: async () => (await api.get<RunDetail>(`/runs/${runId}`)).data,
    enabled: Boolean(runId),
    // Poll while ingest is still pending so the view (and completion toast)
    // update without a manual refresh; stop once it reaches a terminal status.
    refetchInterval: (query) =>
      (query.state.data as RunDetail | undefined)?.status === 'pending' ? 4000 : false,
  });
}

export function useSetCalibration(runId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (calibrationRunId: string | null) =>
      (
        await api.patch<RunDetail>(`/runs/${runId}/calibration`, {
          calibration_run_id: calibrationRunId,
        })
      ).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['runs', 'detail', runId] }),
  });
}

export function useSuiteCases(suiteId: string | undefined) {
  return useQuery({
    queryKey: ['suites', suiteId, 'cases'],
    queryFn: async () => (await api.get<CaseListItem[]>(`/suites/${suiteId}/cases`)).data,
    enabled: Boolean(suiteId),
  });
}

export function useCase(caseId: string | undefined) {
  return useQuery({
    queryKey: ['cases', caseId],
    queryFn: async () => (await api.get<CaseDetail>(`/cases/${caseId}`)).data,
    enabled: Boolean(caseId),
  });
}

export function useWaveform(artifactId: string | undefined, downsample = 2000) {
  return useQuery({
    queryKey: ['artifacts', artifactId, 'waveform', downsample],
    queryFn: async () =>
      (
        await api.get<WaveformResponse>(`/artifacts/${artifactId}/waveform`, {
          params: { downsample },
        })
      ).data,
    enabled: Boolean(artifactId),
  });
}

export function useFFT(
  artifactId: string | undefined,
  params: { window: string; nfft: number; overlap: number } = {
    window: 'hann',
    nfft: 1024,
    overlap: 0.5,
  },
) {
  return useQuery({
    queryKey: ['artifacts', artifactId, 'fft', params],
    queryFn: async () =>
      (await api.get<FFTResponse>(`/artifacts/${artifactId}/fft`, { params })).data,
    enabled: Boolean(artifactId),
  });
}

export function useSpectrum(artifactId: string | undefined) {
  return useQuery({
    queryKey: ['artifacts', artifactId, 'spectrum'],
    queryFn: async () =>
      (await api.get<SpectrumResponse>(`/artifacts/${artifactId}/spectrum`)).data,
    enabled: Boolean(artifactId),
  });
}

export function useSpectrogram(artifactId: string | undefined) {
  return useQuery({
    queryKey: ['artifacts', artifactId, 'spectrogram'],
    queryFn: async () =>
      (await api.get<SpectrogramResponse>(`/artifacts/${artifactId}/spectrogram`)).data,
    enabled: Boolean(artifactId),
  });
}

export function useChannelMetrics(
  artifactId: string | undefined,
  params: { center: number; channel_bw: number; offset?: number; adjacent_bw?: number } | null,
) {
  return useQuery({
    queryKey: ['artifacts', artifactId, 'channel-power', params],
    queryFn: async () =>
      (
        await api.get<ChannelMetricsResponse>(`/artifacts/${artifactId}/channel-power`, {
          params: params!,
        })
      ).data,
    enabled: Boolean(artifactId) && params !== null,
  });
}

export function useSpurs(artifactId: string | undefined, marginDb: number, enabled: boolean) {
  return useQuery({
    queryKey: ['artifacts', artifactId, 'spurs', marginDb],
    queryFn: async () =>
      (
        await api.get<SpursResponse>(`/artifacts/${artifactId}/spurs`, {
          params: { margin_db: marginDb },
        })
      ).data,
    enabled: Boolean(artifactId) && enabled,
  });
}

export function useRegressions(projectSlug: string | undefined) {
  return useQuery({
    queryKey: ['projects', projectSlug, 'regressions'],
    queryFn: async () =>
      (await api.get<RegressionsResponse>(`/projects/${projectSlug}/regressions`)).data,
    enabled: Boolean(projectSlug),
  });
}

export function useSpecs(projectSlug: string | undefined) {
  return useQuery({
    queryKey: ['projects', projectSlug, 'specs'],
    queryFn: async () => (await api.get<SpecDefinition[]>(`/projects/${projectSlug}/specs`)).data,
    enabled: Boolean(projectSlug),
  });
}

export function useUpsertSpec(projectSlug: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (spec: SpecDefinition) =>
      (await api.put<SpecDefinition>(`/projects/${projectSlug}/specs`, spec)).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['projects', projectSlug, 'specs'] });
      qc.invalidateQueries({ queryKey: ['projects', projectSlug, 'regressions'] });
    },
  });
}

export function useDeleteSpec(projectSlug: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (measurementName: string) => {
      await api.delete(`/projects/${projectSlug}/specs/${encodeURIComponent(measurementName)}`);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['projects', projectSlug, 'specs'] });
      qc.invalidateQueries({ queryKey: ['projects', projectSlug, 'regressions'] });
    },
  });
}

export function useViews(projectSlug: string | undefined) {
  return useQuery({
    queryKey: ['projects', projectSlug, 'views'],
    queryFn: async () => (await api.get<SavedView[]>(`/projects/${projectSlug}/views`)).data,
    enabled: Boolean(projectSlug),
  });
}

export function useUpsertView(projectSlug: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (view: SavedView) =>
      (await api.put<SavedView>(`/projects/${projectSlug}/views`, view)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['projects', projectSlug, 'views'] }),
  });
}

export function useDeleteView(projectSlug: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (name: string) => {
      await api.delete(`/projects/${projectSlug}/views/${encodeURIComponent(name)}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['projects', projectSlug, 'views'] }),
  });
}

export function useAudit(projectSlug: string | undefined) {
  return useQuery({
    queryKey: ['projects', projectSlug, 'audit'],
    queryFn: async () => (await api.get<AuditEvent[]>(`/projects/${projectSlug}/audit`)).data,
    enabled: Boolean(projectSlug),
  });
}

export function useMasks(projectSlug: string | undefined) {
  return useQuery({
    queryKey: ['projects', projectSlug, 'masks'],
    queryFn: async () => (await api.get<Mask[]>(`/projects/${projectSlug}/masks`)).data,
    enabled: Boolean(projectSlug),
  });
}

export function useRunArtifacts(runId: string | undefined) {
  return useQuery({
    queryKey: ['runs', runId, 'artifacts'],
    queryFn: async () => (await api.get<CaseArtifact[]>(`/runs/${runId}/artifacts`)).data,
    enabled: Boolean(runId),
  });
}

export function useArtifactJson<T = unknown>(artifactId: string | undefined) {
  return useQuery({
    queryKey: ['artifacts', artifactId, 'raw-json'],
    queryFn: async () => (await api.get<T>(`/artifacts/${artifactId}/raw`)).data,
    enabled: Boolean(artifactId),
  });
}

export function useCompare(runIds: string[]) {
  return useQuery({
    queryKey: ['compare', runIds.slice().sort().join(',')],
    queryFn: async () => (await api.post<CompareResponse>('/compare', { run_ids: runIds })).data,
    enabled: runIds.length >= 2,
  });
}

export function useMeasurementNames(projectSlug: string | undefined) {
  return useQuery({
    queryKey: ['projects', projectSlug, 'measurements'],
    queryFn: async () => (await api.get<string[]>(`/projects/${projectSlug}/measurements`)).data,
    enabled: Boolean(projectSlug),
  });
}

export function useMeasurementTrend(projectSlug: string | undefined, name: string | undefined) {
  return useQuery({
    queryKey: ['projects', projectSlug, 'trend', name],
    queryFn: async () =>
      (
        await api.get<TrendResponse>(
          `/projects/${projectSlug}/measurements/${encodeURIComponent(name!)}/trend`,
        )
      ).data,
    enabled: Boolean(projectSlug) && Boolean(name),
  });
}

export function useRunLogs(runId: string | undefined) {
  return useQuery({
    queryKey: ['runs', runId, 'logs'],
    queryFn: async () => (await api.get<LogReport[]>(`/runs/${runId}/logs`)).data,
    enabled: Boolean(runId),
  });
}

export function useCommits(projectSlug: string | undefined, type: 'kernel' | 'hdl') {
  return useQuery({
    queryKey: ['projects', projectSlug, 'commits', type],
    queryFn: async () =>
      (await api.get<CommitCount[]>(`/projects/${projectSlug}/commits`, { params: { type } })).data,
    enabled: Boolean(projectSlug),
  });
}

export function useRunsByCommit(
  projectSlug: string | undefined,
  field: 'kernel_commit' | 'hdl_commit',
  commit: string | undefined,
) {
  return useQuery({
    queryKey: ['runs', projectSlug, 'by-commit', field, commit ?? null],
    queryFn: async () =>
      (
        await api.get<RunListItem[]>('/runs', {
          params: { project: projectSlug!, [field]: commit! },
        })
      ).data,
    enabled: Boolean(projectSlug) && Boolean(commit),
  });
}

// --- Admin panel -----------------------------------------------------------

export function useAdminAccounts() {
  return useQuery({
    queryKey: ['admin', 'accounts'],
    queryFn: async () => (await api.get<AdminAccount[]>('/admin/accounts')).data,
  });
}

export function useAdminProjects() {
  return useQuery({
    queryKey: ['admin', 'projects'],
    queryFn: async () => (await api.get<AdminProject[]>('/admin/projects')).data,
  });
}

export function useDeleteProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (slug: string) =>
      (await api.delete<ProjectDeleted>(`/admin/projects/${slug}`)).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin', 'projects'] });
      qc.invalidateQueries({ queryKey: ['projects'] });
      qc.invalidateQueries({ queryKey: ['overview'] });
    },
  });
}

export function useAdminBackups() {
  return useQuery({
    queryKey: ['admin', 'backups'],
    queryFn: async () => (await api.get<BackupRun[]>('/admin/backups')).data,
  });
}

export function useAdminActivity(limit = 200) {
  return useQuery({
    queryKey: ['admin', 'activity', limit],
    queryFn: async () =>
      (await api.get<ActivityEvent[]>('/admin/activity', { params: { limit } })).data,
  });
}

export function useAdminLogs(service: string, tail = 200) {
  return useQuery({
    queryKey: ['admin', 'logs', service, tail],
    queryFn: async () =>
      (await api.get<ContainerLogs>('/admin/logs', { params: { service, tail } })).data,
  });
}

export function useOverview() {
  return useQuery({
    queryKey: ['overview'],
    queryFn: async () => (await api.get<OverviewResponse>('/overview')).data,
  });
}

export function useTokens() {
  return useQuery({
    queryKey: ['tokens'],
    queryFn: async () => (await api.get<ApiToken[]>('/tokens')).data,
  });
}

export function useCreateToken() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: CreateTokenRequest) =>
      (await api.post<TokenCreated>('/tokens', body)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['tokens'] }),
  });
}

export function useRevokeToken() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/tokens/${id}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['tokens'] }),
  });
}

export function useProjectTests(projectSlug: string | undefined) {
  return useQuery({
    queryKey: ['projects', projectSlug, 'tests'],
    queryFn: async () => (await api.get<TestSummary[]>(`/projects/${projectSlug}/tests`)).data,
    enabled: Boolean(projectSlug),
  });
}

export function useTestHistory(
  projectSlug: string | undefined,
  classname: string | undefined,
  name: string | undefined,
) {
  return useQuery({
    queryKey: ['projects', projectSlug, 'tests', 'history', classname, name],
    queryFn: async () =>
      (
        await api.get<TestTimelinePoint[]>(`/projects/${projectSlug}/tests/history`, {
          params: { classname: classname!, name: name! },
        })
      ).data,
    enabled: Boolean(projectSlug) && Boolean(classname) && Boolean(name),
  });
}

export function useSearch(query: string) {
  const q = query.trim();
  return useQuery({
    queryKey: ['search', q],
    queryFn: async () => (await api.get<SearchHit[]>('/search', { params: { q } })).data,
    enabled: q.length >= 2,
  });
}

const MATRIX_PREFS_KEY = 'matrix_dashboard';

export function useMatrix(
  scope: string | undefined,
  bootFiles: string[],
  refetchMs: number,
) {
  return useQuery({
    queryKey: ['matrix', scope, [...bootFiles].sort()],
    queryFn: async () => {
      const params = new URLSearchParams();
      params.set('scope', scope!);
      for (const bf of bootFiles) params.append('boot_file', bf);
      return (await api.get<MatrixResponse>(`/matrix?${params.toString()}`)).data;
    },
    enabled: Boolean(scope),
    refetchInterval: refetchMs > 0 ? refetchMs : false,
    placeholderData: (prev) => prev, // keep last good data on refetch/scope change
  });
}

export function useMatrixConfig(scope: string | undefined) {
  return useQuery({
    queryKey: ['matrix', 'config', scope],
    queryFn: async () =>
      (await api.get<MatrixConfigOut>(`/matrix/config?scope=${encodeURIComponent(scope!)}`)).data,
    enabled: Boolean(scope),
  });
}

export function useUpsertMatrixConfig(scope: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (config: MatrixConfig) =>
      (await api.put<MatrixConfigOut>(`/matrix/config?scope=${encodeURIComponent(scope)}`, config))
        .data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['matrix', 'config', scope] });
      qc.invalidateQueries({ queryKey: ['matrix', scope] });
    },
  });
}

export function useMatrixPrefs() {
  return useQuery({
    queryKey: ['user', 'settings', MATRIX_PREFS_KEY],
    queryFn: async () => {
      try {
        const res = await api.get<UserSettingOut>(`/me/settings/${MATRIX_PREFS_KEY}`);
        return res.data.value as unknown as MatrixDashboardPrefs;
      } catch (err) {
        // 404 => not set yet; treat as disabled defaults. Re-throw anything else.
        if (axios.isAxiosError(err) && err.response?.status === 404) {
          return { enabled: false } as MatrixDashboardPrefs;
        }
        throw err;
      }
    },
  });
}

export function useUpsertMatrixPrefs() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (value: MatrixDashboardPrefs) =>
      (await api.put<UserSettingOut>(`/me/settings/${MATRIX_PREFS_KEY}`, { value })).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['user', 'settings', MATRIX_PREFS_KEY] }),
  });
}
