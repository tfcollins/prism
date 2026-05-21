// apps/web/src/lib/logFindings.test.ts
import { describe, expect, it } from 'vitest';

import { severityColor } from './logFindings';

describe('severityColor', () => {
  it('maps known severities and falls back', () => {
    expect(severityColor('panic')).toContain('fail');
    expect(severityColor('warn')).toContain('warn');
    expect(severityColor('unknown')).toContain('text-muted');
  });
});
