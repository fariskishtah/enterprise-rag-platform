import type { DocumentStatus, MediaStatus } from "../types";

const labels: Record<DocumentStatus | MediaStatus, string> = {
  uploaded: "Uploaded",
  validating: "Validating",
  extracting: "Extracting",
  extracted: "Extracted",
  chunking: "Chunking",
  embedding: "Embedding",
  vector_indexing: "Indexing vectors",
  indexing: "Indexing",
  indexed: "Indexed",
  ready_for_chat: "Ready for chat",
  processing: "Processing",
  ready: "Ready",
  failed: "Failed",
  uploaded_or_linked: "Queued",
  fetching_metadata: "Fetching metadata",
  downloading_or_extracting_subtitles: "Finding subtitles",
  extracting_audio: "Extracting audio",
  transcribing: "Transcribing",
  transcript_ready: "Transcript ready",
  summarising: "Summarising",
};

export function StatusBadge({ status }: { status: DocumentStatus | MediaStatus }) {
  return <span className={`status-badge status-${status}`}>{labels[status]}</span>;
}
