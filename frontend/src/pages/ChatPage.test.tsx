import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ChatPage } from "./ChatPage";

const askKnowledgeBase = vi.fn();

vi.mock("../api/client", () => ({
  askKnowledgeBase: (...args: unknown[]) => askKnowledgeBase(...args),
  deleteChatSession: vi.fn(),
  getChatSession: vi.fn(),
  listChatSessions: vi.fn().mockResolvedValue([]),
  listKnowledgeBases: vi.fn().mockResolvedValue({
    items: [
      {
        id: "kb-1",
        name: "Policy library",
        description: null,
        document_count: 1,
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
      },
    ],
    total: 1,
  }),
}));

describe("ChatPage", () => {
  beforeEach(() => {
    askKnowledgeBase.mockReset();
    askKnowledgeBase.mockResolvedValue({
      session_id: "session-1",
      message_id: "message-1",
      answer: "Employees may work remotely for up to three days per week.",
      direct_answer: "Up to three days per week.",
      supporting_explanation: "",
      citations: [],
      retrieved_sources: [],
      verification: {
        status: "supported",
        claim_support: "fully_supported",
        explanation: "Every claim is supported.",
        unsupported_statements: [],
      },
      retrieval_quality: "high",
      confidence: 0.92,
      support_status: "fully_supported",
      retrieved_chunk_ids: ["chunk-1"],
      generation_model: "local-test",
      model_used: "local-test",
      response_time: 12,
      response_time_ms: 12,
      not_found: false,
      created_at: "2026-01-01T00:00:00Z",
      debug: null,
    });
  });

  it("submits a grounded question and renders confidence metadata", async () => {
    render(<ChatPage />);
    const composer = await screen.findByLabelText("Ask a grounded question");
    fireEvent.change(composer, {
      target: { value: "How many remote days are allowed?" },
    });
    fireEvent.keyDown(composer, { key: "Enter" });

    await waitFor(() =>
      expect(
        screen.getByText("Employees may work remotely for up to three days per week."),
      ).toBeInTheDocument(),
    );
    expect(screen.getByText("92% confidence")).toBeInTheDocument();
    expect(askKnowledgeBase).toHaveBeenCalledWith(
      expect.objectContaining({
        knowledgeBaseId: "kb-1",
        responseMode: "concise",
      }),
    );
  });
});
