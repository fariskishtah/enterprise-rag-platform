import {
  AlertCircle,
  ArrowRight,
  Check,
  File,
  FileText,
  Film,
  Link2,
  LoaderCircle,
  Music2,
  RefreshCw,
  Search,
  SlidersHorizontal,
  UploadCloud,
  Video,
  Youtube,
} from "lucide-react";
import {
  type DragEvent,
  type FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import {
  getMedia,
  getProcessingStatus,
  linkMedia,
  listDocuments,
  listKnowledgeBases,
  listMedia,
  processDocument,
  retryDocument,
  retryMedia,
  uploadDocument,
  uploadMedia,
} from "../api/client";
import { EmptyState } from "../components/EmptyState";
import { StatusBadge } from "../components/StatusBadge";
import type {
  DocumentRecord,
  KnowledgeBase,
  MediaSource,
} from "../types";

type IntakeMode = "files" | "url";
type SourceFilter = "all" | "documents" | "media";

const documentExtensions = new Set(["pdf", "txt", "docx"]);
const mediaExtensions = new Set(["mp4", "mov", "mkv", "webm", "m4a", "mp3", "wav"]);

function formatBytes(bytes: number | null): string {
  if (bytes == null) return "Linked source";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function UploadPage() {
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [knowledgeBaseId, setKnowledgeBaseId] = useState(
    new URLSearchParams(window.location.search).get("knowledgeBase") ?? "",
  );
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [media, setMedia] = useState<MediaSource[]>([]);
  const [mode, setMode] = useState<IntakeMode>("files");
  const [files, setFiles] = useState<File[]>([]);
  const [url, setUrl] = useState("");
  const [filter, setFilter] = useState<SourceFilter>("all");
  const [sortOrder, setSortOrder] = useState<"recent" | "name">("recent");
  const [search, setSearch] = useState("");
  const [dragging, setDragging] = useState(false);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    listKnowledgeBases()
      .then((result) => {
        setKnowledgeBases(result.items);
        if (!knowledgeBaseId && result.items[0]) setKnowledgeBaseId(result.items[0].id);
      })
      .catch((reason: unknown) =>
        setError(reason instanceof Error ? reason.message : "Unable to load knowledge bases."),
      )
      .finally(() => setLoading(false));
  }, []);

  const loadSources = useCallback(async () => {
    if (!knowledgeBaseId) {
      setDocuments([]);
      setMedia([]);
      return;
    }
    try {
      const [documentResult, mediaResult] = await Promise.all([
        listDocuments(knowledgeBaseId),
        listMedia(knowledgeBaseId),
      ]);
      setDocuments(documentResult.items);
      setMedia(mediaResult.items);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to load sources.");
    }
  }, [knowledgeBaseId]);

  useEffect(() => {
    void loadSources();
    if (knowledgeBaseId) {
      const next = new URL(window.location.href);
      next.searchParams.set("knowledgeBase", knowledgeBaseId);
      window.history.replaceState(null, "", next);
    }
  }, [knowledgeBaseId, loadSources]);

  function chooseFiles(nextFiles: File[]) {
    const supported = nextFiles.filter((value) => {
      const extension = value.name.split(".").at(-1)?.toLowerCase() ?? "";
      return documentExtensions.has(extension) || mediaExtensions.has(extension);
    });
    if (supported.length !== nextFiles.length) {
      setError("Some files were skipped because their format is not supported.");
    }
    setFiles(supported);
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    chooseFiles(Array.from(event.dataTransfer.files));
  }

  async function waitForDocument(document: DocumentRecord) {
    setProgress((value) => ({ ...value, [document.id]: "Queued for extraction" }));
    await processDocument(document.id);
    for (let attempt = 0; attempt < 240; attempt += 1) {
      await new Promise((resolve) => window.setTimeout(resolve, 750));
      const current = await getProcessingStatus(document.id);
      setProgress((value) => ({
        ...value,
        [document.id]: current.status_message ?? current.status,
      }));
      if (current.status === "ready_for_chat" || current.status === "failed") return;
    }
  }

  async function waitForMedia(source: MediaSource) {
    for (let attempt = 0; attempt < 480; attempt += 1) {
      await new Promise((resolve) => window.setTimeout(resolve, 1000));
      const current = await getMedia(source.id);
      setProgress((value) => ({
        ...value,
        [source.id]: current.status_message ?? current.status,
      }));
      if (current.status === "ready" || current.status === "failed") return;
    }
  }

  async function submitFiles(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!knowledgeBaseId || files.length === 0) return;
    setUploading(true);
    setError(null);
    setSuccess(null);
    try {
      for (const selected of files) {
        const extension = selected.name.split(".").at(-1)?.toLowerCase() ?? "";
        setProgress((value) => ({ ...value, [selected.name]: "Uploading securely" }));
        if (documentExtensions.has(extension)) {
          const source = await uploadDocument(knowledgeBaseId, selected);
          setProgress((value) => ({ ...value, [source.id]: "Stored · extracting" }));
          await waitForDocument(source);
        } else {
          const source = await uploadMedia(knowledgeBaseId, selected);
          setProgress((value) => ({ ...value, [source.id]: "Stored · validating media" }));
          await waitForMedia(source);
        }
      }
      setFiles([]);
      if (inputRef.current) inputRef.current.value = "";
      setSuccess("Every source completed its intake workflow. Review source health below.");
      await loadSources();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Source intake could not complete.");
      await loadSources();
    } finally {
      setUploading(false);
    }
  }

  async function submitUrl(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!knowledgeBaseId || !url.trim()) return;
    setUploading(true);
    setError(null);
    try {
      const source = await linkMedia(knowledgeBaseId, url.trim());
      setProgress({ [source.id]: "Linked · retrieving safe metadata" });
      setUrl("");
      await waitForMedia(source);
      setSuccess("The linked video was ingested and is ready to explore.");
      await loadSources();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The media link could not be ingested.");
      await loadSources();
    } finally {
      setUploading(false);
    }
  }

  const library = useMemo(() => {
    const sourceValues = [
      ...documents.map((value) => ({ kind: "document" as const, value })),
      ...media.map((value) => ({ kind: "media" as const, value })),
    ];
    return sourceValues
      .filter((source) => {
        if (filter === "documents" && source.kind !== "document") return false;
        if (filter === "media" && source.kind !== "media") return false;
        const name = source.kind === "document" ? source.value.name : source.value.title;
        return name.toLowerCase().includes(search.toLowerCase());
      })
      .sort((first, second) => {
        if (sortOrder === "name") {
          const firstName =
            first.kind === "document" ? first.value.name : first.value.title;
          const secondName =
            second.kind === "document" ? second.value.name : second.value.title;
          return firstName.localeCompare(secondName);
        }
        return (
          new Date(second.value.created_at).getTime() -
          new Date(first.value.created_at).getTime()
        );
      });
  }, [documents, media, filter, search, sortOrder]);

  if (!loading && knowledgeBases.length === 0) {
    return (
      <EmptyState
        title="Create a knowledge base first"
        description="Every document, recording, and video belongs to an explicit knowledge scope."
        action={<a className="button primary" href="/knowledge-bases">Create knowledge base</a>}
      />
    );
  }

  return (
    <section className="source-page">
      <div className="page-header source-header">
        <div>
          <span className="eyebrow">Source intelligence</span>
          <h1>Bring knowledge into focus.</h1>
          <p>Documents, recordings, and public videos enter one explainable pipeline.</p>
        </div>
        <label className="inline-select">
          <span>Knowledge base</span>
          <select
            value={knowledgeBaseId}
            onChange={(event) => setKnowledgeBaseId(event.target.value)}
            disabled={uploading}
          >
            <option value="">Choose a collection</option>
            {knowledgeBases.map((value) => (
              <option key={value.id} value={value.id}>{value.name}</option>
            ))}
          </select>
        </label>
      </div>

      {error && <div className="notice error" role="alert"><AlertCircle size={16} /> {error}</div>}
      {success && <div className="notice success"><Check size={16} /> {success}</div>}

      <section className="intake-studio">
        <div className="intake-tabs" role="tablist" aria-label="Source intake method">
          <button
            className={mode === "files" ? "active" : ""}
            onClick={() => setMode("files")}
            role="tab"
            aria-selected={mode === "files"}
          >
            <UploadCloud size={17} /> Files
          </button>
          <button
            className={mode === "url" ? "active" : ""}
            onClick={() => setMode("url")}
            role="tab"
            aria-selected={mode === "url"}
          >
            <Link2 size={17} /> Video link
          </button>
        </div>

        {mode === "files" ? (
          <form className="file-intake" onSubmit={submitFiles}>
            <div
              className={`drop-zone ${dragging ? "dragging" : ""}`}
              onDragOver={(event) => {
                event.preventDefault();
                setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={handleDrop}
              onClick={() => inputRef.current?.click()}
              role="button"
              tabIndex={0}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") inputRef.current?.click();
              }}
            >
              <input
                ref={inputRef}
                type="file"
                multiple
                accept=".pdf,.txt,.docx,.mp4,.mov,.mkv,.webm,.m4a,.mp3,.wav"
                onChange={(event) => chooseFiles(Array.from(event.target.files ?? []))}
                hidden
              />
              <span className="drop-icon"><UploadCloud size={26} /></span>
              <h2>Drop source files here</h2>
              <p>or click to browse your device</p>
              <small>PDF · DOCX · TXT · MP4 · MOV · MKV · WEBM · M4A · MP3 · WAV</small>
            </div>
            {files.length > 0 && (
              <div className="file-queue">
                {files.map((selected) => {
                  const extension = selected.name.split(".").at(-1)?.toLowerCase() ?? "";
                  const isMedia = mediaExtensions.has(extension);
                  return (
                    <div key={`${selected.name}-${selected.size}`}>
                      <span className={`source-glyph ${isMedia ? "video" : "document"}`}>
                        {isMedia ? <Film size={18} /> : <FileText size={18} />}
                      </span>
                      <span>
                        <strong>{selected.name}</strong>
                        <small>{formatBytes(selected.size)} · {isMedia ? "Media transcription" : "Document extraction"}</small>
                      </span>
                      {uploading ? <LoaderCircle className="spin" size={18} /> : <Check size={17} />}
                    </div>
                  );
                })}
              </div>
            )}
            <button
              className="button primary intake-submit"
              disabled={!knowledgeBaseId || files.length === 0 || uploading}
            >
              {uploading ? <><LoaderCircle className="spin" size={16} /> Processing sources…</> : <>Start secure intake <ArrowRight size={16} /></>}
            </button>
          </form>
        ) : (
          <form className="link-intake" onSubmit={submitUrl}>
            <span className="link-illustration"><Youtube size={32} /></span>
            <div>
              <span className="eyebrow">Public video intelligence</span>
              <h2>Paste a public video or YouTube URL.</h2>
              <p>We look for official subtitles first, then transcribe locally when access permits.</p>
            </div>
            <label>
              Public media URL
              <div className="url-field">
                <Link2 size={17} />
                <input
                  type="url"
                  value={url}
                  onChange={(event) => setUrl(event.target.value)}
                  placeholder="https://www.youtube.com/watch?v=…"
                  disabled={uploading}
                  required
                />
                <button className="button primary" disabled={!knowledgeBaseId || !url || uploading}>
                  {uploading ? <LoaderCircle className="spin" size={17} /> : "Import"}
                </button>
              </div>
            </label>
            <small className="security-note">DRM, private content, authentication, and paywalls are never bypassed.</small>
          </form>
        )}

        {Object.keys(progress).length > 0 && uploading && (
          <div className="stage-progress">
            <LoaderCircle className="spin" size={18} />
            <div>
              <strong>Pipeline in motion</strong>
              <span>{Object.values(progress).at(-1)}</span>
            </div>
            <span className="stage-dots"><i /><i /><i /><i /></span>
          </div>
        )}
      </section>

      <div className="library-heading">
        <div>
          <span className="eyebrow">Knowledge inventory</span>
          <h2>Source library</h2>
          <p>{documents.length + media.length} sources in this collection</p>
        </div>
        <div className="library-tools">
          <label className="search-field">
            <Search size={16} />
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search sources"
              aria-label="Search sources"
            />
          </label>
          <div className="filter-segment" aria-label="Filter sources">
            {(["all", "documents", "media"] as const).map((value) => (
              <button
                key={value}
                className={filter === value ? "active" : ""}
                onClick={() => setFilter(value)}
              >
                {value}
              </button>
            ))}
          </div>
          <button className="icon-button" onClick={() => void loadSources()} aria-label="Refresh sources">
            <RefreshCw size={17} />
          </button>
          <button
            className="icon-button"
            onClick={() =>
              setSortOrder((value) => (value === "recent" ? "name" : "recent"))
            }
            aria-label={
              sortOrder === "recent"
                ? "Sort sources by name"
                : "Sort sources by newest"
            }
            title={
              sortOrder === "recent"
                ? "Currently sorted by newest"
                : "Currently sorted by name"
            }
          >
            <SlidersHorizontal size={17} />
          </button>
        </div>
      </div>

      {library.length === 0 ? (
        <EmptyState
          title="No sources match this view"
          description="Add a file or video link above to begin building grounded intelligence."
        />
      ) : (
        <div className="source-library-grid">
          {library.map((source) => {
            const isMedia = source.kind === "media";
            const value = source.value;
            const mediaValue = source.kind === "media" ? source.value : null;
            const documentValue = source.kind === "document" ? source.value : null;
            const title = mediaValue?.title ?? documentValue?.name ?? "Untitled source";
            const ready = mediaValue
              ? mediaValue.status === "ready"
              : documentValue?.status === "ready_for_chat";
            const icon = isMedia
              ? mediaValue?.media_type?.startsWith("audio")
                ? <Music2 size={21} />
                : <Video size={21} />
              : documentValue?.document_type === "pdf"
                ? <FileText size={21} />
                : <File size={21} />;
            return (
              <article className="source-card" key={value.id}>
                <div className="source-card-top">
                  <span className={`source-art ${isMedia ? "media" : "document"}`}>{icon}</span>
                  <StatusBadge status={value.status} />
                </div>
                <div className="source-card-copy">
                  <small>{mediaValue ? mediaValue.source_platform : documentValue?.document_type.toUpperCase()}</small>
                  <h3>{title}</h3>
                  <p>{value.status_message}</p>
                </div>
                <dl>
                  <div><dt>{isMedia ? "Duration" : "Chunks"}</dt><dd>{mediaValue ? (mediaValue.duration_seconds ? `${Math.round(mediaValue.duration_seconds / 60)} min` : "—") : documentValue?.chunk_count}</dd></div>
                  <div><dt>Language</dt><dd>{mediaValue ? mediaValue.detected_language?.toUpperCase() ?? "Auto" : "Text"}</dd></div>
                  <div><dt>Size</dt><dd>{formatBytes(value.size_bytes)}</dd></div>
                </dl>
                <div className="source-card-actions">
                  <a href={isMedia ? `/media/${value.id}` : `/documents/${value.id}`}>
                    {ready ? "Explore source" : "Inspect pipeline"} <ArrowRight size={14} />
                  </a>
                  {!ready && value.status === "failed" && (
                    <button
                      onClick={() =>
                        void (isMedia ? retryMedia(value.id) : retryDocument(value.id)).then(loadSources)
                      }
                    >
                      Retry
                    </button>
                  )}
                </div>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
