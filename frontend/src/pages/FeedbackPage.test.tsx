import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { FeedbackPage } from "./FeedbackPage";

vi.mock("../api/client", () => ({
  getFeedbackAnalytics: vi.fn().mockResolvedValue({
    total_feedback: 4,
    helpful_count: 3,
    unhelpful_count: 1,
    helpful_rate: 0.75,
    complaint_categories: { missing_citation: 1 },
  }),
}));

describe("FeedbackPage", () => {
  it("replaces its loading state with API-backed analytics", async () => {
    render(<FeedbackPage />);

    expect(screen.getByText("Loading feedback analytics…")).toBeInTheDocument();
    expect(await screen.findByText("75%")).toBeInTheDocument();
    expect(screen.queryByText("Loading feedback analytics…")).not.toBeInTheDocument();
    expect(screen.getByText("missing citation")).toBeInTheDocument();
  });
});
