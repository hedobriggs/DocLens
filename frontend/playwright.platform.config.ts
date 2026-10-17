import { defineConfig } from "@playwright/test";
import { randomBytes } from "node:crypto";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
process.env.PLATFORM_FIXTURE_PASSWORD ||= randomBytes(24).toString("hex");
process.env.PLATFORM_BROWSER_FIXTURE_DIR ||= mkdtempSync(join(tmpdir(), "doclens-m1-browser-"));
export default defineConfig({
  testDir: "./e2e-platform", workers: 1,
  use: { baseURL: "http://127.0.0.1:3200", launchOptions: { executablePath: process.env.CHROMIUM_PATH || "/usr/bin/chromium", args: ["--no-sandbox"] } },
  webServer: { command: "exec ../backend/.venv/bin/python ../tests/milestone1/browser_server.py", url: "http://127.0.0.1:3200/workspaces", reuseExistingServer: false, gracefulShutdown: { signal: "SIGTERM", timeout: 15000 }, timeout: 120000 },
});
