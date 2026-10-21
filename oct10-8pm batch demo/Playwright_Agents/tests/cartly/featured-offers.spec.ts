import { test, expect } from '@playwright/test';

test.describe('Landing page, navigation, and catalog categories', () => {
  test('Navigate featured offers and use the offer call to action', async ({ page }) => {
    // 1. Start from a clean browser context and open the root URL.
    await page.goto('https://aisle-and-smile.lovable.app/');
    const featuredOffers = page.getByRole('region', { name: 'Featured offers' });
    const previousOffer = featuredOffers.getByRole('button', { name: 'Previous offer' });
    const nextOffer = featuredOffers.getByRole('button', { name: 'Next offer' });
    const exploreDeals = featuredOffers.getByRole('button', { name: 'Explore deals' });

    await expect(featuredOffers).toBeVisible();
    await expect(previousOffer).toBeVisible();
    await expect(previousOffer).toBeEnabled();
    await expect(nextOffer).toBeVisible();
    await expect(nextOffer).toBeEnabled();
    await expect(exploreDeals).toBeVisible();

    // 2. Activate Next offer, then Previous offer.
    const offerHeading = featuredOffers.getByRole('heading', { level: 1 });
    const getCurrentOfferHeading = async () => (await offerHeading.textContent())?.replace(/\s+/g, '');
    const initialOfferHeading = await getCurrentOfferHeading();
    await nextOffer.focus();
    await nextOffer.press('Enter');
    await expect.poll(getCurrentOfferHeading).not.toBe(initialOfferHeading);
    const nextOfferHeading = await getCurrentOfferHeading();

    await previousOffer.focus();
    await previousOffer.press('Enter');
    await expect.poll(getCurrentOfferHeading).not.toBe(nextOfferHeading);
    await expect.poll(getCurrentOfferHeading).toBe(initialOfferHeading);

    // 3. Activate Explore deals on the active offer.
    await exploreDeals.click();
    const categoryNavigation = page.getByRole('navigation', { name: 'Product categories' });
    await expect(categoryNavigation.getByRole('button', { name: 'Electronics', exact: true })).toHaveAttribute('aria-pressed', 'true');
    await expect(page.getByRole('heading', { name: /Electronics/ })).toContainText('3 products');
    await expect(page.getByRole('article')).toHaveCount(3);
    await expect(page.getByRole('button', { name: 'SoundWave Pro Wireless Headphones', exact: true })).toBeVisible();
  });
});
