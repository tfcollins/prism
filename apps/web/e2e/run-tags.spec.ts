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

test('add, edit, and delete a run tag from the run detail page', async ({ page }) => {
  await login(page);

  // Open the first run in the seeded `audio` project.
  await page.goto('/projects/audio');
  await page.waitForSelector('tbody tr');
  await page.locator('tbody tr a').first().click();
  await page.waitForURL(/\/runs\//);

  // The Tags editor lives in the details panel (rightOpen defaults to true). The
  // panel only renders once the run-detail fetch resolves, which can lag the
  // client-side navigation — so a bare `isVisible()` here races the load and, if
  // it loses, wrongly tries to click a "show details" toggle that doesn't exist
  // on an already-open panel (30s timeout). Wait for the field (or the toggle, if
  // the panel is collapsed) to render before deciding whether to open it.
  const addKey = page.getByLabel('new tag key');
  const showDetails = page.getByText(/show details/);
  await expect(addKey.or(showDetails).first()).toBeVisible({ timeout: 15000 });
  if (!(await addKey.isVisible())) {
    await showDetails.click();
  }
  await expect(addKey).toBeVisible();

  // Add a tag.
  await addKey.fill('e2e_tag');
  await page.getByLabel('new tag value').fill('e2e_val_1');
  await page.getByRole('button', { name: 'Add tag' }).click();
  await expect(page.getByText('e2e_tag')).toBeVisible();
  await expectNoSeriousAxeViolations(page);

  // Edit its value.
  await page.getByRole('button', { name: 'Edit e2e_tag' }).click();
  await page.getByLabel('edit value for e2e_tag').fill('e2e_val_2');
  await page.getByRole('button', { name: 'Save e2e_tag' }).click();
  await expect(page.getByText('e2e_val_2')).toBeVisible();

  // Delete it (two-step confirm).
  await page.getByRole('button', { name: 'Delete e2e_tag' }).click();
  await page.getByRole('button', { name: 'Confirm delete e2e_tag' }).click();
  await expect(page.getByText('e2e_tag')).toHaveCount(0);
  await expectNoSeriousAxeViolations(page);
});
