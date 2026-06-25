// Client-side dmesg/boot-log severity classifier.
//
// Ported from the server parser (apps/api/src/prism_api/parsers/logs.py
// ::_classify) so the boot-log viewer can filter the full raw log without the
// 200-line findings cap. Keep this in parity with the Python rules — the shared
// cases in dmesg.test.ts / test_parsers_logs.py are the guard.

import type { Severity } from './logFindings';

export type { Severity };

export type LogFilter = 'errors' | 'warnings' | 'all';

export interface ClassifiedLine {
  lineNo: number;
  severity: Severity | null;
  text: string;
}

const DMESG_PREFIX = /^\[\s*\d+\.\d+\]\s*/;
const SYSLOG = /<(\d)>/;
const PANIC = /kernel panic|\bOops\b|\bBUG:|Call Trace/i;
const PROBE = /probe failed|failed to|timeout/i;
const ERROR_KW = /error|fail/i;
const WARN_KW = /warn/i;

const ERROR_SEVERITIES: Severity[] = ['panic', 'error', 'probe_fail'];
const WARN_SEVERITIES: Severity[] = ['warn'];

/** Classify one raw log line. Severity precedence matches the server parser. */
export function classifyLine(raw: string): Severity | null {
  const body = raw.replace(DMESG_PREFIX, '');
  if (PANIC.test(body)) return 'panic';
  if (PROBE.test(body)) return 'probe_fail';
  const m = SYSLOG.exec(body);
  if (m) {
    const level = Number(m[1]);
    if (level <= 3) return 'error';
    if (level === 4) return 'warn';
  }
  if (ERROR_KW.test(body)) return 'error';
  if (WARN_KW.test(body)) return 'warn';
  return null;
}

/**
 * Split raw log text into classified, 1-indexed lines. A single trailing
 * newline is dropped (matching Python's str.splitlines()), so a final "\n"
 * doesn't produce a phantom empty line.
 */
export function classifyLines(text: string): ClassifiedLine[] {
  const lines = text.split(/\r?\n/);
  if (lines.length > 0 && lines[lines.length - 1] === '') lines.pop();
  return lines.map((line, i) => ({ lineNo: i + 1, severity: classifyLine(line), text: line }));
}

/** Whether a line's severity is shown under the given filter. */
export function matchesFilter(severity: Severity | null, filter: LogFilter): boolean {
  if (filter === 'all') return true;
  if (severity === null) return false;
  if (filter === 'errors') return ERROR_SEVERITIES.includes(severity);
  return WARN_SEVERITIES.includes(severity);
}
