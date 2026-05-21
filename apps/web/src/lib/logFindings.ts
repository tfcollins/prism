// apps/web/src/lib/logFindings.ts
export type Severity = 'error' | 'warn' | 'panic' | 'probe_fail';

export const SEVERITY_FG: Record<Severity, string> = {
  panic: 'var(--prism-status-fail-fg)',
  error: 'var(--prism-status-fail-fg)',
  probe_fail: 'var(--prism-status-warn-fg)',
  warn: 'var(--prism-status-warn-fg)',
};

export function severityColor(sev: string): string {
  return (SEVERITY_FG as Record<string, string>)[sev] ?? 'var(--prism-text-muted)';
}
