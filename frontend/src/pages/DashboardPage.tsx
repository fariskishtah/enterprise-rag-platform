import {
  ArrowRight,
  Bot,
  CheckCircle2,
  Database,
  FileText,
  Gauge,
  Layers3,
  Plus,
  ScanSearch,
  Sparkles,
  UploadCloud,
  Video,
} from "lucide-react";
import { useEffect, useState } from "react";

import {
  getRagConfiguration,
  listDocuments,
  listKnowledgeBases,
  listMedia,
} from "../api/client";
import { StatusBadge } from "../components/StatusBadge";
import type {
  DocumentRecord,
  KnowledgeBase,
  MediaSource,
  RagConfiguration,
} from "../types";

export function DashboardPage() {
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [media, setMedia] = useState<MediaSource[]>([]);
  const [configuration, setConfiguration] = useState<RagConfiguration | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const [knowledgeResponse, ragConfiguration] = await Promise.all([
          listKnowledgeBases(),
          getRagConfiguration(),
        ]);
        const sourceResults = await Promise.all(
          knowledgeResponse.items.map(async (knowledgeBase) => {
            const [documentResponse, mediaResponse] = await Promise.all([
              listDocuments(knowledgeBase.id),
              listMedia(knowledgeBase.id),
            ]);
            return {
              documents: documentResponse.items,
              media: mediaResponse.items,
            };
          }),
        );
        if (!active) return;
        setKnowledgeBases(knowledgeResponse.items);
        setConfiguration(ragConfiguration);
        setDocuments(sourceResults.flatMap((value) => value.documents));
        setMedia(sourceResults.flatMap((value) => value.media));
      } catch (reason) {
        if (active) {
          setError(
            reason instanceof Error ? reason.message : "Unable to load the workspace.",
          );
        }
      } finally {
        if (active) setLoading(false);
      }
    }
    void load();
    return () => {
      active = false;
    };
  }, []);

  const chunks = documents.reduce((total, value) => total + value.indexed_chunk_count, 0);
  const readySources =
    documents.filter((value) => value.status === "ready_for_chat").length +
    media.filter((value) => value.status === "ready").length;
  const totalSources = documents.length + media.length;
  const readySourcePercentage = totalSources
    ? Math.round((readySources / totalSources) * 100)
    : null;
  const recentSources = [...documents, ...media]
    .sort(
      (first, second) =>
        new Date(second.created_at).getTime() - new Date(first.created_at).getTime(),
    )
    .slice(0, 4);

  return (
    <section className="dashboard-page">
      <div className="dashboard-hero">
        <div>
          <span className="eyebrow">Intelligence workspace</span>
          <h1>
            Your knowledge,
            <br />
            <em>finally in focus.</em>
          </h1>
          <p>
            Turn documents, meetings, and videos into answers you can trace back to
            the exact evidence.
          </p>
          <div className="hero-actions">
            <a className="button primary" href="/upload">
              <Plus size={17} /> Add knowledge
            </a>
            <a className="button ghost" href="/chat">
              Ask a question <ArrowRight size={16} />
            </a>
          </div>
        </div>
        <div className="hero-orbit" aria-hidden="true">
          <span className="orbit-ring ring-one" />
          <span className="orbit-ring ring-two" />
          <span className="knowledge-core">
            <Sparkles size={30} />
          </span>
          <span className="orbit-node node-document">
            <FileText size={17} />
          </span>
          <span className="orbit-node node-video">
            <Video size={17} />
          </span>
          <span className="orbit-node node-answer">
            <Bot size={17} />
          </span>
        </div>
      </div>

      {error && (
        <div className="notice error" role="alert">
          {error}
        </div>
      )}

      <div className="metric-ribbon" aria-busy={loading}>
        {[
          {
            label: "Knowledge bases",
            value: knowledgeBases.length,
            note: "Active collections",
            icon: Database,
          },
          {
            label: "Sources",
            value: documents.length + media.length,
            note: `${media.length} video or audio`,
            icon: Layers3,
          },
          {
            label: "Indexed passages",
            value: chunks.toLocaleString(),
            note: "Ready for retrieval",
            icon: ScanSearch,
          },
          {
            label: "Source health",
            value: readySourcePercentage === null ? "—" : `${readySourcePercentage}%`,
            note: "Successfully indexed",
            icon: Gauge,
          },
        ].map((metric) => {
          const Icon = metric.icon;
          return (
            <div className="metric-item" key={metric.label}>
              <span className="metric-icon">
                <Icon size={17} />
              </span>
              <span>
                <small>{metric.label}</small>
                <strong>{loading ? <span className="skeleton-line" /> : metric.value}</strong>
                <em>{metric.note}</em>
              </span>
            </div>
          );
        })}
      </div>

      <div className="dashboard-grid">
        <section className="dashboard-section source-activity">
          <div className="section-heading">
            <div>
              <span className="eyebrow">Source pulse</span>
              <h2>Recent knowledge</h2>
            </div>
            <a href="/upload">View library <ArrowRight size={14} /></a>
          </div>
          {recentSources.length === 0 ? (
            <div className="dashboard-empty">
              <UploadCloud size={24} />
              <h3>The workspace is waiting for its first source.</h3>
              <p>Upload a policy, report, meeting recording, or public video.</p>
              <a href="/upload">Open source intake</a>
            </div>
          ) : (
            <div className="recent-source-list">
              {recentSources.map((source) => {
                const isMedia = "source_kind" in source;
                return (
                  <a
                    key={source.id}
                    href={isMedia ? `/media/${source.id}` : `/documents/${source.id}`}
                    className="recent-source"
                  >
                    <span className={`source-glyph ${isMedia ? "video" : "document"}`}>
                      {isMedia ? <Video size={18} /> : <FileText size={18} />}
                    </span>
                    <span>
                      <strong>{isMedia ? source.title : source.name}</strong>
                      <small>
                        {isMedia
                          ? source.source_platform
                          : `${source.document_type.toUpperCase()} · ${source.chunk_count} chunks`}
                      </small>
                    </span>
                    <StatusBadge status={source.status} />
                    <ArrowRight size={15} />
                  </a>
                );
              })}
            </div>
          )}
        </section>

        <aside className="dashboard-section retrieval-health">
          <div className="section-heading">
            <div>
              <span className="eyebrow">Trust layer</span>
              <h2>Source readiness</h2>
            </div>
            <span className="live-label"><span /> current</span>
          </div>
          <div className="health-visual">
            <div className="health-score">
              <span>
                {loading
                  ? "…"
                  : readySourcePercentage === null
                    ? "—"
                    : `${readySourcePercentage}%`}
              </span>
              <small>Sources ready</small>
            </div>
            <div
              className="health-progress"
              role="progressbar"
              aria-label="Ready sources"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={readySourcePercentage ?? 0}
            >
              <span style={{ width: `${readySourcePercentage ?? 0}%` }} />
            </div>
          </div>
          <dl className="health-details">
            <div>
              <dt>Retrieval</dt>
              <dd>
                {configuration?.retrieval_strategy.replaceAll("_", " ") ??
                  (loading ? "Loading" : "Unavailable")}
              </dd>
            </div>
            <div>
              <dt>Generator</dt>
              <dd>
                {configuration?.generation_model.split("/").at(-1) ??
                  (loading ? "Loading" : "Unavailable")}
              </dd>
            </div>
            <div>
              <dt>Runtime</dt>
              <dd>
                {configuration
                  ? `${configuration.model_device.toUpperCase()} · ${
                      configuration.warmup_status === "loading"
                        ? "warming"
                        : configuration.model_warm
                        ? "warm"
                        : configuration.generation_model_cached
                          ? "cached"
                          : "on demand"
                    }`
                  : loading
                    ? "Loading"
                    : "Unavailable"}
              </dd>
            </div>
            <div>
              <dt>Privacy</dt>
              <dd><CheckCircle2 size={14} /> Local processing</dd>
            </div>
          </dl>
        </aside>
      </div>

      <section className="quick-actions">
        <div>
          <span className="eyebrow">Begin a workflow</span>
          <h2>What would you like to understand?</h2>
        </div>
        <div className="quick-action-list">
          <a href="/chat">
            <Bot size={19} />
            <span><strong>Ask your sources</strong><small>Grounded answers with citations</small></span>
            <ArrowRight size={15} />
          </a>
          <a href="/video">
            <Video size={19} />
            <span><strong>Decode a recording</strong><small>Transcript, chapters, and decisions</small></span>
            <ArrowRight size={15} />
          </a>
          <a href="/intelligence">
            <Layers3 size={19} />
            <span><strong>Compare evidence</strong><small>Find alignment and contradictions</small></span>
            <ArrowRight size={15} />
          </a>
        </div>
      </section>
    </section>
  );
}
