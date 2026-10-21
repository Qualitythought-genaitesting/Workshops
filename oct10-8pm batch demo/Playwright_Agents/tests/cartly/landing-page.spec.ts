import { test, expect } from '@playwright/test';

test.describe('Landing page, navigation, and catalog categories', () => {
  test('Load landing page and verify primary content', async ({ page }) => {
    const pageErrors: string[] = [];
    const failedAppRequests: string[] = [];
    const appOrigin = 'https://aisle-and-smile.lovable.app';

    page.on('pageerror', error => pageErrors.push(error.message));
    page.on('requestfailed', request => {
      if (new URL(request.url()).origin === appOrigin) {
        failedAppRequests.push(`${request.method()} ${request.url()}: ${request.failure()?.errorText ?? 'request failed'}`);
      }
    });

    // 1. Start from a clean browser context and navigate to the application root URL.
    await page.goto(`${appOrigin}/`);
    await expect(page).toHaveURL(/^https:\/\//);
    await expect(page).toHaveTitle('Cartly — Everyday favourites, extraordinary finds');

    // 2. Inspect the header, primary category navigation, main content, and footer using the accessibility tree.
    await expect(page.getByRole('link', { name: 'Cartly home' })).toBeVisible();
    await expect(page.getByRole('textbox', { name: 'Search products' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Wishlist' })).toBeVisible();

    const categories = page.getByRole('navigation', { name: 'Product categories' });
    await expect(categories).toBeVisible();
    for (const category of [
      'All categories',
      'Electronics',
      'Mobiles',
      'Fashion',
      'Home & Living',
      'Appliances',
      'Beauty & More',
    ]) {
      await expect(categories.getByRole('button', { name: category, exact: true })).toBeVisible();
    }

    await expect(page.getByRole('region', { name: 'Featured offers' })).toBeVisible();
    await expect(page.getByRole('region', { name: 'Collections' })).toBeVisible();
    await expect(page.getByText('Sample collection · Shopping preview', { exact: true })).toBeVisible();

    // 3. Check the initial catalog and featured content after page loading settles.
    await expect(page.getByRole('heading', { name: 'Good tech. Great prices.' })).toBeVisible();
    await expect(page.getByRole('img', { name: 'Blue wireless headphones, smartphone and earbuds' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'SoundWave Pro Wireless Headphones', exact: true })).toBeVisible();
    await expect(page.getByRole('img', { name: 'SoundWave Pro Wireless Headphones' })).toBeVisible();
    await expect(page.getByRole('article').first()).toBeVisible();
    await expect(pageErrors, 'The page should not raise uncaught JavaScript errors').toEqual([]);
    await expect(failedAppRequests, 'Application resources should not fail to load').toEqual([]);
  });
});
