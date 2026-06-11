import { expect, test } from '@playwright/test';

import { expectNoSeriousAxeViolations } from './helpers/axe';

const EMAIL = process.env.PLAYWRIGHT_ADMIN_EMAIL ?? 'admin@example.com';
const PASSWORD = process.env.PLAYWRIGHT_ADMIN_PASSWORD ?? 'analog';

test('login redirects to the overview and shows nav', async ({ page }) => {
  await page.goto('/login');
  await page.fill('input[type=email]', EMAIL);
  await page.fill('input[type=password]', PASSWORD);
  await page.click('button[type=submit]');
  await expect(page.getByRole('heading', { name: /overview/i })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Projects' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Compare' })).toBeVisible();
  await expectNoSeriousAxeViolations(page);
});

test('logout clears session and bounces to login', async ({ page }) => {
  await page.goto('/login');
  await page.fill('input[type=email]', EMAIL);
  await page.fill('input[type=password]', PASSWORD);
  await page.click('button[type=submit]');
  await expect(page.getByRole('heading', { name: /overview/i })).toBeVisible();
  await page.click('button:has-text("Sign out")');
  await expect(page).toHaveURL(/\/login$/);
});
