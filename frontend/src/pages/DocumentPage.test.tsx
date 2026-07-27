import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DocumentPage } from "./DocumentPage";

const getDocument = vi.fn();
const getExtraction = vi.fn();
const getDocumentPreview = vi.fn();
const getDocumentChunks = vi.fn();
const getProcessingStatus = vi.fn();

vi.mock("../api/client", () => ({
  deleteDocument: vi.fn(),
  getDocument: (...args: unknown[]) => getDocument(...args),
  getDocumentChunks: (...args: unknown[]) => getDocumentChunks(...args),
  getDocumentPreview: (...args: unknown[]) => getDocumentPreview(...args),
  getExtraction: (...args: unknown[]) => getExtraction(...args),
  getProcessingStatus: (...args: unknown[]) => getProcessingStatus(...args),
  originalDocumentUrl: () => "/api/v1/documents/document-1/content",
  processDocument: vi.fn(),
  retryDocument: vi.fn(),
}));

const activeDocument = {
  id: "document-1",
  knowledge_base_id: "knowledge-base-1",
  name: "bounded.pdf",
  document_type: "pdf",
  media_type: "application/pdf",
  size_bytes: 10,
  checksum_sha256: "a".repeat(64),
  status: "extracting",
  status_message: "Extracting text.",
  extraction_warnings: [],
  extraction_metadata: {},
  page_count: 1,
  character_count: 0,
  chunk_count: 0,
  indexed_chunk_count: 0,
  processing_attempts: 1,
  embedding_model: null,
  processing_started_at: null,
  extraction_completed_at: null,
  indexing_completed_at: null,
  created_at: "2026-07-27T00:00:00Z",
  updated_at: "2026-07-27T00:00:00Z",
  last_accessed_at: "2026-07-27T00:00:00Z",
  expires_at: null,
  is_protected: false,
};

describe("DocumentPage processing polling", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    getDocument.mockResolvedValue(activeDocument);
    getExtraction.mockResolvedValue({
      document_id: "document-1",
      status: "extracting",
      sections: [],
      warnings: [],
      metadata: {},
      character_count: 0,
      page_count: 1,
      extraction_completed_at: null,
    });
    getDocumentPreview.mockResolvedValue({
      document_id: "document-1",
      text: "",
      truncated: false,
      character_count: 0,
    });
    getDocumentChunks.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 10 });
    getProcessingStatus.mockResolvedValue(activeDocument);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  it("terminates status polling with an actionable message", async () => {
    render(<DocumentPage documentId="document-1" />);
    await act(async () => Promise.resolve());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(182_000);
    });

    expect(
      screen.getByText(/processing is taking longer than expected/i),
    ).toBeInTheDocument();
    expect(getProcessingStatus.mock.calls.length).toBeLessThanOrEqual(180);
  });
});
