import type { DocumentRecord, DocumentStatus } from "../types";

const stages: Array<{ status: DocumentStatus; label: string }> = [
  { status: "validating", label: "Validate" },
  { status: "extracting", label: "Extract" },
  { status: "chunking", label: "Chunk" },
  { status: "embedding", label: "Embed" },
  { status: "vector_indexing", label: "Index" },
  { status: "ready_for_chat", label: "Ready" },
];

const rank: Partial<Record<DocumentStatus, number>> = {
  uploaded: -1,
  validating: 0,
  extracting: 1,
  extracted: 1,
  chunking: 2,
  embedding: 3,
  vector_indexing: 4,
  indexed: 4,
  ready_for_chat: 5,
  ready: 5,
};

export function ProcessingTimeline({ document }: { document: DocumentRecord }) {
  const current = rank[document.status] ?? -1;
  return (
    <ol className="processing-timeline" aria-label="Document processing progress">
      {stages.map((stage, index) => (
        <li
          key={stage.status}
          className={
            document.status === "failed"
              ? index < Math.max(current, 0)
                ? "complete"
                : "pending"
              : index < current
                ? "complete"
                : index === current
                  ? "active"
                  : "pending"
          }
        >
          <span aria-hidden="true">{index + 1}</span>
          {stage.label}
        </li>
      ))}
    </ol>
  );
}

