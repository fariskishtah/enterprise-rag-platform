import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { IntelligencePage } from "./IntelligencePage";

const listDocuments = vi.fn();

vi.mock("../api/client", () => ({
  compareDocuments: vi.fn(),
  createReport: vi.fn(),
  createSummary: vi.fn(),
  listDocuments: (...args: unknown[]) => listDocuments(...args),
  listKnowledgeBases: vi.fn().mockResolvedValue({
    items: [
      { id: "kb-1", name: "First collection" },
      { id: "kb-2", name: "Requested collection" },
    ],
    total: 2,
  }),
}));

describe("IntelligencePage", () => {
  beforeEach(() => {
    listDocuments.mockReset();
    listDocuments.mockResolvedValue({ items: [], total: 0 });
    window.history.replaceState({}, "", "/intelligence?knowledgeBase=kb-2");
  });

  it("honors a valid knowledge-base scope from the workspace shortcut", async () => {
    render(<IntelligencePage />);

    await waitFor(() => expect(listDocuments).toHaveBeenCalledWith("kb-2"));
    expect(screen.getByRole("combobox", { name: "Knowledge base" })).toHaveValue("kb-2");
  });
});
