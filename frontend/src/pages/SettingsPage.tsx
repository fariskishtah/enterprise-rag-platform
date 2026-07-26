import { useEffect, useState } from "react";

import { getRagConfiguration } from "../api/client";
import type { RagConfiguration } from "../types";

export function SettingsPage() {
  const [configuration, setConfiguration] = useState<RagConfiguration | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    getRagConfiguration()
      .then((value) => {
        if (active) setConfiguration(value);
      })
      .catch((reason: unknown) => {
        if (active) {
          setError(
            reason instanceof Error ? reason.message : "Unable to load model settings.",
          );
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const values = configuration
    ? [
        ["Runtime profile", configuration.runtime_profile ?? "balanced"],
        ["Embedding model", configuration.embedding_model],
        ["Generation model", configuration.generation_model],
        ["RAG engine", configuration.rag_engine],
        ["Quantization", configuration.quantization],
        ["Vector store", configuration.vector_store],
        ["Retrieval top-k", configuration.top_k],
        ["Similarity threshold", configuration.similarity_threshold],
        ["Chunk size", `${configuration.chunk_size} characters`],
        ["Chunk overlap", `${configuration.chunk_overlap} characters`],
        ["Temperature", configuration.temperature],
        ["Generation top-k", configuration.generation_top_k],
        ["Top-p", configuration.top_p],
        ["Maximum new tokens", configuration.maximum_new_tokens],
        ["Repetition penalty", configuration.repetition_penalty],
        ["Sampling", configuration.do_sample ? "Enabled" : "Disabled"],
        [
          "Maximum context",
          `${configuration.maximum_context_characters.toLocaleString()} characters`,
        ],
        ["Conversation history", `${configuration.conversation_history_messages} messages`],
        ["Generation timeout", `${configuration.generation_timeout_seconds ?? 90}s`],
        [
          "Generation queue",
          `${configuration.generation_queue_active ?? 0} active, ${configuration.generation_queue_queued ?? 0} queued`,
        ],
      ]
    : [];

  return (
    <section>
      <div className="page-header">
        <div>
          <span className="eyebrow">Runtime configuration</span>
          <h1>Model settings</h1>
          <p>Inspect the validated settings used by extraction, retrieval, and generation.</p>
        </div>
      </div>

      {error && <div className="notice error">{error}</div>}
      <div className="notice information">
        Settings are environment-controlled to keep model changes deliberate and
        restart-safe. Changing an embedding model requires reprocessing affected documents
        so vectors cannot become stale.
      </div>

      {loading ? (
        <div className="panel loading-state">Loading configuration…</div>
      ) : configuration ? (
        <article className="panel settings-panel">
          <dl className="settings-list">
            {values.map(([label, value]) => (
              <div key={String(label)}>
                <dt>{label}</dt>
                <dd>{value}</dd>
              </div>
            ))}
          </dl>
        </article>
      ) : (
        <div className="panel empty-state">
          <h2>Configuration unavailable</h2>
          <p>Verify the backend is running, then refresh this page to try again.</p>
        </div>
      )}
    </section>
  );
}
