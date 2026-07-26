import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ChatPage } from "./ChatPage";

const askKnowledgeBase = vi.fn();

vi.mock("../api/client", () => ({
  askKnowledgeBase: (...args: unknown[]) => askKnowledgeBase(...args),
  deleteChatSession: vi.fn(),
  getChatSession: vi.fn(),
  getRagConfiguration: vi.fn().mockResolvedValue({ generation_model_status: "ready" }),
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
      output_language: "en",
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

  it("requests Arabic output and renders the answer right-to-left", async () => {
    askKnowledgeBase.mockResolvedValueOnce({
      session_id: "session-ar",
      message_id: "message-ar",
      answer: "يسمح للموظفين بالعمل عن بُعد ثلاثة أيام أسبوعياً.",
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
      confidence: 0.9,
      support_status: "fully_supported",
      retrieved_chunk_ids: ["chunk-ar"],
      generation_model: "local-test",
      model_used: "local-test",
      response_time: 15,
      response_time_ms: 15,
      not_found: false,
      output_language: "ar",
      created_at: "2026-01-01T00:00:00Z",
      debug: null,
    });
    render(<ChatPage />);
    fireEvent.change(await screen.findByLabelText("Answer language"), {
      target: { value: "ar" },
    });
    const composer = screen.getByLabelText("Ask a grounded question");
    fireEvent.change(composer, { target: { value: "ما سياسة العمل عن بُعد؟" } });
    fireEvent.keyDown(composer, { key: "Enter" });

    const answer = await screen.findByText(
      "يسمح للموظفين بالعمل عن بُعد ثلاثة أيام أسبوعياً.",
    );
    expect(answer).toHaveAttribute("dir", "rtl");
    expect(askKnowledgeBase).toHaveBeenCalledWith(
      expect.objectContaining({ outputLanguage: "ar" }),
    );
  });
});
