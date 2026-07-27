import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { DashboardPage } from "./DashboardPage";

vi.mock("../api/client", () => ({
  getRagConfiguration: vi.fn().mockResolvedValue({
    retrieval_strategy: "hybrid_dense_lexical_rerank",
    generation_model: "local/test-model",
    model_device: "cpu",
    warmup_status: "cold",
    model_warm: false,
    generation_model_cached: false,
  }),
  listKnowledgeBases: vi.fn().mockResolvedValue({
    items: [{ id: "kb-1", name: "Policies" }],
    total: 1,
  }),
  listDocuments: vi.fn().mockResolvedValue({
    items: [
      {
        id: "doc-ready",
        name: "ready.txt",
        document_type: "txt",
        status: "ready_for_chat",
        chunk_count: 2,
        indexed_chunk_count: 2,
        created_at: "2026-07-27T00:00:00Z",
      },
      {
        id: "doc-failed",
        name: "failed.txt",
        document_type: "txt",
        status: "failed",
        chunk_count: 0,
        indexed_chunk_count: 0,
        created_at: "2026-07-26T00:00:00Z",
      },
    ],
    total: 2,
  }),
  listMedia: vi.fn().mockResolvedValue({ items: [], total: 0 }),
}));

describe("DashboardPage", () => {
  it("shows measured source readiness instead of a decorative grade", async () => {
    render(<DashboardPage />);

    expect(screen.getByText("Source readiness")).toBeInTheDocument();
    expect((await screen.findAllByText("50%")).length).toBeGreaterThan(0);
    expect(screen.getByRole("progressbar", { name: "Ready sources" })).toHaveAttribute(
      "aria-valuenow",
      "50",
    );
    expect(screen.queryByText("A")).not.toBeInTheDocument();
  });
});
