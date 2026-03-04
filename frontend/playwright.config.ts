import { defineConfig, devices } from '@playwright/test';

const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? 'http://localhost:3000';

function isLocalUrl(url: string): boolean {
  try {
    const u = new URL(url);
    return u.hostname === 'localhost' || u.hostname === '127.0.0.1';
  } catch {
    return false;
  }
}

const shouldStartWebServer = isLocalUrl(baseURL);
const baseUrlObj = new URL(baseURL);
const basePort = baseUrlObj.port ? Number(baseUrlObj.port) : 3000;

/**
 * Read environment variables from file.
 * https://github.com/motdotla/dotenv
 */
// import dotenv from 'dotenv';
// import path from 'path';
// dotenv.config({ path: path.resolve(__dirname, '.env') });

/**
 * See https://playwright.dev/docs/test-configuration.
 */
export default defineConfig({
  testDir: './e2e',
  /* Run tests in files in parallel */
  fullyParallel: true,
  /* Fail the build on CI if you accidentally left test.only in the source code. */
  forbidOnly: !!process.env.CI,
  /* Retry on CI only */
  retries: process.env.CI ? 2 : 0,
  /* Opt out of parallel tests on CI. */
  workers: process.env.CI ? 1 : undefined,
  /* Reporter to use. See https://playwright.dev/docs/test-reporters */
  reporter: 'html',
  /* Shared settings for all the projects below. See https://playwright.dev/docs/api/class-testoptions. */
  use: {
    /* Base URL to use in actions like `await page.goto('')`. */
    baseURL,

    // Keep e2e assertions stable across machines (avoid accept-language drift into non-English locales).
    locale: 'en-US',

    /* Collect trace when retrying the failed test. See https://playwright.dev/docs/trace-viewer */
    trace: 'on-first-retry',
  },

  /* Configure projects for major browsers */
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },

    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
    },

    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'] },
    },

    /* Test against mobile viewports. */
    // {
    //   name: 'Mobile Chrome',
    //   use: { ...devices['Pixel 5'] },
    // },
    // {
    //   name: 'Mobile Safari',
    //   use: { ...devices['iPhone 12'] },
    // },

    /* Test against branded browsers. */
    // {
    //   name: 'Microsoft Edge',
    //   use: { ...devices['Desktop Edge'], channel: 'msedge' },
    // },
    // {
    //   name: 'Google Chrome',
    //   use: { ...devices['Desktop Chrome'], channel: 'chrome' },
    // },
  ],

  /**
   * Local DX: make `npm run test:e2e` work without manually starting the app.
   *
   * If baseURL points at localhost, we start (or reuse) a local Next server.
   * If baseURL points at a non-local host (e.g. Docker Compose `http://frontend:3000`),
   * we assume a server is already running and skip starting one here.
   */
  webServer: shouldStartWebServer
    ? {
        command: process.env.CI
          ? `npm run build && npm run start -- -p ${basePort} -H 127.0.0.1`
          : `npm run dev -- -p ${basePort} -H 127.0.0.1`,
        // /login does not require backend connectivity (AuthBootstrap skips it),
        // so it is a safe readiness probe for smoke tests.
        url: new URL('/login', baseURL).toString(),
        reuseExistingServer: !process.env.CI,
        timeout: 120_000,
      }
    : undefined,
});
