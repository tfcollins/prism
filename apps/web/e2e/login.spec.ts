import { expect, test } from '@playwright/test';

const EMAIL = process.env.PLAYWRIGHT_ADMIN_EMAIL ?? 'admin@example.com';
const PASSWORD = process.env.PLAYWRIGHT_ADMIN_PASSWORD ?? 'change-me-in-prod';

test('login redirects to dashboard and shows projects nav', async ({ page }) => {
  await page.goto('/login');
  await page.fill('input[type=email]', EMAIL);
  await page.fill('input[type=password]', PASSWORD);
  await page.click('button[type=submit]');
  await expect(page.getByRole('heading', { name: /projects/i })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Compare' })).toBeVisible();
});

test('logout clears session and bounces to login', async ({ page }) => {
  await page.goto('/login');
  await page.fill('input[type=email]', EMAIL);
  await page.fill('input[type=password]', PASSWORD);
  await page.click('button[type=submit]');
  await expect(page.getByRole('heading', { name: /projects/i })).toBeVisible();
  await page.click('button:has-text("Sign out")');
  await expect(page).toHaveURL(/\/login$/);
});
