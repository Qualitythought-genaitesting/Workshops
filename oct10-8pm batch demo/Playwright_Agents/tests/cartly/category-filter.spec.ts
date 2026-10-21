import { test, expect } from '@playwright/test';

test.describe('Landing page, navigation, and catalog categories', () => {
  test('Filter catalog by a populated category and return to all categories', async ({ page }) => {
    // 1. Start with a clean browser context, navigate to root, and note initially visible catalog products.
    await page.goto('https://aisle-and-smile.lovable.app/');
    const categoryNavigation = page.getByRole('navigation', { name: 'Product categories' });
    await expect(categoryNavigation).toBeVisible();
    await expect(page.getByRole('button', { name: 'SoundWave Pro Wireless Headphones', exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Everyday Comfort Running Shoes', exact: true })).toBeVisible();

    // 2. Activate Electronics in Product categories.
    const electronicsButton = categoryNavigation.getByRole('button', { name: 'Electronics', exact: true });
    await electronicsButton.click();
    await expect(electronicsButton).toHaveAttribute('aria-pressed', 'true');
    await expect(page.getByRole('heading', { name: /Electronics/ })).toContainText('3 products');
    const products = page.getByRole('article');
    await expect(products).toHaveCount(3);
    await expect(page.getByRole('button', { name: 'SoundWave Pro Wireless Headphones', exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Pulse Smartwatch · AMOLED Display', exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Focus Mirrorless Camera with Lens', exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Everyday Comfort Running Shoes', exact: true })).toHaveCount(0);

    // 3. Activate All categories.
    const allCategoriesButton = categoryNavigation.getByRole('button', { name: 'All categories', exact: true });
    await allCategoriesButton.click();
    await expect(allCategoriesButton).toHaveAttribute('aria-pressed', 'true');
    await expect(page.getByRole('region', { name: 'Featured offers' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'SoundWave Pro Wireless Headphones', exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Everyday Comfort Running Shoes', exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Stainless Steel Electric Kettle · 1.7L', exact: true })).toBeVisible();
  });
});
