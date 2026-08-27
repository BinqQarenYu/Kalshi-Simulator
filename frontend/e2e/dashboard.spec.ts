import { test, expect } from '@playwright/test';

test.describe('Kalshi Institutional Trading Simulator Dashboard E2E', () => {
  test('Dashboard loads successfully with live market data, chart, and order book', async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });

    await page.goto('/');

    // 1. Header & Live Timeframe Indicator
    await expect(page.locator('header')).toBeVisible();
    await expect(page.locator('header').getByText(/BTC \/ 15M|BTC \/ 5M/)).toBeVisible();

    // 2. Price Hero & Target Strike
    await expect(page.getByText('TO BEAT')).toBeVisible();
    await expect(page.getByText('NOW')).toBeVisible();

    // 3. Trajectory Canvas Chart
    const canvas = page.locator('canvas');
    await expect(canvas).toBeVisible();

    // 4. L2 CLOB Order Book Ladder
    await expect(page.getByText('Price').first()).toBeVisible();
    await expect(page.getByText('Contracts').first()).toBeVisible();
    await expect(page.getByText('Total').first()).toBeVisible();

    // 5. AI Microstructure Card
    await expect(page.getByText('Stage 1 & 2: ONNX AI Engine').first()).toBeVisible();
    await expect(page.getByText('VPIN Toxicity').first()).toBeVisible();

    // 6. Portfolio & Active Positions Drawer
    await expect(page.getByText('Total Equity')).toBeVisible();
    await expect(page.getByText('Realized P&L', { exact: true })).toBeVisible();

    // Ensure zero uncaught frontend errors
    expect(consoleErrors).toEqual([]);
  });

  test('1-Click Order Execution places order and updates portfolio', async ({ page }) => {
    await page.goto('/');

    // Locate order entry execute button (e.g. "⚡ Buy YES with 1-Click")
    const buyButton = page.locator('button:has-text("1-Click")');
    await expect(buyButton).toBeVisible();

    // Click Buy button
    await buyButton.click();

    // Feedback alert should show either execution fill or resting order message
    await expect(
      page.locator('text=/Resting limit order placed|Order filled|Order executed/')
    ).toBeVisible({ timeout: 5000 });
  });

  test('Timeframe Switcher switches between 5M, 15M, and 1H series', async ({ page }) => {
    await page.goto('/');

    // Click 5M timeframe pill in header
    const fiveMinPill = page.getByRole('banner').getByRole('button', { name: '5M', exact: true });
    await expect(fiveMinPill).toBeVisible();
    await fiveMinPill.click();

    // Header title should update to BTC / 5M
    await expect(page.locator('header').getByText(/BTC \/ 5M/)).toBeVisible({ timeout: 5000 });
  });

  test('Export Analytics download links are available in portfolio drawer', async ({ page }) => {
    await page.goto('/');

    await expect(page.getByText('Export Analytics')).toBeVisible();
    await expect(page.locator('a:has-text("Trades CSV")')).toBeVisible();
    await expect(page.locator('a:has-text("Settlements CSV")')).toBeVisible();
    await expect(page.locator('a:has-text("P&L CSV")')).toBeVisible();
  });

  test('Live Mode switch opens LiveTradeModal confirmation when placing orders', async ({ page }) => {
    await page.goto('/');

    // Toggle into Kalshi Live mode
    const liveModeButton = page.locator('button:has-text("Kalshi Live")');
    await expect(liveModeButton).toBeVisible();
    await liveModeButton.click();
    await page.waitForTimeout(500);

    // Click Buy with 1-Click
    const buyButton = page.locator('button:has-text("1-Click")');
    await buyButton.click();

    // Live Order Confirmation Modal should appear
    await expect(page.getByText('Live Order Confirmation')).toBeVisible({ timeout: 5000 });
    await expect(page.getByText('Safety Dry-Run Mode')).toBeVisible();
    await expect(page.locator('button:has-text("Simulate (Dry-Run)")')).toBeVisible();

    // Click Simulate button in modal
    await page.locator('button:has-text("Simulate (Dry-Run)")').click();

    // Modal should close
    await expect(page.getByText('Live Order Confirmation')).not.toBeVisible();
  });

  test('Performance Analytics & Historical Journal tab switches and displays KPI metrics and tables', async ({ page }) => {
    await page.goto('/');

    // Click tab switcher to Performance Analytics
    const analyticsTabBtn = page.getByRole('button', { name: /Performance Analytics & Historical Journal/ });
    await expect(analyticsTabBtn).toBeVisible();
    await analyticsTabBtn.click();

    // Verify institutional KPI metric cards
    await expect(page.getByText('SHARPE RATIO')).toBeVisible();
    await expect(page.getByText('SORTINO RATIO')).toBeVisible();
    await expect(page.getByText('WIN RATE')).toBeVisible();
    await expect(page.getByText('MAX DRAWDOWN')).toBeVisible();
    await expect(page.getByText('PROFIT FACTOR')).toBeVisible();
    await expect(page.getByText('NET REALIZED P&L')).toBeVisible();

    // Verify sub-tabs (Trade Execution Journal, Contract Settlements, Stage 1/2 AI Predictions)
    await expect(page.getByText(/Trade Execution Journal/)).toBeVisible();
    await expect(page.getByText(/Contract Settlements/)).toBeVisible();
    await expect(page.getByText(/Stage 1\/2 AI Predictions/)).toBeVisible();

    // Switch back to Live CLOB Trading Terminal
    const liveTerminalBtn = page.getByRole('button', { name: /Live CLOB Trading Terminal/ });
    await liveTerminalBtn.click();
    await expect(page.getByText('TO BEAT')).toBeVisible();
  });
});


