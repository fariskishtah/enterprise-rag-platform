import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 120_000,
  expect: { timeout: 20_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [["list"], ["html", { outputFolder: "../artifacts/playwright-report", open: "never" }]],
  use: {
    baseURL: "http://127.0.0.1:5173",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
  webServer: [
    {
      command: "cd ../backend && .venv/bin/python -m scripts.run_test_server",
      url: "http://127.0.0.1:8010/api/v1/health",
      timeout: 120_000,
      reuseExistingServer: false,
    },
    {
      command:
        "VITE_API_BASE_URL=http://127.0.0.1:8010/api/v1 npm run dev -- --host 127.0.0.1",
      url: "http://127.0.0.1:5173",
      timeout: 120_000,
      reuseExistingServer: false,
    },
  ],
});
