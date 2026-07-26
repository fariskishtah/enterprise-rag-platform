import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  deleteChatSession,
  listKnowledgeBases,
} from "./client";

describe("API client", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it("uses the relative API prefix and forwards the stored access token", async () => {
    window.localStorage.setItem("token", "signed-token");
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ items: [], total: 0 }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await listKnowledgeBases();

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/knowledge-bases",
      expect.objectContaining({
        headers: expect.any(Headers),
        signal: expect.any(AbortSignal),
      }),
    );
    const request = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect((request.headers as Headers).get("Authorization")).toBe(
      "Bearer signed-token",
    );
  });

  it("applies shared error parsing to delete requests", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            error: { code: "session_locked", message: "Conversation is busy." },
          }),
          { status: 409, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );

    await expect(deleteChatSession("session-1")).rejects.toMatchObject({
      message: "Conversation is busy.",
      status: 409,
      code: "session_locked",
    });
  });

  it("turns a stalled request into an actionable timeout error", async () => {
    vi.useFakeTimers();
    vi.stubGlobal(
      "fetch",
      vi.fn((_url: string, init: RequestInit) =>
        new Promise<Response>((_resolve, reject) => {
          init.signal?.addEventListener("abort", () => {
            reject(new DOMException("Aborted", "AbortError"));
          });
        }),
      ),
    );

    const result = listKnowledgeBases().catch((error: unknown) => error);
    await vi.advanceTimersByTimeAsync(30_000);
    expect(await result).toEqual(
      expect.objectContaining({
        code: "request_timeout",
        status: 0,
      }),
    );
  });
});
