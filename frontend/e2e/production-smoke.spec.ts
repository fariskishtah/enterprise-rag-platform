import { expect, test, type Page } from "@playwright/test";

const productionRun = process.env.PLAYWRIGHT_PRODUCTION === "1";

interface BrowserDiagnostics {
  consoleErrors: string[];
  pageErrors: string[];
  failedRequests: string[];
  failedApiResponses: string[];
  apiRequests: string[];
}

function collectDiagnostics(
  page: Page,
  expectedApiFailures: string[] = [],
): BrowserDiagnostics {
  const diagnostics: BrowserDiagnostics = {
    consoleErrors: [],
    pageErrors: [],
    failedRequests: [],
    failedApiResponses: [],
    apiRequests: [],
  };
  page.on("console", (message) => {
    if (message.type() !== "error") return;
    const location = message.location().url;
    const expectedFailure = expectedApiFailures.some((value) =>
      location.includes(value),
    );
    if (!expectedFailure) diagnostics.consoleErrors.push(message.text());
  });
  page.on("pageerror", (error) => diagnostics.pageErrors.push(error.message));
  page.on("requestfailed", (request) => {
    const failure = request.failure()?.errorText ?? "unknown failure";
    if (failure !== "net::ERR_ABORTED") {
      diagnostics.failedRequests.push(`${request.method()} ${request.url()} (${failure})`);
    }
  });
  page.on("request", (request) => {
    if (new URL(request.url()).pathname.startsWith("/api/v1")) {
      diagnostics.apiRequests.push(request.url());
    }
  });
  page.on("response", (response) => {
    const url = response.url();
    const path = new URL(url).pathname;
    if (
      path.startsWith("/api/v1") &&
      response.status() >= 400 &&
      !expectedApiFailures.some((value) => path.includes(value))
    ) {
      diagnostics.failedApiResponses.push(
        `${response.request().method()} ${url} (${response.status()})`,
      );
    }
  });
  return diagnostics;
}

function expectCleanDiagnostics(diagnostics: BrowserDiagnostics) {
  expect(diagnostics.consoleErrors, "browser console errors").toEqual([]);
  expect(diagnostics.pageErrors, "uncaught browser errors").toEqual([]);
  expect(diagnostics.failedRequests, "failed browser requests").toEqual([]);
  expect(diagnostics.failedApiResponses, "unexpected failed API responses").toEqual([]);
}

test.describe("production container smoke", () => {
  test.skip(!productionRun, "Run with PLAYWRIGHT_PRODUCTION=1 against the Docker container");

  test("serves the SPA, direct routes, static assets, and same-origin APIs", async ({
    page,
  }) => {
    const diagnostics = collectDiagnostics(page, ["/documents/smoke-missing", "/media/smoke-missing"]);
    const routes = [
      "/",
      "/landing",
      "/login",
      "/dashboard",
      "/workspace",
      "/knowledge-bases",
      "/documents",
      "/upload",
      "/chat",
      "/media",
      "/video",
      "/intelligence",
      "/evaluation",
      "/feedback",
      "/templates",
      "/settings",
      "/documents/smoke-missing",
      "/media/smoke-missing",
    ];

    for (const route of routes) {
      const response = await page.goto(route, { waitUntil: "networkidle" });
      expect(response?.status(), `${route} should be served by the SPA`).toBe(200);
      expect(response?.headers()["content-type"]).toContain("text/html");
      await expect(page.locator("main")).toBeVisible();
      await expect(page.locator('[aria-label="Loading workspace"]')).toHaveCount(0);
    }

    const assets = await page.evaluate(() =>
      performance
        .getEntriesByType("resource")
        .map((entry) => entry.name)
        .filter((url) => new URL(url).pathname.startsWith("/assets/")),
    );
    expect(assets.length).toBeGreaterThan(0);
    for (const asset of assets.slice(0, 3)) {
      const response = await page.request.get(asset);
      expect(response.status()).toBe(200);
    }

    expect(diagnostics.apiRequests.length).toBeGreaterThan(0);
    for (const requestUrl of diagnostics.apiRequests) {
      const url = new URL(requestUrl);
      expect(url.origin).toBe(new URL(page.url()).origin);
      expect(url.pathname).toMatch(/^\/api\/v1(?:\/|$)/);
    }
    expectCleanDiagnostics(diagnostics);
  });

  test("every primary navigation destination renders and remains interactive", async ({
    page,
  }) => {
    const diagnostics = collectDiagnostics(page);
    await page.goto("/", { waitUntil: "networkidle" });
    await expect(page.getByRole("heading", { name: /Your knowledge/ })).toBeVisible();

    const destinations = [
      ["Product Showcase", "/landing", "Enterprise Knowledge Intelligence & Grounded QA"],
      ["Overview", "/", /Your knowledge/],
      ["Knowledge", "/knowledge-bases", "Knowledge bases"],
      [
        "Source library",
        "/upload",
        /Bring knowledge into focus\.|Create a knowledge base first/,
      ],
      ["Research chat", "/chat", /Ask with evidence.|No knowledge base available/],
      ["Video intelligence", "/video", /Video intelligence|No video workspace yet/],
      ["Compare & reports", "/intelligence", "Intelligence studio"],
      ["Evaluation", "/evaluation", "Evaluation Dashboard"],
      ["Feedback", "/feedback", "Feedback Analytics"],
      ["Templates", "/templates", "Action Template Library"],
      ["Settings", "/settings", "Model settings"],
    ] as const;

    for (const [title, path, heading] of destinations) {
      await page.getByTitle(title).click();
      await expect(page).toHaveURL(new RegExp(`${path === "/" ? "/?$" : `${path}/?$`}`));
      await expect(
        page.getByRole("heading", {
          name: heading,
          exact: typeof heading === "string",
        }),
      ).toBeVisible();
    }

    await page.goto("/landing");
    await page.getByRole("link", { name: "Launch Workspace" }).click();
    await expect(page).toHaveURL(/\/chat\/?$/);

    await page.goto("/");
    await page
      .getByRole("main")
      .getByRole("link", { name: "Add knowledge", exact: true })
      .click();
    await expect(page).toHaveURL(/\/upload\/?$/);
    await page.goto("/");
    await page.getByRole("main").getByRole("link", { name: "Ask a question" }).click();
    await expect(page).toHaveURL(/\/chat\/?$/);

    await page.goto("/login");
    await page.getByRole("button", { name: /Need an account/ }).click();
    await expect(page.getByRole("heading", { name: "Create Account" })).toBeVisible();
    await page.getByRole("button", { name: /Already have an account/ }).click();
    await expect(page.getByRole("heading", { name: "Enterprise Authentication" })).toBeVisible();
    expectCleanDiagnostics(diagnostics);
  });

  test("primary async actions terminate on both success and failure", async ({ page }) => {
    const diagnostics = collectDiagnostics(page, ["/documents", "/auth/login", "/demo/seed"]);
    const workspaceName = `Production smoke ${Date.now()}`;

    await page.goto("/knowledge-bases");
    await page.getByLabel("Name").fill(workspaceName);
    await page.getByLabel(/Description/).fill("Production navigation validation");
    await page.getByRole("button", { name: "Create knowledge base" }).click();
    const workspaceCard = page.locator(".knowledge-card", { hasText: workspaceName });
    await expect(workspaceCard).toBeVisible();
    await workspaceCard.getByRole("link", { name: "Open workspace" }).click();
    await expect(page.getByRole("heading", { name: "Focused collection" })).toBeVisible();

    await page.getByRole("link", { name: "Add knowledge", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Bring knowledge into focus." })).toBeVisible();
    await page.route("**/api/v1/knowledge-bases/*/documents", async (route) => {
      if (route.request().method() === "POST") {
        await route.fulfill({
          status: 503,
          contentType: "application/json",
          body: JSON.stringify({
            error: { code: "intake_unavailable", message: "Test intake unavailable." },
          }),
        });
      } else {
        await route.continue();
      }
    });
    await page.locator('input[type="file"]').setInputFiles({
      name: "production-smoke.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("Production smoke source"),
    });
    await page.getByRole("button", { name: /Start secure intake/ }).click();
    await expect(page.getByRole("alert")).toContainText("Test intake unavailable.");
    await expect(page.getByRole("button", { name: /Start secure intake/ })).toBeEnabled();
    await page.unroute("**/api/v1/knowledge-bases/*/documents");

    await page.route("**/api/v1/knowledge-bases/*/ask", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          session_id: "smoke-session",
          message_id: "smoke-message",
          answer: "The production request completed.",
          direct_answer: "The production request completed.",
          supporting_explanation: "",
          citations: [],
          retrieved_sources: [],
          verification: {
            status: "supported",
            claim_support: "fully_supported",
            explanation: "Smoke response",
            unsupported_statements: [],
          },
          retrieval_quality: "high",
          confidence: 1,
          support_status: "fully_supported",
          retrieved_chunk_ids: [],
          generation_model: "smoke",
          model_used: "smoke",
          response_time: 1,
          response_time_ms: 1,
          not_found: false,
          output_language: "en",
          created_at: new Date().toISOString(),
          debug: null,
        }),
      });
    });
    await page.goto("/chat");
    const composer = page.getByLabel("Ask a grounded question");
    await composer.fill("Does the production action finish?");
    await page.getByLabel("Ask sources").click();
    await expect(page.getByText("The production request completed.")).toBeVisible();
    await expect(composer).toBeEnabled();
    await composer.fill("A follow-up remains usable.");
    await expect(page.getByLabel("Ask sources")).toBeEnabled();

    await page.route("**/api/v1/auth/login", (route) =>
      route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({
          error: { code: "invalid_credentials", message: "Incorrect email or password." },
        }),
      }),
    );
    await page.goto("/login");
    await page.getByLabel("Email Address").fill("smoke@example.com");
    await page.getByLabel("Password").fill("invalid-password");
    await page.getByRole("button", { name: "Sign In" }).click();
    await expect(page.getByText("Incorrect email or password.")).toBeVisible();
    await expect(page.getByRole("button", { name: "Sign In" })).toBeEnabled();
    expect(await page.evaluate(() => localStorage.getItem("token"))).toBeNull();
    await expect(page).toHaveURL(/\/login\/?$/);

    await page.route("**/api/v1/demo/seed", (route) =>
      route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({
          error: { code: "seed_unavailable", message: "Demo seed is unavailable." },
        }),
      }),
    );
    await page.goto("/landing");
    await page.getByRole("button", { name: "Load Demo Workspace" }).click();
    await expect(page.getByText("Demo seed is unavailable.")).toBeVisible();
    await expect(page.getByRole("button", { name: "Load Demo Workspace" })).toBeEnabled();
    await expect(page).toHaveURL(/\/landing\/?$/);

    expectCleanDiagnostics(diagnostics);
  });

  test("Arabic controls, RTL answers, and YouTube auth errors terminate cleanly", async ({
    page,
  }) => {
    const diagnostics = collectDiagnostics(page);
    const workspace = await page.request.post("/api/v1/knowledge-bases", {
      data: {
        name: `Arabic production smoke ${Date.now()}`,
        description: "Multilingual production validation",
      },
    });
    expect(workspace.status()).toBe(201);
    const knowledgeBase = (await workspace.json()) as { id: string };

    let askPayload: Record<string, unknown> | null = null;
    await page.route("**/api/v1/knowledge-bases/*/ask", async (route) => {
      askPayload = route.request().postDataJSON() as Record<string, unknown>;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          session_id: "arabic-smoke-session",
          message_id: "arabic-smoke-message",
          answer: "يسمح بالعمل عن بُعد ثلاثة أيام أسبوعياً.",
          direct_answer: "ثلاثة أيام أسبوعياً.",
          supporting_explanation: "",
          citations: [],
          retrieved_sources: [],
          verification: {
            status: "supported",
            claim_support: "fully_supported",
            explanation: "الإجابة مدعومة بالمصدر.",
            unsupported_statements: [],
          },
          retrieval_quality: "high",
          confidence: 1,
          support_status: "fully_supported",
          retrieved_chunk_ids: [],
          generation_model: "smoke",
          model_used: "smoke",
          response_time: 1,
          response_time_ms: 1,
          not_found: false,
          output_language: "ar",
          created_at: new Date().toISOString(),
          debug: null,
        }),
      });
    });
    await page.goto(`/chat?knowledgeBase=${knowledgeBase.id}`);
    await page.getByLabel("Answer language").selectOption("ar");
    await page.getByLabel("Ask a grounded question").fill("ما سياسة العمل عن بُعد؟");
    await page.getByLabel("Ask sources").click();
    const answer = page.getByText("يسمح بالعمل عن بُعد ثلاثة أيام أسبوعياً.");
    await expect(answer).toBeVisible();
    await expect(answer).toHaveAttribute("dir", "rtl");
    expect(askPayload?.output_language).toBe("ar");

    const terminalMessage =
      "YouTube requires authenticated cookies on this server. Update the server cookie file or upload the media file directly.";
    await page.route("**/api/v1/knowledge-bases/*/media/from-url", (route) =>
      route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({
          id: "yt-auth-smoke",
          knowledge_base_id: knowledgeBase.id,
          title: "YouTube auth smoke",
          status: "validating",
          status_message: "Validating media source.",
        }),
      }),
    );
    await page.route("**/api/v1/media/yt-auth-smoke", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: "yt-auth-smoke",
          knowledge_base_id: knowledgeBase.id,
          title: "YouTube auth smoke",
          status: "failed",
          status_message: terminalMessage,
          safe_error_message: terminalMessage,
          error_code: "youtube_authentication_required",
          retryable: true,
        }),
      }),
    );
    await page.goto(`/upload?knowledgeBase=${knowledgeBase.id}`);
    await page.getByLabel("Transcription language").selectOption("ar");
    await page.getByLabel("Media intelligence language").selectOption("ar");
    await page.getByRole("tab", { name: "Video link" }).click();
    await page.getByLabel("Public media URL").fill("https://www.youtube.com/watch?v=smoke");
    await page.getByRole("button", { name: "Import" }).click();
    await expect(page.getByRole("alert")).toContainText(terminalMessage);
    await expect(page.getByLabel("Public media URL")).toBeEnabled();
    await expect(page.getByRole("button", { name: "Import" })).toBeVisible();
    await expect(page.getByText("Pipeline in motion")).toHaveCount(0);
    expectCleanDiagnostics(diagnostics);
  });
});
