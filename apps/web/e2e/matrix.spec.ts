import { expect, test } from '@playwright/test';

import { expectNoSeriousAxeViolations } from './helpers/axe';

const EMAIL = process.env.PLAYWRIGHT_ADMIN_EMAIL ?? 'admin@example.com';
const PASSWORD = process.env.PLAYWRIGHT_ADMIN_PASSWORD ?? 'change-me-in-prod';

async function login(page: import('@playwright/test').Page) {
  await page.goto('/login');
  await page.fill('input[type=email]', EMAIL);
  await page.fill('input[type=password]', PASSWORD);
  await page.click('button[type=submit]');
  // Login lands on the overview ("/"); wait until we're off the login page.
  await page.waitForURL((url) => url.pathname === '/');
}

test('enable matrix dashboard, view grid, and check kiosk', async ({ page }) => {
  await login(page);

  // Enable via the settings card on the Tokens page.
  await page.goto('/tokens');
  // Enable via the settings card. Idempotent: if already enabled on a re-run,
  // the "Enable" button is absent, so we skip the toggle and just verify nav below.
  const enableBtn = page.locator('button:has-text("Enable matrix dashboard")');
  if (await enableBtn.count()) {
    await enableBtn.click();
    await expect(page.getByText('Currently enabled.')).toBeVisible();
  }

  // Nav entry now appears; open the matrix.
  // Wait for the Sidebar to re-render with the Matrix nav entry after enabling.
  await expect(page.locator('a[href="/matrix"]')).toBeVisible();
  await page.click('a[href="/matrix"]');
  await page.waitForURL('/matrix');
  await expect(page.getByRole('heading', { name: /^matrix/i })).toBeVisible();
  await expectNoSeriousAxeViolations(page);

  // Kiosk route renders without the sidebar nav.
  await page.goto('/kiosk/matrix?scope=global');
  await expect(page.getByText(/Kuiper Linux/i)).toBeVisible();
  await expect(page.locator('a[href="/tokens"]')).toHaveCount(0); // no sidebar
  await expectNoSeriousAxeViolations(page);
});
