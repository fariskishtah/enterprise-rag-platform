import { useCallback, useEffect, useState } from "react";

import {
  deleteDocument,
  getDocument,
  getDocumentChunks,
  getDocumentPreview,
  getExtraction,
  getProcessingStatus,
  originalDocumentUrl,
  processDocument,
  retryDocument,
} from "../api/client";
import { EmptyState } from "../components/EmptyState";
import { ProcessingTimeline } from "../components/ProcessingTimeline";
import { StatusBadge } from "../components/StatusBadge";
import type {
  DocumentChunk,
  DocumentExtraction,
  DocumentPreview,
  DocumentRecord,
} from "../types";

const activeStatuses = new Set([
  "validating",
  "extracting",
  "extracted",
  "chunking",
  "embedding",
  "vector_indexing",
  "indexed",
]);

export function DocumentPage({ documentId }: { documentId: string }) {
  const highlightedChunk = new URLSearchParams(window.location.search).get("chunk");
  const [document, setDocument] = useState<DocumentRecord | null>(null);
  const [extraction, setExtraction] = useState<DocumentExtraction | null>(null);
  const [preview, setPreview] = useState<DocumentPreview | null>(null);
  const [chunks, setChunks] = useState<DocumentChunk[]>([]);
  const [chunkPage, setChunkPage] = useState(1);
  const [chunkTotal, setChunkTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [documentValue, extractionValue, previewValue, chunkValue] =
        await Promise.all([
          getDocument(documentId),
          getExtraction(documentId),
          getDocumentPreview(documentId),
          getDocumentChunks(documentId, chunkPage, 10),
        ]);
      setDocument(documentValue);
      setExtraction(extractionValue);
      setPreview(previewValue);
      setChunks(chunkValue.items);
      setChunkTotal(chunkValue.total);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to load the document.");
    } finally {
      setLoading(false);
    }
  }, [chunkPage, documentId]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!document || !activeStatuses.has(document.status)) return;
    const interval = window.setInterval(() => {
      getProcessingStatus(document.id)
        .then((current) => {
          setDocument(current);
          if (current.status === "ready_for_chat" || current.status === "failed") {
            window.clearInterval(interval);
            void load();
          }
        })
        .catch((reason: unknown) => {
          window.clearInterval(interval);
          setError(
            reason instanceof Error
              ? reason.message
              : "Unable to refresh document processing status.",
          );
        });
    }, 1000);
    return () => window.clearInterval(interval);
  }, [document, load]);

  useEffect(() => {
    if (!highlightedChunk) return;
    window.setTimeout(() => {
      window.document
        .getElementById(`chunk-${highlightedChunk}`)
        ?.scrollIntoView({ behavior: "smooth", block: "center" });
    }, 100);
  }, [chunks, highlightedChunk]);

  async function handleProcessing(retry: boolean) {
    if (!document) return;
    setActionLoading(true);
    setError(null);
    try {
      const queued = retry
        ? await retryDocument(document.id)
        : await processDocument(document.id);
      setDocument(queued);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to start processing.");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleDelete() {
    if (!document || !window.confirm(`Delete ${document.name}? This cannot be undone.`)) {
      return;
    }
    setActionLoading(true);
    try {
      await deleteDocument(document.id);
      window.location.assign(
        `/upload?knowledgeBase=${encodeURIComponent(document.knowledge_base_id)}`,
      );
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to delete the document.");
    } finally {
      setActionLoading(false);
    }
  }

  if (loading) return <div className="panel loading-state">Loading document…</div>;
  if (!document) {
    return (
      <EmptyState
        title="Document unavailable"
        description={error ?? "The requested document could not be loaded."}
      />
    );
  }

  return (
    <section>
      <div className="page-header">
        <div>
          <span className="eyebrow">Document intelligence</span>
          <h1>{document.name}</h1>
          <p>
            {document.document_type.toUpperCase()} ·{" "}
            {document.character_count.toLocaleString()} characters ·{" "}
            {document.chunk_count} chunks
          </p>
        </div>
        <div className="header-actions">
          <a
            className="button secondary"
            href={originalDocumentUrl(document.id)}
            target="_blank"
            rel="noreferrer"
          >
            Open original
          </a>
          <button
            className="button danger"
            disabled={actionLoading}
            onClick={() => void handleDelete()}
          >
            Delete
          </button>
        </div>
      </div>

      {error && <div className="notice error">{error}</div>}

      <article className="panel processing-card">
        <div className="section-header compact">
          <div>
            <h2>Processing lifecycle</h2>
            <p>{document.status_message}</p>
          </div>
          <StatusBadge status={document.status} />
        </div>
        <ProcessingTimeline document={document} />
        {document.status === "uploaded" && (
          <button
            className="button primary"
            disabled={actionLoading}
            onClick={() => void handleProcessing(false)}
          >
            Start processing
          </button>
        )}
        {document.status === "failed" && (
          <button
            className="button primary"
            disabled={actionLoading}
            onClick={() => void handleProcessing(true)}
          >
            Retry processing
          </button>
        )}
      </article>

      <div className="metrics-grid document-metrics">
        <article className="metric-card">
          <span>Pages</span>
          <strong>{document.page_count ?? "—"}</strong>
          <small>Preserved when the format exposes pages</small>
        </article>
        <article className="metric-card">
          <span>Characters</span>
          <strong>{document.character_count.toLocaleString()}</strong>
          <small>Extracted source text</small>
        </article>
        <article className="metric-card">
          <span>Indexed chunks</span>
          <strong>
            {document.indexed_chunk_count}/{document.chunk_count}
          </strong>
          <small>{document.embedding_model ?? "No embedding model yet"}</small>
        </article>
      </div>

      {extraction?.warnings.length ? (
        <div className="notice warning">
          <strong>Extraction warnings</strong>
          <ul>
            {extraction.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {document.processing_error && (
        <div className="notice error" role="alert">
          <strong>Processing failed:</strong> {document.processing_error}
        </div>
      )}

      <article className="panel preview-panel">
        <div className="section-header compact">
          <div>
            <h2>Extracted text preview</h2>
            <p>
              Plain text is rendered safely; document content is never interpreted as HTML.
            </p>
          </div>
        </div>
        {preview?.text ? (
          <pre className="document-preview">{preview.text}</pre>
        ) : (
          <EmptyState
            title="No extracted text yet"
            description="Process this document to create a source-aware text representation."
          />
        )}
      </article>

      <div className="section-header">
        <div>
          <h2>Retrieval chunks</h2>
          <p>Deterministic chunks with source location and vector-index state.</p>
        </div>
        <span className="environment-chip">{chunkTotal} total</span>
      </div>
      {chunks.length === 0 ? (
        <EmptyState
          title="No chunks yet"
          description="Chunks appear after successful extraction and chunking."
        />
      ) : (
        <div className="chunk-list">
          {chunks.map((chunk) => (
            <article
              id={`chunk-${chunk.id}`}
              className={
                highlightedChunk === chunk.id
                  ? "chunk-card highlighted"
                  : "chunk-card"
              }
              key={chunk.id}
            >
              <div className="chunk-meta">
                <strong>Chunk {chunk.chunk_index + 1}</strong>
                <span>
                  {chunk.page_number != null
                    ? `Page ${chunk.page_number}`
                    : chunk.section_index != null
                      ? `Section ${chunk.section_index + 1}`
                      : "No location"}
                </span>
                <span>{chunk.token_estimate} estimated tokens</span>
              </div>
              <p>{chunk.text}</p>
            </article>
          ))}
        </div>
      )}
      {chunkTotal > 10 && (
        <div className="pagination">
          <button
            className="button secondary"
            disabled={chunkPage === 1}
            onClick={() => setChunkPage((page) => page - 1)}
          >
            Previous
          </button>
          <span>Page {chunkPage}</span>
          <button
            className="button secondary"
            disabled={chunkPage * 10 >= chunkTotal}
            onClick={() => setChunkPage((page) => page + 1)}
          >
            Next
          </button>
        </div>
      )}
    </section>
  );
}
