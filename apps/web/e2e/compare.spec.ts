import { expect, test } from '@playwright/test';
import { expectNoSeriousAxeViolations } from './helpers/axe';

const EMAIL = process.env.PLAYWRIGHT_ADMIN_EMAIL ?? 'admin@example.com';
const PASSWORD = process.env.PLAYWRIGHT_ADMIN_PASSWORD ?? 'change-me-in-prod';

async function login(page: import('@playwright/test').Page) {
  await page.goto('/login');
  await page.fill('input[type=email]', EMAIL);
  await page.fill('input[type=password]', PASSWORD);
  await page.click('button[type=submit]');
  await page.waitForURL(/\/projects$/);
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

  // Button appears once ≥2 selected.
  const compareBtn = page.locator('button:has-text("Compare 2 runs")');
  await expect(compareBtn).toBeVisible();
  await compareBtn.click();

  await page.waitForURL(/\/compare\?runs=/);

  // Compare page header + diff table render.
  await expect(page.getByRole('heading', { name: /^compare$/i })).toBeVisible();
  await expect(page.getByText(/pass rate/i)).toBeVisible();
  await expect(page.locator('table')).toBeVisible();

  // Axe check 2: compare panel / overlay UI is visible.
  await expectNoSeriousAxeViolations(page);
});
