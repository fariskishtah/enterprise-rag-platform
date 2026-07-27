import { expect, test, type Page } from "@playwright/test";
import path from "node:path";

async function createKnowledgeBase(page: Page, name: string) {
  await page.goto("/knowledge-bases");
  await page.getByLabel("Name").fill(name);
  await page.getByLabel(/Description/).fill("Deterministic browser evaluation sources");
  await page.getByRole("button", { name: "Create knowledge base" }).click();
  await expect(page.getByRole("heading", { name })).toBeVisible();
}

function wavFixture(): Buffer {
  const sampleRate = 16_000;
  const seconds = 1;
  const dataSize = sampleRate * seconds * 2;
  const buffer = Buffer.alloc(44 + dataSize);
  buffer.write("RIFF", 0);
  buffer.writeUInt32LE(36 + dataSize, 4);
  buffer.write("WAVEfmt ", 8);
  buffer.writeUInt32LE(16, 16);
  buffer.writeUInt16LE(1, 20);
  buffer.writeUInt16LE(1, 22);
  buffer.writeUInt32LE(sampleRate, 24);
  buffer.writeUInt32LE(sampleRate * 2, 28);
  buffer.writeUInt16LE(2, 32);
  buffer.writeUInt16LE(16, 34);
  buffer.write("data", 36);
  buffer.writeUInt32LE(dataSize, 40);
  for (let index = 0; index < sampleRate * seconds; index += 1) {
    buffer.writeInt16LE(Math.round(Math.sin((2 * Math.PI * 440 * index) / sampleRate) * 3000), 44 + index * 2);
  }
  return buffer;
}

test.describe.serial("EnterpriseRAG product journeys", () => {
  test("document RAG: upload, grounded facts, follow-up, unknown, and source jump", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1440, height: 1000 });
    await createKnowledgeBase(page, "Policy Evaluation");
    await page.goto("/upload");
    await page.getByLabel("Knowledge base").selectOption({ label: "Policy Evaluation" });
    const pdfPath = path.resolve("../backend/tests/fixtures/remote_work_policy.pdf");
    await page.locator('input[type="file"]').setInputFiles(pdfPath);
    await page.getByRole("button", { name: /Start secure intake/ }).click();
    await expect(page.getByText(/Every source completed/)).toBeVisible({ timeout: 60_000 });
    await expect(page.getByText("remote_work_policy.pdf")).toBeVisible();
    await expect(page.getByText("Ready for chat")).toBeVisible();

    await page.goto("/chat");
    await page.getByLabel("Knowledge base").selectOption({ label: "Policy Evaluation" });
    const composer = page.getByLabel("Ask a grounded question");
    await composer.fill("How many remote days are employees allowed per week?");
    await composer.press("Enter");
    await expect(
      page.locator(".research-message.assistant .message-body > p").last(),
    ).toContainText(/up to three days per week/i);
    await expect(page.getByText("Supported by sources")).toBeVisible();
    await page.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
    await page.screenshot({ path: "../artifacts/research-chat.png" });

    await composer.fill("When can an employee request a fully remote arrangement?");
    await composer.press("Enter");
    await expect(
      page.locator(".research-message.assistant .message-body > p").last(),
    ).toContainText(/more than 120 kilometres/i);
    await composer.fill("What approvals does it need?");
    await composer.press("Enter");
    await expect(
      page.locator(".research-message.assistant .message-body > p").last(),
    ).toContainText(/department director and People Operations/i);

    await composer.fill("Who is the CEO?");
    await composer.press("Enter");
    await expect(
      page.locator(".research-message.assistant .message-body > p").last(),
    ).toContainText(/do not contain enough information/i);

    await page.locator(".citation-card summary").first().click();
    const sourceLink = page.getByRole("link", { name: "Open cited passage" }).first();
    await expect(sourceLink).toHaveAttribute("href", /\/documents\//);
    await page.screenshot({ path: "../artifacts/research-chat-unknown.png" });
    await sourceLink.click();
    await expect(page).toHaveURL(/\/documents\//);
    await expect(page.getByRole("main")).toContainText(/up to three days per week/i);
  });

  test("local media: transcription, timestamps, intelligence, scoped answer, and export", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1440, height: 1000 });
    await createKnowledgeBase(page, "Media Evaluation");
    await page.goto("/upload");
    await page.getByLabel("Knowledge base").selectOption({ label: "Media Evaluation" });
    await page.locator('input[type="file"]').setInputFiles({
      name: "atlas-review.wav",
      mimeType: "audio/wav",
      buffer: wavFixture(),
    });
    await page.getByRole("button", { name: /Start secure intake/ }).click();
    await expect(page.getByText(/Every source completed/)).toBeVisible({ timeout: 60_000 });
    await expect(
      page.getByRole("heading", { name: "atlas-review", exact: true }),
    ).toBeVisible();

    await page.goto("/video");
    await page.getByRole("combobox").nth(1).selectOption({ label: "atlas-review" });
    await expect(
      page
        .getByRole("button", { name: /0:05 Maya owns the deployment checklist/i })
        .first(),
    ).toBeVisible({ timeout: 30_000 });
    await expect(page.getByRole("heading", { name: "Summary" })).toBeVisible();
    await page.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
    await page.screenshot({ path: "../artifacts/video-player-transcript.png" });
    await page.getByPlaceholder("What decision did the team make?").fill(
      "Who owns the deployment checklist?",
    );
    await page.getByRole("button", { name: "Ask this video" }).click();
    await expect(
      page
        .locator(".video-answer")
        .getByText(/Maya owns the deployment checklist/i)
        .first(),
    ).toBeVisible();
    await expect(page.locator(".video-answer").getByText("0:05").first()).toBeVisible();

    const downloadPromise = page.waitForEvent("download");
    await page.getByRole("link", { name: "Transcript JSON" }).click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toContain("transcript.json");
    await page.locator(".ask-video").scrollIntoViewIfNeeded();
    await page.screenshot({ path: "../artifacts/video-intelligence.png" });
    await page.locator(".video-answer .citation-card summary").click();
    const timestampLink = page
      .locator(".video-answer")
      .getByRole("link", { name: "Open cited passage" });
    await expect(timestampLink).toHaveAttribute("href", /\?t=5(?:\.0)?$/);
    await timestampLink.click();
    await expect(page).toHaveURL(/\?t=5(?:\.0)?$/);
    await expect(page.locator(".transcript-segment.active")).toContainText(
      "Maya owns the deployment checklist",
    );
  });

  test("error boundaries and responsive core actions remain usable", async ({ page }) => {
    await createKnowledgeBase(page, "Security Evaluation");
    await page.goto("/upload");
    await page.getByLabel("Knowledge base").selectOption({ label: "Security Evaluation" });
    await page.getByRole("tab", { name: "Video link" }).click();
    await page.getByLabel("Public media URL").fill("http://127.0.0.1/private.mp4");
    await page.getByRole("button", { name: "Import" }).click();
    await expect(page.getByText(/Private, local, reserved/)).toBeVisible();

    for (const viewport of [
      { width: 1280, height: 800 },
      { width: 820, height: 1000 },
      { width: 390, height: 844 },
    ]) {
      await page.setViewportSize(viewport);
      await page.goto("/dashboard");
      await expect(
        page.getByRole("main").getByRole("link", { name: "Add knowledge", exact: true }),
      ).toBeVisible();
    }
    await page.screenshot({ path: "../artifacts/dashboard-mobile.png", fullPage: true });
  });

  test("public media URL: secure import reaches timestamped video intelligence", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1440, height: 1000 });
    await createKnowledgeBase(page, "Public URL Evaluation");
    await page.goto("/upload");
    await page
      .getByLabel("Knowledge base")
      .selectOption({ label: "Public URL Evaluation" });
    await page.getByRole("tab", { name: "Video link" }).click();
    await page
      .getByLabel("Public media URL")
      .fill("https://media.example/atlas-review.mp4");
    await page.getByRole("button", { name: "Import" }).click();
    await expect(page.getByText(/linked video was ingested/i)).toBeVisible({
      timeout: 60_000,
    });
    await expect(
      page.getByRole("heading", { name: "Linked media", exact: true }),
    ).toBeVisible();

    await page.goto("/video");
    await page
      .getByRole("combobox")
      .first()
      .selectOption({ label: "Public URL Evaluation" });
    await page.getByRole("combobox").nth(1).selectOption({ label: "Linked media" });
    await expect(
      page.getByRole("button", { name: /0:05 Maya owns the deployment checklist/i }),
    ).toBeVisible({ timeout: 30_000 });
    await expect(page.getByRole("heading", { name: "Summary" })).toBeVisible();
    await page
      .getByPlaceholder("What decision did the team make?")
      .fill("Who owns the deployment checklist?");
    await page.getByRole("button", { name: "Ask this video" }).click();
    await expect(
      page.locator(".video-answer > p"),
    ).toBeVisible();
    await expect(page.locator(".video-answer > p")).toContainText(
      /Maya owns the deployment checklist/i,
    );
    await expect(page.locator(".video-answer").getByText("0:05")).toBeVisible();
    await page.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
    await page.screenshot({ path: "../artifacts/public-media-url.png" });
  });
});
