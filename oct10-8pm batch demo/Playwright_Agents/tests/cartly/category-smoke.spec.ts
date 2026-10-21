import { test, expect } from '@playwright/test';

test.describe('Landing page, navigation, and catalog categories', () => {
  test('Verify each remaining category has a consistent result state', async ({ page }) => {
    const pageErrors: string[] = [];
    page.on('pageerror', error => pageErrors.push(error.message));

    // 1. Start from a clean browser context and open the root URL.
    await page.goto('https://aisle-and-smile.lovable.app/');
    const categoryNavigation = page.getByRole('navigation', { name: 'Product categories' });
    await expect(categoryNavigation).toBeVisible();

    // 2. Select Fashion, Home & Living, Appliances, and Beauty & More; inspect each result state.
    const categories = [
      { name: 'Fashion', count: 2, products: ['Everyday Comfort Running Shoes', 'Urban Everyday Backpack · 25L'] },
      { name: 'Home & Living', count: 0, products: [] },
      { name: 'Appliances', count: 1, products: ['Stainless Steel Electric Kettle · 1.7L'] },
      { name: 'Beauty & More', count: 0, products: [] },
    ];

    for (const category of categories) {
      const categoryButton = categoryNavigation.getByRole('button', { name: category.name, exact: true });
      await categoryButton.click();
      await expect(categoryButton).toHaveAttribute('aria-pressed', 'true');
      await expect(page.getByRole('heading', { name: new RegExp(category.name) })).toContainText(`${category.count} products`);

      await expect(page.getByRole('article')).toHaveCount(category.count);
      for (const productName of category.products) {
        await expect(page.getByRole('button', { name: productName, exact: true })).toBeVisible();
      }

      if (category.count === 0) {
        await expect(page.getByRole('heading', { name: 'No products found' })).toBeVisible();
        await expect(page.getByText('Try another search or browse all categories.')).toBeVisible();
        await expect(page.getByRole('button', { name: 'Browse all products' })).toBeVisible();
      } else {
        await expect(page.getByRole('heading', { name: 'No products found' })).toHaveCount(0);
      }
    }

    await expect(pageErrors, 'Category changes should not raise uncaught JavaScript errors').toEqual([]);
  });
});
