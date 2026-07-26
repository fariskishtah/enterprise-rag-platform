import { type FormEvent, useCallback, useEffect, useState } from "react";

import { createKnowledgeBase, listKnowledgeBases } from "../api/client";
import { EmptyState } from "../components/EmptyState";
import type { KnowledgeBase } from "../types";

export function KnowledgeBasesPage() {
  const [items, setItems] = useState<KnowledgeBase[]>([]);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await listKnowledgeBases();
      setItems(result.items);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to load knowledge bases.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const created = await createKnowledgeBase({
        name: name.trim(),
        description: description.trim() || undefined,
      });
      setItems((current) => [created, ...current]);
      setName("");
      setDescription("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to create knowledge base.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section>
      <div className="page-header">
        <div>
          <span className="eyebrow">Source organization</span>
          <h1>Knowledge bases</h1>
          <p>Keep documents grouped by subject, team, or research objective.</p>
        </div>
      </div>

      {error && (
        <div className="notice error" role="alert">
          {error} <button onClick={() => void load()}>Retry</button>
        </div>
      )}

      <div className="content-grid">
        <article className="panel form-panel">
          <h2>Create a knowledge base</h2>
          <p className="supporting">Give a trusted document collection a clear purpose.</p>
          <form onSubmit={handleSubmit}>
            <label>
              Name
              <input
                value={name}
                onChange={(event) => setName(event.target.value)}
                minLength={1}
                maxLength={120}
                placeholder="e.g. Medical Research"
                required
              />
            </label>
            <label>
              Description <span className="optional">Optional</span>
              <textarea
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                maxLength={2000}
                rows={4}
                placeholder="What knowledge belongs in this collection?"
              />
            </label>
            <button className="button primary" disabled={submitting} type="submit">
              {submitting ? "Creating…" : "Create knowledge base"}
            </button>
          </form>
        </article>

        <div className="collection" aria-busy={loading}>
          {loading ? (
            <div className="panel loading-state">Loading knowledge bases…</div>
          ) : items.length === 0 ? (
            <EmptyState
              title="No knowledge bases yet"
              description="Create your first collection to begin adding trusted documents."
            />
          ) : (
            items.map((knowledgeBase) => (
              <article className="knowledge-card" key={knowledgeBase.id}>
                <div className="knowledge-icon" aria-hidden="true">
                  KB
                </div>
                <div>
                  <h2>{knowledgeBase.name}</h2>
                  <p>{knowledgeBase.description ?? "No description provided."}</p>
                  <span>
                    {knowledgeBase.document_count} document
                    {knowledgeBase.document_count === 1 ? "" : "s"}
                  </span>
                </div>
                <a href={`/knowledge-bases/${knowledgeBase.id}`}>Open workspace</a>
              </article>
            ))
          )}
        </div>
      </div>
    </section>
  );
}
