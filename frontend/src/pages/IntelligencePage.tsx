import { type FormEvent, useCallback, useEffect, useState } from "react";

import {
  compareDocuments,
  createReport,
  createSummary,
  listDocuments,
  listKnowledgeBases,
} from "../api/client";
import { CitationList } from "../components/CitationList";
import { EmptyState } from "../components/EmptyState";
import { StatusBadge } from "../components/StatusBadge";
import { VerificationBadge } from "../components/VerificationBadge";
import type {
  ComparisonResult,
  DocumentRecord,
  KnowledgeBase,
  ReportResult,
  SummaryKind,
  SummaryResult,
} from "../types";
import { contentDirection, type OutputLanguage } from "../utils/language";

type Mode = "summary" | "comparison" | "report";

export function IntelligencePage() {
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [knowledgeBaseId, setKnowledgeBaseId] = useState("");
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [mode, setMode] = useState<Mode>("summary");
  const [summaryKind, setSummaryKind] =
    useState<SummaryKind>("executive_summary");
  const [sectionIndex, setSectionIndex] = useState(0);
  const [reportTitle, setReportTitle] = useState("Knowledge Intelligence Report");
  const [objective, setObjective] = useState("");
  const [outputLanguage, setOutputLanguage] = useState<OutputLanguage>("auto");
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [result, setResult] = useState<
    SummaryResult | ComparisonResult | ReportResult | null
  >(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!generating) return;
    setElapsedSeconds(0);
    const started = Date.now();
    const timer = window.setInterval(
      () => setElapsedSeconds(Math.floor((Date.now() - started) / 1000)),
      1000,
    );
    return () => window.clearInterval(timer);
  }, [generating]);

  useEffect(() => {
    const requestedKnowledgeBaseId = new URLSearchParams(window.location.search).get(
      "knowledgeBase",
    );
    listKnowledgeBases()
      .then((response) => {
        setKnowledgeBases(response.items);
        const requestedKnowledgeBase = response.items.find(
          (knowledgeBase) => knowledgeBase.id === requestedKnowledgeBaseId,
        );
        const initialKnowledgeBase = requestedKnowledgeBase ?? response.items[0];
        if (initialKnowledgeBase) setKnowledgeBaseId(initialKnowledgeBase.id);
      })
      .catch((reason: unknown) =>
        setError(reason instanceof Error ? reason.message : "Unable to load knowledge bases."),
      )
      .finally(() => setLoading(false));
  }, []);

  const loadDocumentsForKnowledgeBase = useCallback(async () => {
    if (!knowledgeBaseId) {
      setDocuments([]);
      return;
    }
    try {
      const response = await listDocuments(knowledgeBaseId);
      setDocuments(response.items);
      setSelectedIds([]);
      setResult(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to load documents.");
    }
  }, [knowledgeBaseId]);

  useEffect(() => {
    void loadDocumentsForKnowledgeBase();
  }, [loadDocumentsForKnowledgeBase]);

  function toggleDocument(documentId: string) {
    setSelectedIds((current) =>
      current.includes(documentId)
        ? current.filter((id) => id !== documentId)
        : [...current, documentId],
    );
  }

  function validateSelection(): string | null {
    if (mode === "comparison" && selectedIds.length < 2) {
      return "Select at least two ready documents to compare.";
    }
    if (mode === "report" && selectedIds.length < 1) {
      return "Select at least one ready document for the report.";
    }
    if (
      mode === "summary" &&
      (summaryKind === "whole_document" || summaryKind === "section") &&
      selectedIds.length !== 1
    ) {
      return "This summary type requires exactly one selected document.";
    }
    return null;
  }

  async function generate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const selectionError = validateSelection();
    if (selectionError) {
      setError(selectionError);
      return;
    }
    if (generating) return;
    setGenerating(true);
    setError(null);
    setResult(null);
    try {
      if (mode === "summary") {
        setResult(
          await createSummary({
            knowledgeBaseId,
            documentIds: selectedIds,
            kind: summaryKind,
            sectionIndex: summaryKind === "section" ? sectionIndex : undefined,
            outputLanguage,
          }),
        );
      } else if (mode === "comparison") {
        setResult(
          await compareDocuments({
            knowledgeBaseId,
            documentIds: selectedIds,
            outputLanguage,
          }),
        );
      } else {
        setResult(
          await createReport({
            knowledgeBaseId,
            documentIds: selectedIds,
            title: reportTitle,
            objective,
            outputLanguage,
          }),
        );
      }
    } catch (reason) {
      const isApiError = reason instanceof Error && "code" in reason;
      const code = isApiError ? (reason as { code: string }).code : "";
      if (code === "request_timeout" || code === "generation_timeout") {
        setError(
          "The operation timed out. The local model may be under heavy load. " +
            "Try fewer sources, a narrower scope, or retry in a moment.",
        );
      } else if (code === "model_provider_unavailable" || code === "generation_queue_full") {
        setError(
          "The model is currently unavailable or busy. Please wait a moment and retry.",
        );
      } else {
        setError(
          reason instanceof Error ? reason.message : "Unable to generate the analysis.",
        );
      }
    } finally {
      setGenerating(false);
    }
  }

  function downloadMarkdown(report: ReportResult) {
    const blob = new Blob([report.markdown], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = window.document.createElement("a");
    link.href = url;
    link.download = `${report.title.toLowerCase().replace(/[^a-z0-9]+/g, "-")}.md`;
    link.click();
    URL.revokeObjectURL(url);
  }

  const readyDocuments = documents.filter(
    (document) => document.status === "ready_for_chat",
  );

  return (
    <section>
      <div className="page-header">
        <div>
          <span className="eyebrow">Advanced analysis</span>
          <h1>Intelligence studio</h1>
          <p>
            Generate grounded summaries, comparisons, and research reports from explicit
            source selections.
          </p>
        </div>
      </div>

      {error && (
        <div className="notice error" role="alert" dir={contentDirection(error)}>
          {error}
        </div>
      )}

      <div className="mode-tabs" role="tablist" aria-label="Intelligence workflow">
        {(["summary", "comparison", "report"] as const).map((value) => (
          <button
            key={value}
            className={mode === value ? "mode-tab active" : "mode-tab"}
            onClick={() => {
              setMode(value);
              setResult(null);
              setError(null);
            }}
            role="tab"
            aria-selected={mode === value}
          >
            {value === "summary"
              ? "Summarize"
              : value === "comparison"
                ? "Compare"
                : "Research report"}
          </button>
        ))}
      </div>

      <div className="intelligence-layout">
        <form className="panel intelligence-form" onSubmit={generate}>
          <label>
            Knowledge base
            <select
              value={knowledgeBaseId}
              onChange={(event) => setKnowledgeBaseId(event.target.value)}
              disabled={loading || generating}
            >
              {knowledgeBases.map((knowledgeBase) => (
                <option value={knowledgeBase.id} key={knowledgeBase.id}>
                  {knowledgeBase.name}
                </option>
              ))}
            </select>
          </label>

          <fieldset className="document-selector">
            <legend>Source documents</legend>
            {readyDocuments.length === 0 ? (
              <p className="muted-copy">Process documents before analysis.</p>
            ) : (
              readyDocuments.map((document) => (
                <label className="document-option" key={document.id}>
                  <input
                    type="checkbox"
                    checked={selectedIds.includes(document.id)}
                    onChange={() => toggleDocument(document.id)}
                  />
                  <span>
                    <strong>{document.name}</strong>
                    <small>{document.chunk_count} indexed chunks</small>
                  </span>
                  <StatusBadge status={document.status} />
                </label>
              ))
            )}
          </fieldset>

          {mode === "summary" && (
            <>
              <label>
                Summary type
                <select
                  value={summaryKind}
                  onChange={(event) =>
                    setSummaryKind(event.target.value as SummaryKind)
                  }
                >
                  <option value="executive_summary">Executive summary</option>
                  <option value="whole_document">Whole document</option>
                  <option value="knowledge_base">Knowledge base synthesis</option>
                  <option value="section">Specific section</option>
                  <option value="key_points">Key points</option>
                </select>
              </label>
              {summaryKind === "section" && (
                <label>
                  Section number
                  <input
                    type="number"
                    min={1}
                    value={sectionIndex + 1}
                    onChange={(event) =>
                      setSectionIndex(Math.max(0, Number(event.target.value) - 1))
                    }
                  />
                </label>
              )}
            </>
          )}

          <label>
            Output language
            <select
              aria-label="Intelligence output language"
              value={outputLanguage}
              onChange={(event) => setOutputLanguage(event.target.value as OutputLanguage)}
              disabled={generating}
            >
              <option value="auto">Automatic</option>
              <option value="ar">Arabic</option>
              <option value="en">English</option>
            </select>
          </label>

          {mode === "report" && (
            <>
              <label>
                Report title
                <input
                  value={reportTitle}
                  onChange={(event) => setReportTitle(event.target.value)}
                  maxLength={200}
                  required
                />
              </label>
              <label>
                Objective
                <textarea
                  value={objective}
                  onChange={(event) => setObjective(event.target.value)}
                  rows={4}
                  maxLength={2000}
                  placeholder="What decision or research objective should this report address?"
                  required
                />
              </label>
            </>
          )}

          <button
            className="button primary"
            type="submit"
            disabled={!knowledgeBaseId || readyDocuments.length === 0 || generating}
          >
            {generating
              ? `Running grounded analysis… ${elapsedSeconds}s`
              : mode === "summary"
                ? "Generate summary"
                : mode === "comparison"
                  ? "Compare documents"
                  : "Generate report"}
          </button>
        </form>

        <article className="panel intelligence-result">
          {!result ? (
            <EmptyState
              title="Analysis result"
              description="Choose indexed sources and a workflow. Generated content will include passage references and a verification result."
            />
          ) : "content" in result ? (
            <>
              <span className="eyebrow">Grounded summary</span>
              <h2>
                {result.output_language === "ar"
                  ? {
                      whole_document: "ملخص المستند",
                      knowledge_base: "توليف قاعدة المعرفة",
                      section: "ملخص القسم",
                      key_points: "النقاط الرئيسية",
                      executive_summary: "الملخص التنفيذي",
                    }[result.kind]
                  : result.kind.replaceAll("_", " ")}
              </h2>
              <p className="analysis-copy" dir={contentDirection(result.content)}>{result.content}</p>
              <VerificationBadge verification={result.verification} />
              <CitationList citations={result.citations} />
            </>
          ) : "common_themes" in result ? (
            <>
              <span className="eyebrow">Structured comparison</span>
              {(result.output_language === "ar"
                ? [
                    ["الموضوعات المشتركة", result.common_themes],
                    ["الاختلافات", result.differences],
                    ["التناقضات", result.contradictions],
                    ["المنهجيات", result.methodologies],
                    ["الاستنتاجات", result.conclusions],
                    ["القيود", result.limitations],
                  ]
                : [
                    ["Common themes", result.common_themes],
                    ["Differences", result.differences],
                    ["Contradictions", result.contradictions],
                    ["Methodologies", result.methodologies],
                    ["Conclusions", result.conclusions],
                    ["Limitations", result.limitations],
                  ]).map(([title, content]) => (
                <section className="analysis-section" key={title}>
                  <h2>{title}</h2>
                  <p dir={contentDirection(content)}>{content}</p>
                </section>
              ))}
              <VerificationBadge verification={result.verification} />
              <CitationList citations={result.citations} />
            </>
          ) : (
            <>
              <div className="section-header compact">
                <div>
                  <span className="eyebrow">Research report</span>
                  <h2>{result.title}</h2>
                </div>
                <button
                  className="button secondary"
                  onClick={() => downloadMarkdown(result)}
                >
                  Export Markdown
                </button>
              </div>
              {(result.output_language === "ar"
                ? [
                    ["الهدف", result.objective],
                    ["الملخص التنفيذي", result.executive_summary],
                    ["النتائج", result.findings],
                    ["المقارنة", result.comparison],
                    ["المخاطر والقيود", result.risks_and_limitations],
                    ["الاستنتاجات", result.conclusions],
                  ]
                : [
                    ["Objective", result.objective],
                    ["Executive summary", result.executive_summary],
                    ["Findings", result.findings],
                    ["Comparison", result.comparison],
                    ["Risks and limitations", result.risks_and_limitations],
                    ["Conclusions", result.conclusions],
                  ]).map(([title, content]) => (
                <section className="analysis-section" key={title}>
                  <h3>{title}</h3>
                  <p dir={contentDirection(content)}>{content}</p>
                </section>
              ))}
              <VerificationBadge verification={result.verification} />
              <CitationList citations={result.cited_sources} />
            </>
          )}
        </article>
      </div>
    </section>
  );
}
