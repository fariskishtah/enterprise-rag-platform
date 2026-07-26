import { citationLocation } from "../api/client";
import type { Citation } from "../types";
import { contentDirection } from "../utils/language";

interface CitationListProps {
  citations: Citation[];
  expandable?: boolean;
}

export function CitationList({ citations, expandable = true }: CitationListProps) {
  if (citations.length === 0) return null;
  return (
    <div className="citations" aria-label="Answer sources">
      <h4>Sources</h4>
      {citations.map((citation, index) => (
        <details
          className="citation-card"
          key={`${citation.chunk_id}-${index}`}
          open={!expandable}
        >
          <summary>
            <span className="citation-index">{index + 1}</span>
            <span>
              <strong>{citation.document_name}</strong>
              <small>
                {citationLocation(citation)} · score{" "}
                {citation.similarity_score.toFixed(3)}
              </small>
            </span>
          </summary>
          <p dir={contentDirection(citation.passage)}>{citation.passage}</p>
          <a
            href={
              citation.media_source_id && citation.timestamp_start != null
                ? `/media/${citation.media_source_id}?t=${citation.timestamp_start}`
                : `/documents/${citation.document_id}?chunk=${citation.chunk_id}`
            }
            className="source-link"
          >
            Open cited passage
          </a>
        </details>
      ))}
    </div>
  );
}
