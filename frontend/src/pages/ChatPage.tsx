import {
  ArrowUp,
  Bot,
  BrainCircuit,
  ChevronRight,
  CircleStop,
  Copy,
  FileSearch,
  Gauge,
  History,
  PanelRightOpen,
  Plus,
  RotateCcw,
  ShieldCheck,
  Sparkles,
  Trash2,
} from "lucide-react";
import {
  type FormEvent,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";

import {
  askKnowledgeBase,
  deleteChatSession,
  getChatSession,
  listChatSessions,
  listKnowledgeBases,
} from "../api/client";
import { CitationList } from "../components/CitationList";
import { EmptyState } from "../components/EmptyState";
import { VerificationBadge } from "../components/VerificationBadge";
import type {
  ChatMessage,
  ChatSession,
  Citation,
  KnowledgeBase,
  RagDebug,
  RetrievedSource,
  Verification,
} from "../types";

interface DisplayMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations: Citation[];
  verification?: Verification;
  debug?: RagDebug | null;
  retrievedSources?: RetrievedSource[];
  confidence?: number;
  responseTime?: number;
  supportStatus?: string;
}

function toDisplay(message: ChatMessage): DisplayMessage {
  const verification =
    message.role === "assistant" &&
    message.verification.status &&
    message.verification.explanation
      ? (message.verification as Verification)
      : undefined;
  return {
    id: message.id,
    role: message.role,
    content: message.content,
    citations: message.citations,
    verification,
  };
}

const suggestions = [
  "Summarize the most important policy details.",
  "What evidence supports the main conclusion?",
  "Where do the sources disagree?",
  "What information is missing?",
];

export function ChatPage() {
  const parameters = new URLSearchParams(window.location.search);
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [knowledgeBaseId, setKnowledgeBaseId] = useState(
    parameters.get("knowledgeBase") ?? "",
  );
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [question, setQuestion] = useState(parameters.get("question") ?? "");
  const [debug, setDebug] = useState(false);
  const [responseMode, setResponseMode] = useState<"concise" | "detailed">("concise");
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [asking, setAsking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

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

  const loadSessions = useCallback(async () => {
    if (!knowledgeBaseId) {
      setSessions([]);
      return;
    }
    try {
      setSessions(await listChatSessions(knowledgeBaseId));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to load conversations.");
    }
  }, [knowledgeBaseId]);

  useEffect(() => {
    setSessionId(null);
    setMessages([]);
    void loadSessions();
  }, [knowledgeBaseId, loadSessions]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, asking]);

  async function openSession(nextSessionId: string) {
    setError(null);
    try {
      const detail = await getChatSession(nextSessionId);
      setSessionId(detail.id);
      setMessages(detail.messages.map(toDisplay));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to open the conversation.");
    }
  }

  async function submitQuestion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = question.trim();
    if (!knowledgeBaseId || !value || asking) return;
    const temporaryId = `pending-${Date.now()}`;
    setMessages((current) => [
      ...current,
      { id: temporaryId, role: "user", content: value, citations: [] },
    ]);
    setQuestion("");
    setAsking(true);
    setError(null);
    try {
      const answer = await askKnowledgeBase({
        knowledgeBaseId,
        question: value,
        sessionId: sessionId ?? undefined,
        debug: debug || evidenceOpen,
        responseMode,
      });
      setSessionId(answer.session_id);
      setMessages((current) => [
        ...current,
        {
          id: answer.message_id,
          role: "assistant",
          content: answer.answer,
          citations: answer.citations,
          verification: answer.verification,
          debug: answer.debug,
          retrievedSources: answer.retrieved_sources,
          confidence: answer.confidence,
          responseTime: answer.response_time_ms,
          supportStatus: answer.support_status,
        },
      ]);
      await loadSessions();
    } catch (reason) {
      setMessages((current) => current.filter((message) => message.id !== temporaryId));
      setQuestion(value);
      setError(
        reason instanceof Error ? reason.message : "The grounded answer could not be generated.",
      );
    } finally {
      setAsking(false);
    }
  }

  async function clearConversation() {
    if (sessionId) await deleteChatSession(sessionId);
    setSessionId(null);
    setMessages([]);
    await loadSessions();
  }

  if (!loading && knowledgeBases.length === 0) {
    return (
      <EmptyState
        title="No knowledge base available"
        description="Create a knowledge base and process a source before asking questions."
        action={<a className="button primary" href="/knowledge-bases">Create knowledge base</a>}
      />
    );
  }

  const currentKnowledgeBase = knowledgeBases.find((value) => value.id === knowledgeBaseId);

  return (
    <section className="research-page">
      <header className="research-header">
        <div>
          <span className="eyebrow">Grounded research</span>
          <h1>Ask with evidence.</h1>
        </div>
        <div className="research-scope">
          <label>
            <span>Searching</span>
            <select
              value={knowledgeBaseId}
              onChange={(event) => setKnowledgeBaseId(event.target.value)}
              disabled={asking}
            >
              <option value="">Choose a knowledge base</option>
              {knowledgeBases.map((knowledgeBase) => (
                <option key={knowledgeBase.id} value={knowledgeBase.id}>
                  {knowledgeBase.name}
                </option>
              ))}
            </select>
          </label>
          <span className="model-state"><span /> Local model ready</span>
        </div>
      </header>

      {error && <div className="notice error" role="alert">{error}</div>}

      <div className={`research-layout ${evidenceOpen ? "evidence-visible" : ""}`}>
        <aside className="session-rail">
          <div className="session-rail-heading">
            <span><History size={15} /> Threads</span>
            <button
              className="icon-button"
              onClick={() => {
                setSessionId(null);
                setMessages([]);
              }}
              aria-label="New conversation"
            >
              <Plus size={16} />
            </button>
          </div>
          <button
            className={!sessionId ? "session-button active" : "session-button"}
            onClick={() => {
              setSessionId(null);
              setMessages([]);
            }}
          >
            <Sparkles size={15} />
            <span><strong>New research</strong><small>{currentKnowledgeBase?.name}</small></span>
          </button>
          {sessions.map((chatSession) => (
            <button
              key={chatSession.id}
              className={sessionId === chatSession.id ? "session-button active" : "session-button"}
              onClick={() => void openSession(chatSession.id)}
            >
              <Bot size={15} />
              <span>
                <strong>{chatSession.title}</strong>
                <small>{new Date(chatSession.updated_at).toLocaleDateString()}</small>
              </span>
            </button>
          ))}
          {messages.length > 0 && (
            <button className="clear-thread" onClick={() => void clearConversation()}>
              <Trash2 size={14} /> Clear thread
            </button>
          )}
        </aside>

        <div className="research-canvas">
          <div className="message-list" aria-live="polite">
            {messages.length === 0 ? (
              <div className="research-empty">
                <span className="research-emblem"><BrainCircuit size={30} /></span>
                <span className="eyebrow">Traceable intelligence</span>
                <h2>What do you want to know?</h2>
                <p>
                  I’ll retrieve the strongest evidence, answer precisely, and show
                  exactly where every supported claim came from.
                </p>
                <div className="suggestion-grid">
                  {suggestions.map((value) => (
                    <button key={value} onClick={() => setQuestion(value)}>
                      {value} <ChevronRight size={14} />
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((message) => (
                <article className={`research-message ${message.role}`} key={message.id}>
                  <div className="message-identity">
                    <span>{message.role === "user" ? "FK" : <Bot size={16} />}</span>
                    <strong>{message.role === "user" ? "You" : "EnterpriseRAG"}</strong>
                  </div>
                  <div className="message-body">
                    <p>{message.content}</p>
                    {message.role === "assistant" && (
                      <>
                        <div className="answer-toolbar">
                          <button onClick={() => void navigator.clipboard.writeText(message.content)}>
                            <Copy size={14} /> Copy
                          </button>
                          <button onClick={() => setQuestion("Answer again more concisely.")}>
                            <RotateCcw size={14} /> Regenerate
                          </button>
                          {message.confidence != null && (
                            <span><Gauge size={14} /> {Math.round(message.confidence * 100)}% confidence</span>
                          )}
                          {message.responseTime != null && (
                            <span>{message.responseTime.toFixed(0)} ms</span>
                          )}
                        </div>
                        {message.verification && (
                          <VerificationBadge verification={message.verification} />
                        )}
                        <CitationList citations={message.citations} />
                      </>
                    )}
                  </div>
                </article>
              ))
            )}
            {asking && (
              <div className="research-message assistant pending">
                <div className="message-identity">
                  <span><Bot size={16} /></span><strong>EnterpriseRAG</strong>
                </div>
                <div className="thinking-state">
                  <span className="thinking-orb" />
                  <span>
                    <strong>Reading the strongest evidence…</strong>
                    <small>Hybrid retrieval · reranking · claim verification</small>
                  </span>
                  <CircleStop size={16} />
                </div>
              </div>
            )}
            <div ref={endRef} />
          </div>

          <form className="research-composer" onSubmit={submitQuestion}>
            <textarea
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  event.currentTarget.form?.requestSubmit();
                }
              }}
              placeholder="Ask a precise question about your sources…"
              rows={2}
              maxLength={4000}
              disabled={!knowledgeBaseId || asking}
              aria-label="Ask a grounded question"
            />
            <div className="composer-footer">
              <div>
                <button
                  type="button"
                  className={responseMode === "concise" ? "mode-pill active" : "mode-pill"}
                  onClick={() => setResponseMode("concise")}
                >
                  Concise
                </button>
                <button
                  type="button"
                  className={responseMode === "detailed" ? "mode-pill active" : "mode-pill"}
                  onClick={() => setResponseMode("detailed")}
                >
                  Detailed
                </button>
                <button
                  type="button"
                  className={debug ? "mode-pill active" : "mode-pill"}
                  onClick={() => setDebug((value) => !value)}
                >
                  <FileSearch size={13} /> Explain
                </button>
              </div>
              <button
                className="send-button"
                disabled={!knowledgeBaseId || !question.trim() || asking}
                aria-label="Ask sources"
              >
                <ArrowUp size={18} />
              </button>
            </div>
          </form>
          <p className="research-disclaimer">
            <ShieldCheck size={13} /> Answers are constrained to retrieved sources. Verify critical decisions.
          </p>
        </div>

        <aside className="evidence-drawer">
          <button className="evidence-toggle" onClick={() => setEvidenceOpen((value) => !value)}>
            <PanelRightOpen size={17} />
            <span>Evidence</span>
          </button>
          {evidenceOpen && (
            <div className="evidence-content">
              <div>
                <span className="eyebrow">Developer evidence</span>
                <h2>Retrieval trace</h2>
                <p>Explainability shows evidence and scores—not private chain of thought.</p>
              </div>
              {messages
                .filter((value) => value.role === "assistant")
                .slice(-1)
                .map((message) => (
                  <div key={message.id}>
                    {message.debug && (
                      <dl className="trace-metrics">
                        <div><dt>Strategy</dt><dd>{message.debug.retrieval_diagnostics.strategy}</dd></div>
                        <div><dt>Rewrite</dt><dd>{message.debug.rewritten_query}</dd></div>
                        <div><dt>Generator</dt><dd>{message.debug.generation_model}</dd></div>
                        <div><dt>Device</dt><dd>{message.debug.model_device}</dd></div>
                      </dl>
                    )}
                    <div className="evidence-passages">
                      {message.retrievedSources?.map((source, index) => (
                        <details key={source.chunk_id} open={index === 0}>
                          <summary>
                            <span>{index + 1}</span>
                            <strong>{source.document_name}</strong>
                            <em>{source.score.toFixed(3)}</em>
                          </summary>
                          <p>{source.text}</p>
                          <small>
                            dense {source.dense_score.toFixed(2)} · lexical {source.lexical_score.toFixed(2)} · rerank {source.reranking_score.toFixed(2)}
                          </small>
                        </details>
                      ))}
                    </div>
                  </div>
                ))}
              {messages.every((value) => value.role !== "assistant") && (
                <div className="evidence-placeholder">
                  <FileSearch size={22} />
                  Ask a question to inspect retrieved passages and score fusion.
                </div>
              )}
            </div>
          )}
        </aside>
      </div>
    </section>
  );
}
