import {
  ArrowDownToLine,
  ArrowRight,
  Bot,
  Captions,
  CheckCircle2,
  Clock3,
  ExternalLink,
  FileJson,
  FileText,
  Languages,
  ListChecks,
  LoaderCircle,
  Play,
  Search,
  Send,
  Sparkles,
  Target,
  Users,
  Video,
} from "lucide-react";
import { type FormEvent, useEffect, useMemo, useRef, useState } from "react";

import {
  askMedia,
  getMedia,
  getTranscript,
  getVideoIntelligence,
  listKnowledgeBases,
  listMedia,
  mediaContentUrl,
  mediaExportUrl,
  searchTranscript,
} from "../api/client";
import { CitationList } from "../components/CitationList";
import { EmptyState } from "../components/EmptyState";
import { StatusBadge } from "../components/StatusBadge";
import type {
  Citation,
  KnowledgeBase,
  MediaDetail,
  MediaSource,
  Transcript,
  TranscriptSegment,
  VideoIntelligence,
} from "../types";

interface VideoPageProps {
  mediaId?: string;
}

function formatTimestamp(seconds: number): string {
  const whole = Math.max(0, Math.floor(seconds));
  return `${Math.floor(whole / 60)}:${(whole % 60).toString().padStart(2, "0")}`;
}

export function VideoPage({ mediaId: routeMediaId }: VideoPageProps) {
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [knowledgeBaseId, setKnowledgeBaseId] = useState("");
  const [media, setMedia] = useState<MediaSource[]>([]);
  const [selectedId, setSelectedId] = useState(routeMediaId ?? "");
  const [selected, setSelected] = useState<MediaDetail | null>(null);
  const [transcript, setTranscript] = useState<Transcript | null>(null);
  const [intelligence, setIntelligence] = useState<VideoIntelligence | null>(null);
  const [search, setSearch] = useState("");
  const [searchResults, setSearchResults] = useState<TranscriptSegment[] | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [activeTime, setActiveTime] = useState(
    Number(new URLSearchParams(window.location.search).get("t") ?? 0),
  );
  const [question, setQuestion] = useState("");
  const [sessionId, setSessionId] = useState<string | undefined>();
  const [answer, setAnswer] = useState<{ text: string; citations: Citation[] } | null>(null);
  const [asking, setAsking] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const playerRef = useRef<HTMLVideoElement | HTMLAudioElement>(null);

  useEffect(() => {
    listKnowledgeBases()
      .then(async (result) => {
        setKnowledgeBases(result.items);
        if (routeMediaId) {
          const detail = await getMedia(routeMediaId);
          setKnowledgeBaseId(detail.knowledge_base_id);
        } else if (result.items[0]) {
          setKnowledgeBaseId(result.items[0].id);
        }
      })
      .catch((reason: unknown) =>
        setError(reason instanceof Error ? reason.message : "Unable to load video sources."),
      )
      .finally(() => setLoading(false));
  }, [routeMediaId]);

  useEffect(() => {
    if (!knowledgeBaseId) return;
    listMedia(knowledgeBaseId)
      .then((result) => {
        setMedia(result.items);
        if (!selectedId && result.items[0]) setSelectedId(result.items[0].id);
      })
      .catch((reason: unknown) =>
        setError(reason instanceof Error ? reason.message : "Unable to load media."),
      );
  }, [knowledgeBaseId]);

  useEffect(() => {
    if (!selectedId) return;
    let active = true;
    let timeout: number | undefined;
    async function loadSelection() {
      try {
        const detail = await getMedia(selectedId);
        if (!active) return;
        setSelected(detail);
        if (detail.status === "ready") {
          const [nextTranscript, nextIntelligence] = await Promise.all([
            getTranscript(selectedId),
            getVideoIntelligence(selectedId),
          ]);
          if (active) {
            setTranscript(nextTranscript);
            setIntelligence(nextIntelligence);
          }
        } else if (detail.status !== "failed") {
          timeout = window.setTimeout(() => void loadSelection(), 1500);
        }
      } catch (reason) {
        if (active) {
          setError(reason instanceof Error ? reason.message : "Unable to open this media.");
        }
      }
    }
    setTranscript(null);
    setIntelligence(null);
    void loadSelection();
    return () => {
      active = false;
      if (timeout) window.clearTimeout(timeout);
    };
  }, [selectedId]);

  useEffect(() => {
    if (playerRef.current && activeTime > 0) {
      playerRef.current.currentTime = activeTime;
    }
  }, [selected?.id]);

  useEffect(() => {
    if (!selectedId || search.trim().length < 2) {
      setSearchResults(null);
      return;
    }
    setSearchResults(null);
    let active = true;
    const timeout = window.setTimeout(() => {
      searchTranscript(selectedId, search.trim())
        .then((values) => {
          if (active) setSearchResults(values);
        })
        .catch((reason: unknown) => {
          if (active) {
            setError(
              reason instanceof Error
                ? reason.message
                : "Unable to search this transcript.",
            );
          }
        });
    }, 250);
    return () => {
      active = false;
      window.clearTimeout(timeout);
    };
  }, [search, selectedId]);

  const visibleSegments = useMemo(() => {
    if (!transcript) return [];
    if (!search.trim()) return transcript.segments;
    return searchResults ?? [];
  }, [transcript, search, searchResults]);

  const activeSegment = transcript?.segments.find(
    (segment) => activeTime >= segment.start_time && activeTime <= segment.end_time,
  );

  function seek(seconds: number) {
    setActiveTime(seconds);
    if (playerRef.current) {
      playerRef.current.currentTime = seconds;
      void playerRef.current.play();
    }
  }

  async function loadMoreSegments() {
    if (!selectedId || !transcript || loadingMore) return;
    setLoadingMore(true);
    try {
      const next = await getTranscript(selectedId, transcript.segments.length);
      setTranscript((current) =>
        current
          ? {
              ...current,
              segments: [...current.segments, ...next.segments],
              limit: current.segments.length + next.segments.length,
            }
          : current,
      );
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Unable to load more transcript segments.",
      );
    } finally {
      setLoadingMore(false);
    }
  }

  async function submitQuestion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected || !question.trim()) return;
    setAsking(true);
    setError(null);
    try {
      const result = await askMedia(selected.id, question.trim(), sessionId);
      setSessionId(result.session_id);
      setAnswer({ text: result.answer, citations: result.citations });
      setQuestion("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to answer from this video.");
    } finally {
      setAsking(false);
    }
  }

  if (!loading && knowledgeBases.length === 0) {
    return (
      <EmptyState
        title="No video workspace yet"
        description="Create a knowledge base, then add an audio file, video, or public link."
        action={<a className="button primary" href="/upload">Add a video source</a>}
      />
    );
  }

  return (
    <section className="video-page">
      <header className="video-page-header">
        <div>
          <span className="eyebrow">Multimodal workspace</span>
          <h1>Video intelligence</h1>
        </div>
        <div className="video-selectors">
          <select value={knowledgeBaseId} onChange={(event) => setKnowledgeBaseId(event.target.value)}>
            {knowledgeBases.map((value) => <option key={value.id} value={value.id}>{value.name}</option>)}
          </select>
          <select value={selectedId} onChange={(event) => setSelectedId(event.target.value)}>
            <option value="">Choose a video or recording</option>
            {media.map((value) => <option key={value.id} value={value.id}>{value.title}</option>)}
          </select>
          <a className="button secondary" href="/upload"><Video size={16} /> Add media</a>
        </div>
      </header>

      {error && <div className="notice error">{error}</div>}

      {!selected ? (
        <EmptyState
          title="Select a media source"
          description="Explore synchronized transcripts, chapters, summaries, decisions, and grounded answers."
        />
      ) : selected.status !== "ready" ? (
        <section className="video-processing">
          <span className="processing-emblem">
            {selected.status === "failed" ? <Target size={30} /> : <LoaderCircle className="spin" size={30} />}
          </span>
          <StatusBadge status={selected.status} />
          <h2>{selected.status === "failed" ? "This source needs attention." : "Building media intelligence."}</h2>
          <p>{selected.safe_error_message ?? selected.status_message}</p>
          <div className="media-stage-line" aria-label="Media processing lifecycle">
            {["Validate", "Metadata", "Audio", "Transcript", "Index", "Summarize"].map(
              (stage, index) => (
                <span key={stage} className={index < selected.progress_stage / 2 ? "complete" : ""}>
                  <i>{index + 1}</i>{stage}
                </span>
              ),
            )}
          </div>
          {selected.status === "failed" && <a className="button primary" href="/upload">Review and retry</a>}
        </section>
      ) : (
        <>
          <div className="video-workspace">
            <section className="media-stage">
              {selected.source_kind === "upload" ? (
                selected.media_type?.startsWith("audio") ? (
                  <audio
                    ref={playerRef as React.RefObject<HTMLAudioElement>}
                    src={mediaContentUrl(selected.id)}
                    controls
                    onTimeUpdate={(event) => setActiveTime(event.currentTarget.currentTime)}
                  />
                ) : (
                  <video
                    ref={playerRef as React.RefObject<HTMLVideoElement>}
                    src={mediaContentUrl(selected.id)}
                    controls
                    onTimeUpdate={(event) => setActiveTime(event.currentTarget.currentTime)}
                  />
                )
              ) : (
                <div className="linked-media-preview">
                  <span><Play size={26} /></span>
                  <strong>{selected.title}</strong>
                  <p>Transcript imported from a public source.</p>
                  {selected.original_url && <a href={selected.original_url} target="_blank" rel="noreferrer">Open original <ExternalLink size={14} /></a>}
                </div>
              )}
              <div className="media-title">
                <div>
                  <span className="eyebrow">{selected.source_platform}</span>
                  <h2>{selected.title}</h2>
                  <p>{selected.author ?? "Local source"} · {selected.duration_seconds ? formatTimestamp(selected.duration_seconds) : "Duration unavailable"}</p>
                </div>
                <StatusBadge status={selected.status} />
              </div>
              <div className="media-facts">
                <span><Languages size={15} /> {selected.detected_language?.toUpperCase() ?? "Auto"}</span>
                <span><Captions size={15} /> {selected.subtitle_source ?? selected.transcription_status}</span>
                <span><CheckCircle2 size={15} /> {selected.segment_count} segments</span>
              </div>
            </section>

            <section className="transcript-panel">
              <div className="transcript-heading">
                <div>
                  <span className="eyebrow">Synchronized text</span>
                  <h2>Transcript</h2>
                </div>
                <label className="search-field">
                  <Search size={15} />
                  <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Find in transcript" />
                </label>
              </div>
              <div className="transcript-scroll" aria-label="Timestamped transcript">
                {visibleSegments.map((segment) => (
                  <button
                    key={segment.id}
                    className={activeSegment?.id === segment.id ? "transcript-segment active" : "transcript-segment"}
                    onClick={() => seek(segment.start_time)}
                  >
                    <time>{formatTimestamp(segment.start_time)}</time>
                    <span>{segment.text}</span>
                  </button>
                ))}
                {!search.trim() &&
                  transcript &&
                  transcript.segments.length < transcript.total_segments && (
                    <button
                      className="transcript-load-more"
                      onClick={() => void loadMoreSegments()}
                      disabled={loadingMore}
                    >
                      {loadingMore
                        ? "Loading more segments…"
                        : `Load more · ${transcript.segments.length} of ${transcript.total_segments}`}
                    </button>
                  )}
                {search.trim().length >= 2 && searchResults === null && (
                  <p className="muted-copy">Searching the complete transcript…</p>
                )}
                {visibleSegments.length === 0 &&
                  (!search.trim() || searchResults !== null) && (
                    <p className="muted-copy">No transcript segment matches that search.</p>
                  )}
              </div>
            </section>
          </div>

          <div className="video-intelligence-grid">
            <section className="intelligence-summary">
              <div className="section-heading">
                <div><span className="eyebrow">Distilled understanding</span><h2>Summary</h2></div>
                <Sparkles size={19} />
              </div>
              <p>{intelligence?.detailed_summary}</p>
              <div className="key-point-list">
                {intelligence?.key_points.slice(0, 5).map((value) => (
                  <div key={value}><CheckCircle2 size={15} /><span>{value}</span></div>
                ))}
              </div>
            </section>

            <section className="chapter-panel">
              <div className="section-heading">
                <div><span className="eyebrow">Navigation</span><h2>Chapters</h2></div>
                <Clock3 size={18} />
              </div>
              {intelligence?.chapters.map((chapter) => (
                <button key={chapter.chapter_index} onClick={() => seek(chapter.start_time)}>
                  <time>{formatTimestamp(chapter.start_time)}</time>
                  <span><strong>{chapter.title}</strong><small>{chapter.summary}</small></span>
                  <Play size={14} />
                </button>
              ))}
            </section>

            <section className="video-signals">
              <div><span><ListChecks size={17} /> Action items</span><strong>{intelligence?.action_items.length ?? 0}</strong></div>
              <div><span><Target size={17} /> Decisions</span><strong>{intelligence?.decisions.length ?? 0}</strong></div>
              <div><span><Users size={17} /> Entities</span><strong>{intelligence?.entities.length ?? 0}</strong></div>
              {intelligence?.action_items.slice(0, 3).map((value) => <p key={value.text}>{value.text}</p>)}
            </section>
          </div>

          <section className="ask-video">
            <div className="ask-video-copy">
              <span className="ask-video-icon"><Bot size={22} /></span>
              <div><span className="eyebrow">Scoped research</span><h2>Ask this video</h2><p>Answers cite the exact transcript timestamps used.</p></div>
            </div>
            {answer && (
              <div className="video-answer">
                <p>{answer.text}</p>
                <CitationList citations={answer.citations} />
              </div>
            )}
            <form onSubmit={submitQuestion}>
              <input value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="What decision did the team make?" />
              <button
                className="send-button"
                disabled={!question.trim() || asking}
                aria-label="Ask this video"
              >
                {asking ? <LoaderCircle className="spin" size={17} /> : <Send size={17} />}
              </button>
            </form>
          </section>

          <section className="export-strip">
            <span><ArrowDownToLine size={18} /><strong>Take the intelligence with you</strong></span>
            <a href={mediaExportUrl(selected.id, "transcript.txt")}><FileText size={15} /> Transcript TXT</a>
            <a href={mediaExportUrl(selected.id, "transcript.md")}><FileText size={15} /> Transcript Markdown</a>
            <a href={mediaExportUrl(selected.id, "transcript.json")}><FileJson size={15} /> Transcript JSON</a>
            <a href={mediaExportUrl(selected.id, "summary.md")}><Sparkles size={15} /> Summary Markdown</a>
          </section>
        </>
      )}
    </section>
  );
}
