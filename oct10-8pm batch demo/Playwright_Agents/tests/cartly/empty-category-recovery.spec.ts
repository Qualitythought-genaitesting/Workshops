import { test, expect } from '@playwright/test';

test.describe('Landing page, navigation, and catalog categories', () => {
  test('Show empty-category state and recover to all products', async ({ page }) => {
    // 1. Start from a clean browser context and open the root URL.
    await page.goto('https://aisle-and-smile.lovable.app/');
    const categoryNavigation = page.getByRole('navigation', { name: 'Product categories' });
    await expect(categoryNavigation).toBeVisible();

    // 2. Select the Mobiles category to check the zero-product state.
    const mobilesButton = categoryNavigation.getByRole('button', { name: 'Mobiles', exact: true });
    await mobilesButton.click();
    await expect(mobilesButton).toHaveAttribute('aria-pressed', 'true');
    await expect(page.getByRole('heading', { name: /Mobiles/ })).toContainText('0 products');
    await expect(page.getByRole('heading', { name: 'No products found' })).toBeVisible();
    await expect(page.getByText('Try another search or browse all categories.')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Browse all products' })).toBeVisible();

    // 3. Activate Browse all products from the empty category state.
    await page.getByRole('button', { name: 'Browse all products' }).click();
    const allCategoriesButton = categoryNavigation.getByRole('button', { name: 'All categories', exact: true });
    await expect(allCategoriesButton).toHaveAttribute('aria-pressed', 'true');
    await expect(page.getByRole('heading', { name: 'Good tech. Great prices.' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'SoundWave Pro Wireless Headphones', exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Everyday Comfort Running Shoes', exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Stainless Steel Electric Kettle · 1.7L', exact: true })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'No products found' })).toHaveCount(0);
  });
});
