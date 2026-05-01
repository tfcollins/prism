import { useQuery } from '@tanstack/react-query';

import { api } from './client';
import type {
  CaseDetail,
  CaseListItem,
  CompareResponse,
  FFTResponse,
  Project,
  RunDetail,
  RunListItem,
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

export function useRun(runId: string | undefined) {
  return useQuery({
    queryKey: ['runs', 'detail', runId],
    queryFn: async () => (await api.get<RunDetail>(`/runs/${runId}`)).data,
    enabled: Boolean(runId),
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
      (await api.get<WaveformResponse>(`/artifacts/${artifactId}/waveform`, { params: { downsample } })).data,
    enabled: Boolean(artifactId),
  });
}

export function useFFT(
  artifactId: string | undefined,
  params: { window: string; nfft: number; overlap: number } = { window: 'hann', nfft: 1024, overlap: 0.5 },
) {
  return useQuery({
    queryKey: ['artifacts', artifactId, 'fft', params],
    queryFn: async () =>
      (await api.get<FFTResponse>(`/artifacts/${artifactId}/fft`, { params })).data,
    enabled: Boolean(artifactId),
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
