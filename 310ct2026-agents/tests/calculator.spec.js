// @ts-check
const { test, expect } = require('@playwright/test');
const path = require('node:path');
const { pathToFileURL } = require('node:url');

const calculatorUrl = pathToFileURL(path.resolve(__dirname, '../index.html')).href;

test.beforeEach(async ({ page }) => {
  await page.goto(calculatorUrl);
});

test('calculates basic operations and chained operations', async ({ page }) => {
  const display = page.locator('[data-display]');

  await page.getByRole('button', { name: '1', exact: true }).click();
  await page.getByRole('button', { name: '2', exact: true }).click();
  await page.getByRole('button', { name: 'Add' }).click();
  await page.getByRole('button', { name: '7', exact: true }).click();
  await page.getByRole('button', { name: 'Equals' }).click();
  await expect(display).toHaveText('19');

  await page.getByRole('button', { name: 'Multiply' }).click();
  await page.getByRole('button', { name: '3', exact: true }).click();
  await page.getByRole('button', { name: 'Equals' }).click();
  await expect(display).toHaveText('57');
});

test('supports decimal input, sign toggle, percent, and backspace', async ({ page }) => {
  const display = page.locator('[data-display]');

  await page.getByRole('button', { name: '1', exact: true }).click();
  await page.getByRole('button', { name: 'Decimal point' }).click();
  await page.getByRole('button', { name: '5', exact: true }).click();
  await page.getByRole('button', { name: 'Toggle sign' }).click();
  await expect(display).toHaveText('-1.5');
  await page.getByRole('button', { name: 'Percent' }).click();
  await expect(display).toHaveText('-0.015');
  await page.getByRole('button', { name: 'Delete last digit' }).click();
  await expect(display).toHaveText('-0.01');
});

test('supports keyboard input and reports division by zero', async ({ page }) => {
  const display = page.locator('[data-display]');

  await page.keyboard.type('8/0');
  await page.keyboard.press('Enter');
  await expect(display).toHaveText('Error');

  await page.keyboard.press('Escape');
  await page.keyboard.type('6*7');
  await page.keyboard.press('Enter');
  await expect(display).toHaveText('42');
});
