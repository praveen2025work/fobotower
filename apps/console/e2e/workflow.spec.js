import { expect, test } from '@playwright/test';

const API = 'http://localhost:8101';

test('a draft goes live when a second controller approves it, and only new runs use it', async ({
  page,
  request,
}) => {
  await page.goto('/fobo');
  await expect(page.getByText('FOBO Controller')).toBeVisible({ timeout: 120_000 });

  // Loading the board ran R-1055's investigation on v1.
  await page.getByRole('button', { name: 'Workflow', exact: true }).click();
  await expect(page.getByText('Workflow v1', { exact: true })).toBeVisible();

  // praveen drafts a 90-day lookback.
  await page.getByRole('button', { name: 'New draft' }).click();
  await page.getByLabel('priors lookback days').fill('90');
  await page.getByLabel('Change note').fill('Lookback 180 to 90 days');
  await expect(page.getByText(/^Valid/)).toBeVisible();
  await page.getByRole('button', { name: 'Save draft' }).click();
  await expect(page.getByRole('button', { name: '1 draft awaiting approval' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Approve', exact: true })).toBeDisabled();

  // asha approves it.
  await page.getByLabel('Act as').selectOption('asha');
  await page.getByRole('button', { name: /^v2/ }).click();
  await page.getByRole('button', { name: 'Approve', exact: true }).click();
  const dialog = page.getByRole('dialog');
  for (const box of await dialog.getByRole('checkbox').all()) await box.check();
  await dialog.getByRole('button', { name: 'Approve and activate' }).click();
  await expect(page.getByText('Workflow v2', { exact: true })).toBeVisible();

  // A run that starts now uses v2.
  await request.get(`${API}/api/recs/R-2031`, { timeout: 120_000 });
  const fresh = await (await request.get(`${API}/api/recs/R-2031/trace`)).json();
  expect(fresh.trace.workflow_version).toBe(2);

  // The run that started on v1 keeps it.
  await page.getByRole('button', { name: 'Pipeline', exact: true }).click();
  // R-1055's current step is Human Sign-off, so RecDetail defaults to the
  // "Drafted adjustments" pane below the 2xl breakpoint; the Graph run
  // button lives in the "Helix session" pane.
  await page.getByRole('tab', { name: 'Helix session' }).click();
  await page.getByRole('button', { name: /Graph run/ }).click();
  await expect(page.getByText(/workflow v1 ·/)).toBeVisible();
});
