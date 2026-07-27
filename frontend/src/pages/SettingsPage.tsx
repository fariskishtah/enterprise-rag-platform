import { useEffect, useState } from "react";

import { getRagConfiguration, warmModels } from "../api/client";
import type { RagConfiguration } from "../types";

export function SettingsPage() {
  const [configuration, setConfiguration] = useState<RagConfiguration | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [warming, setWarming] = useState(false);

  async function loadConfiguration() {
    setLoading(true);
    setError(null);
    try {
      setConfiguration(await getRagConfiguration());
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to load model settings.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadConfiguration();
  }, []);

  async function beginWarmup() {
    if (warming) return;
    setWarming(true);
    setError(null);
    try {
      await warmModels();
      await loadConfiguration();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to start model warm-up.");
    } finally {
      setWarming(false);
    }
  }

  const values = configuration
    ? [
        ["Runtime profile", configuration.runtime_profile ?? "balanced"],
        ["Embedding model", configuration.embedding_model],
        ["Generation model", configuration.generation_model],
        ["Embedding state", configuration.embedding_model_status],
        ["Generation state", configuration.generation_model_status],
        ["Warm-up state", configuration.warmup_status],
        ["RAG engine", configuration.rag_engine],
        ["Quantization", configuration.quantization],
        ["Vector store", configuration.vector_store],
        ["Retrieval top-k", configuration.top_k],
        ["Similarity threshold", configuration.similarity_threshold],
        ["Chunk size", `${configuration.chunk_size} characters`],
        ["Maximum upload", `${configuration.maximum_upload_mb} MB`],
        ["Maximum document pages", configuration.maximum_document_pages],
        ["Maximum media duration", `${configuration.maximum_media_duration_minutes} minutes`],
        ["Files per knowledge base", configuration.maximum_files_per_knowledge_base],
        ["Knowledge bases", configuration.maximum_knowledge_bases],
        ["Concurrent heavy operations", configuration.maximum_concurrent_heavy_operations],
        ["Bounded heavy queue", configuration.heavy_queue_max_size],
        ["Demo data retention", `${configuration.demo_data_retention_hours} hours`],
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
      {configuration?.embedding_reindex_required && (
        <div className="notice warning" role="alert">
          The embedding model changed. Reindex existing documents before retrieval; vectors
          from different models will not be mixed.
        </div>
      )}
      {configuration?.warmup_status === "failed" && (
        <div className="notice error" role="alert">
          Model warm-up failed. Confirm the model-cache volume, network access, and available
          memory, then retry.
        </div>
      )}

      {loading ? (
        <div className="panel loading-state">Loading configuration…</div>
      ) : configuration ? (
        <article className="panel settings-panel">
          <div className="settings-actions">
            <button className="button secondary" onClick={() => void beginWarmup()} disabled={warming}>
              {warming ? "Starting warm-up…" : "Warm models"}
            </button>
            <button className="button secondary" onClick={() => void loadConfiguration()} disabled={loading}>
              Refresh status
            </button>
          </div>
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
          <button className="button secondary" onClick={() => void loadConfiguration()}>
            Retry
          </button>
        </div>
      )}
    </section>
  );
}
