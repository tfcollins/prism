import { expect, test } from '@playwright/test';

import { expectNoSeriousAxeViolations } from './helpers/axe';

const EMAIL = process.env.PLAYWRIGHT_ADMIN_EMAIL ?? 'admin@example.com';
const PASSWORD = process.env.PLAYWRIGHT_ADMIN_PASSWORD ?? 'analog';

async function login(page: import('@playwright/test').Page) {
  await page.goto('/login');
  await page.fill('input[type=email]', EMAIL);
  await page.fill('input[type=password]', PASSWORD);
  await page.click('button[type=submit]');
  // Login lands on the overview ("/"); wait until we're off the login page.
  await page.waitForURL((url) => url.pathname === '/');
}

test('select two runs and open the compare page', async ({ page }) => {
  await login(page);
  await page.click('a[href="/projects/audio"]');
  await page.waitForSelector('tbody tr');

  // Select the first two runs.
  const rows = page.locator('tbody tr');
  await expect(rows).not.toHaveCount(0);
  await rows.nth(0).locator('label[data-scope="checkbox"]').click();
  await rows.nth(1).locator('label[data-scope="checkbox"]').click();

  // Axe check 1: runs table is fully rendered.
  await expectNoSeriousAxeViolations(page);

  // Buttons appear once selected: Export PDF (combined report) + Compare.
  const compareBtn = page.locator('button:has-text("Compare 2 runs")');
  await expect(compareBtn).toBeVisible();
  // The dashboard Export PDF is the COMBINED test-results report, not a comparison.
  const dashPdf = page.getByRole('link', { name: /export pdf/i });
  await expect(dashPdf).toBeVisible();
  await expect(dashPdf).toHaveAttribute('href', /\/api\/v1\/runs\/report\.pdf\?runs=/);
  await compareBtn.click();

  await page.waitForURL(/\/compare\?runs=/);

  // Compare page header + diff table render.
  await expect(page.getByRole('heading', { name: /^compare$/i })).toBeVisible();
  await expect(page.getByText(/pass rate/i)).toBeVisible();
  await expect(page.locator('table')).toBeVisible();

  // Export PDF link points at the multi-run report for the selected runs.
  const pdfLink = page.getByRole('link', { name: /export pdf/i });
  await expect(pdfLink).toBeVisible();
  await expect(pdfLink).toHaveAttribute('href', /\/api\/v1\/compare\/report\.pdf\?runs=/);

  // Axe check 2: compare panel / overlay UI is visible.
  await expectNoSeriousAxeViolations(page);
});
