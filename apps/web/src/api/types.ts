export interface User {
  id: string;
  email: string;
  auth_provider?: string;
  is_admin?: boolean;
}

export interface AdminProject {
  id: string;
  slug: string;
  name: string;
  run_count: number;
}

export interface ProjectDeleted {
  slug: string;
  runs: number;
  artifacts: number;
  blobs: number;
}

export interface AdminAccount {
  id: string;
  email: string;
  auth_provider: string;
  is_admin: boolean;
  created_at: string;
}

export interface BackupRun {
  timestamp: string;
  status: string;
  postgres_bytes: number | null;
  minio_included: boolean;
  minio_bytes: number | null;
  cloudsmith: string;
  keep: number | null;
  error: string | null;
}

export interface ActivityEvent {
  action: string;
  user_email: string | null;
  project_id: string | null;
  target_type: string | null;
  target_id: string | null;
  detail: Record<string, unknown>;
  created_at: string;
}

export interface ContainerLogs {
  service: string;
  available: boolean;
  message: string | null;
  lines: string[];
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
  created_at: string;
  pass_count: number;
  fail_count: number;
  error_count: number;
  skip_count: number;
  suite_names: string[];
  tags: RunTag[];
  has_figures: boolean;
  has_boot_log: boolean;
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

export interface BootSummary {
  kernel_version: string | null;
  board: string | null;
  kernel_commit: string | null;
  hdl_commit: string | null;
  kernel_commit_url: string | null;
  hdl_commit_url: string | null;
  error_count: number;
  warn_count: number;
  has_panic: boolean;
  shared_kernel_count: number;
  shared_hdl_count: number;
}

export interface CommitCount {
  commit: string;
  run_count: number;
}

export interface LogFinding {
  severity: 'error' | 'warn' | 'panic' | 'probe_fail';
  line_no: number | null;
  text: string;
}

export interface LogReport {
  source: string;
  artifact_id: string | null;
  kernel_version: string | null;
  board: string | null;
  kernel_commit: string | null;
  hdl_commit: string | null;
  kernel_commit_url: string | null;
  hdl_commit_url: string | null;
  error_count: number;
  warn_count: number;
  has_panic: boolean;
  findings: LogFinding[];
}

export interface RunDetail {
  id: string;
  project_id: string;
  project_slug: string | null;
  name: string;
  status: RunStatus;
  started_at: string | null;
  finished_at: string | null;
  junit_artifact_id: string | null;
  calibration_run_id: string | null;
  calibration_run_name: string | null;
  tags: RunTag[];
  suites: SuiteSummary[];
  boot: BootSummary | null;
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
  manifest_kind: string | null;
  filename: string;
  size_bytes: number;
}

export interface Measurement {
  name: string;
  value: number;
  unit: string | null;
  spec_min: number | null;
  spec_max: number | null;
  in_spec: boolean | null;
  margin: number | null;
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
  measurements: Measurement[];
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

export interface SpectrumResponse {
  frequencies: number[];
  powers: number[];
  unit: string | null;
  metadata: Record<string, string | number>;
}

export interface SpectrogramResponse {
  frequencies: number[];
  times: number[];
  powers: number[][];
  unit: string | null;
  metadata: Record<string, string | number>;
}

export interface ChannelMetricsResponse {
  channel_power_dbm: number | null;
  acpr_lower_dbc: number | null;
  acpr_upper_dbc: number | null;
  obw_hz: number | null;
  channel_band: [number, number];
  lower_band: [number, number] | null;
  upper_band: [number, number] | null;
}

export interface Spur {
  frequency: number;
  power: number;
}

export interface SpursResponse {
  margin_db: number;
  noise_floor_dbm: number;
  spurs: Spur[];
}

export interface GenalyzerMarker {
  label: string;
  frequency: number;
  mag_dbfs: number;
}

export interface GenalyzerResponse {
  markers: GenalyzerMarker[];
  snr: number | null;
  sfdr: number | null;
  sinad: number | null;
  thd: number | null;
  enob: number | null;
  fsnr: number | null;
}

export interface MaskSegment {
  f_start: number;
  f_end: number;
  max_dbm: number;
}

export interface Mask {
  id: string;
  project_id: string;
  name: string;
  segments: MaskSegment[];
}

export interface RunHeader {
  id: string;
  name: string;
  status: RunStatus;
  pass_count: number;
  fail_count: number;
}

export interface CaseDiff {
  suite_name: string;
  classname: string;
  name: string;
  statuses: (string | null)[];
  waveform_artifact_ids: (string | null)[];
}

export interface MeasurementDiff {
  name: string;
  unit: string | null;
  values: (number | null)[];
  delta: number | null;
}

export interface CompareResponse {
  runs: RunHeader[];
  cases: CaseDiff[];
  pass_rate_delta: number | null;
  measurement_diffs: MeasurementDiff[];
  boots: (BootSummary | null)[];
}

export interface TrendPoint {
  run_id: string;
  run_name: string;
  created_at: string;
  case_id: string;
  case_name: string;
  value: number;
  unit: string | null;
  spec_min: number | null;
  spec_max: number | null;
  in_spec: boolean | null;
  margin: number | null;
  tags: Record<string, string>;
}

export interface TrendResponse {
  measurement_name: string;
  points: TrendPoint[];
}

export interface RegressionEvent {
  measurement_name: string;
  run_id: string;
  run_name: string;
  created_at: string;
  value: number;
  unit: string | null;
  previous_value: number | null;
  kind: 'crossed_out' | 'still_out';
}

export interface RegressionsResponse {
  events: RegressionEvent[];
}

export interface SpecDefinition {
  measurement_name: string;
  spec_min: number | null;
  spec_max: number | null;
  unit: string | null;
}

export interface DashboardViewConfig {
  tab?: string;
  measurement?: string | null;
  tagFilters?: Record<string, string>;
}

export interface SavedView {
  name: string;
  config: DashboardViewConfig;
}

export interface AuditEvent {
  action: string;
  user_email: string | null;
  target_type: string | null;
  target_id: string | null;
  detail: Record<string, unknown>;
  created_at: string;
}

export interface OverviewStats {
  total_projects: number;
  total_runs: number;
  total_tests: number;
  total_failures: number;
  pass_rate: number;
}

export interface RecentRun {
  id: string;
  name: string;
  project_slug: string;
  project_name: string;
  status: RunStatus;
  created_at: string;
  pass_count: number;
  fail_count: number;
}

export interface DailyPoint {
  date: string;
  runs: number;
  failures: number;
}

export interface OverviewResponse {
  stats: OverviewStats;
  recent_runs: RecentRun[];
  daily: DailyPoint[];
}

export interface ApiToken {
  id: string;
  name: string;
  prefix: string;
  created_at: string;
  last_used_at: string | null;
  expires_at: string | null;
}

export interface CreateTokenRequest {
  name: string;
  expires_in_days?: number | null;
}

export interface TokenCreated extends ApiToken {
  token: string;
}

export interface TestSummary {
  classname: string;
  name: string;
  runs: number;
  pass_count: number;
  fail_count: number;
  skip_count: number;
  fail_rate: number;
  flaky_score: number;
  last_status: string;
  avg_duration_ms: number;
  last_duration_ms: number;
  recent_statuses: string[];
}

export interface TestTimelinePoint {
  run_id: string;
  run_name: string;
  created_at: string;
  status: string;
  duration_ms: number;
}

export interface SearchHit {
  kind: 'project' | 'run' | 'case' | 'commit';
  title: string;
  subtitle: string;
  project_slug: string | null;
  run_id: string | null;
}

export interface MatrixCell {
  status: RunStatus;
  run_id: string;
  passed: number;
  total: number;
  finished_at: string | null;
  age_seconds: number;
  stale: boolean;
}

export interface MatrixResponse {
  scope: string;
  generated_at: string;
  row_key: string;
  col_key: string;
  rows: string[];
  cols: string[];
  boot_files: string[];
  stale_after_hours: number;
  summary: Record<string, number>;
  unplaced_runs: number;
  cells: Record<string, MatrixCell>;
}

export interface MatrixConfig {
  row_key: string;
  col_key: string;
  filter_key: string;
  curated_rows: string[];
  curated_cols: string[];
  stale_after_hours: number;
  refresh_seconds: number;
  rotate_filters: string[];
}

export interface MatrixConfigOut {
  scope: string;
  config: MatrixConfig;
}

export interface MatrixDashboardPrefs {
  enabled: boolean;
  default_scope?: string;
  boot_file_filter?: string[];
  rotate?: boolean;
}

export interface UserSettingOut {
  key: string;
  value: Record<string, unknown>;
  updated_at: string;
}
