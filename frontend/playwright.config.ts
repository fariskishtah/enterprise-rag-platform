import { defineConfig, devices } from "@playwright/test";

const externalBaseURL = process.env.PLAYWRIGHT_BASE_URL;
const developmentPort = process.env.PLAYWRIGHT_DEV_PORT ?? "5173";
const developmentBaseURL = `http://127.0.0.1:${developmentPort}`;

export default defineConfig({
  testDir: "./e2e",
  timeout: 120_000,
  expect: { timeout: 20_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [["list"], ["html", { outputFolder: "../artifacts/playwright-report", open: "never" }]],
  use: {
    baseURL: externalBaseURL ?? developmentBaseURL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
  webServer: externalBaseURL
    ? undefined
    : [
        {
          command: "cd ../backend && .venv/bin/python -m scripts.run_test_server",
          url: "http://127.0.0.1:8010/api/v1/health",
          timeout: 120_000,
          reuseExistingServer: false,
        },
        {
          command:
            `VITE_API_BASE_URL=http://127.0.0.1:8010/api/v1 npm run dev -- --host 127.0.0.1 --port ${developmentPort}`,
          url: developmentBaseURL,
          timeout: 120_000,
          reuseExistingServer: false,
        },
      ],
});
