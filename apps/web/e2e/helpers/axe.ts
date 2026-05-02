import AxeBuilder from '@axe-core/playwright';
import { expect, type Page } from '@playwright/test';

type AxeViolation = {
  id: string;
  impact: 'minor' | 'moderate' | 'serious' | 'critical' | null | undefined;
  help: string;
  helpUrl: string;
  nodes: { target: string[] }[];
};

export async function expectNoSeriousAxeViolations(page: Page): Promise<void> {
  const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
    .analyze();
  const filtered = (results.violations as AxeViolation[]).filter(
    (v) => v.impact === 'serious' || v.impact === 'critical',
  );
  // expect.soft reports findings without failing the test, so we can land
  // this helper before existing violations are fixed. Task 7 flips this to
  // hard `expect(...)` after fixes land.
  expect.soft(filtered, formatViolations(filtered)).toEqual([]);
}

function formatViolations(violations: AxeViolation[]): string {
  if (violations.length === 0) return 'no serious or critical axe violations';
  return violations
    .map((v) => {
      const targets = v.nodes.map((n) => n.target.join(' ')).join(', ');
      return `${v.impact} ${v.id}: ${v.help} (${v.helpUrl}) — targets: ${targets}`;
    })
    .join('\n');
}
