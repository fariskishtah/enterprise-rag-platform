import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { CitationList } from "./CitationList";

describe("CitationList", () => {
  it("links timestamp citations to the synchronized media workspace", () => {
    render(
      <CitationList
        citations={[
          {
            document_id: "document-1",
            document_name: "Launch review transcript",
            chunk_id: "chunk-1",
            passage: "Maya owns the deployment checklist.",
            similarity_score: 0.91,
            page_number: null,
            section_index: 0,
            timestamp_start: 65,
            timestamp_end: 70,
            media_source_id: "media-1",
            support_score: 0.91,
          },
        ]}
      />,
    );

    expect(screen.getByText(/1:05/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /open cited passage/i })).toHaveAttribute(
      "href",
      "/media/media-1?t=65",
    );
  });
});
