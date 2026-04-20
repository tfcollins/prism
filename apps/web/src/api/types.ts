export interface User {
  id: string;
  email: string;
}

export interface Project {
  id: string;
  slug: string;
  name: string;
  description: string;
}

export interface CreateProjectRequest {
  slug: string;
  name: string;
  description?: string;
}

export type RunStatus = 'pending' | 'pass' | 'fail' | 'mixed' | 'error';

export interface RunTag {
  key: string;
  value: string;
}

export interface RunListItem {
  id: string;
  project_id: string;
  name: string;
  status: RunStatus;
  started_at: string | null;
  finished_at: string | null;
  pass_count: number;
  fail_count: number;
  error_count: number;
  skip_count: number;
  tags: RunTag[];
}

export interface SuiteSummary {
  id: string;
  name: string;
  pass_count: number;
  fail_count: number;
  error_count: number;
  skip_count: number;
  duration_ms: number;
}

export interface RunDetail {
  id: string;
  project_id: string;
  name: string;
  status: RunStatus;
  started_at: string | null;
  finished_at: string | null;
  junit_artifact_id: string | null;
  tags: RunTag[];
  suites: SuiteSummary[];
}

export type CaseStatus = 'pass' | 'fail' | 'error' | 'skip';

export interface CaseListItem {
  id: string;
  classname: string;
  name: string;
  status: CaseStatus;
  duration_ms: number;
}

export interface CaseArtifact {
  id: string;
  kind: string;
  filename: string;
  size_bytes: number;
}

export interface CaseDetail {
  id: string;
  suite_id: string;
  classname: string;
  name: string;
  status: CaseStatus;
  duration_ms: number;
  failure_message: string | null;
  failure_trace: string | null;
  artifacts: CaseArtifact[];
}

export interface WaveformResponse {
  samples: number[];
  sample_rate: number | null;
  stride: number;
  total_samples: number;
}

export interface FFTResponse {
  frequencies: number[];
  magnitudes: number[];
  sample_rate: number;
  params: { window: string; nfft: number; overlap: number };
}
