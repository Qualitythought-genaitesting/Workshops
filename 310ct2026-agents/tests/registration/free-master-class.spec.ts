// spec: test-plans/qualitythought-test-plan.md
// seed: tests/seed.spec.ts

import { test, expect } from '@playwright/test';

test.describe('Registration, Contact, and Site Resources', () => {
  test('Open and validate the free master class registration prompt', async ({ page }) => {
    // 1. Navigate to the homepage and open the free master class registration prompt.
    await page.goto('https://qualitythought.in/');
    await expect(page).toHaveTitle('Top Software Training Institute | Unlocking Career Potential');

    const scholarshipDismissal = page.getByRole('link', { name: 'No thanks' });
    if (await scholarshipDismissal.isVisible()) {
      await scholarshipDismissal.click();
    }

    const masterClassAction = page.getByRole('link', { name: 'Join a Free Master Class' });
    await expect(masterClassAction).toBeVisible();
    await masterClassAction.click();

    const registrationForm = page.getByRole('form', { name: 'New Form' });
    const fullName = page.getByRole('textbox', { name: 'Full Name' });
    const email = page.getByRole('textbox', { name: 'Email address' });
    const phone = page.getByRole('textbox', { name: 'Phone Number' });
    const course = page.getByRole('combobox', { name: 'Interested Course' });
    const reserveSeat = page.getByRole('button', { name: 'Reserve my seat' });

    await expect(page).toHaveURL('https://qualitythought.in/');
    await expect(page.getByText('Join a Free Master Class.', { exact: true })).toBeVisible();
    await expect(page.getByText('Pick a course and share your details', { exact: false })).toBeVisible();
    await expect(registrationForm).toBeVisible();
    await expect(fullName).toBeVisible();
    await expect(email).toBeVisible();
    await expect(phone).toBeVisible();
    await expect(course).toBeVisible();
    await expect(reserveSeat).toBeVisible();

    // 2. Submit the form empty, then verify malformed email and phone values are rejected and retained.
    await reserveSeat.click();
    await expect(fullName).toBeFocused();
    await expect(fullName).toHaveValue('');

    await fullName.fill('Playwright Test');
    await email.fill('not-an-email');
    await phone.fill('12');
    await reserveSeat.click();

    await expect(page.getByRole('alert')).toContainText('too short');
    await expect(fullName).toHaveValue('Playwright Test');
    await expect(email).toHaveValue('not-an-email');
    await expect(phone).toHaveValue('12');
    await expect(registrationForm).toBeVisible();
    await expect(page).toHaveURL('https://qualitythought.in/');

    // 3. Do not submit valid details to the live form because that could create a real lead or trigger external contact.

    // 4. Close the popup and reopen it from the hero action.
    await page.getByRole('button', { name: 'Close' }).click();
    await expect(registrationForm).toBeHidden();
    await expect(masterClassAction).toBeVisible();
    await masterClassAction.click();
    await expect(registrationForm).toBeVisible();
    await expect(page.getByText('Join a Free Master Class.', { exact: true })).toBeVisible();
  });
});
