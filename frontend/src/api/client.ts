import type {
  ChatSession,
  ChatSessionDetail,
  Citation,
  ComparisonResult,
  DocumentChunkList,
  DocumentExtraction,
  DocumentList,
  DocumentPreview,
  DocumentRecord,
  KnowledgeBase,
  KnowledgeBaseList,
  MediaDetail,
  MediaList,
  MediaSource,
  RagAnswer,
  RagConfiguration,
  ReportResult,
  SummaryKind,
  SummaryResult,
  Transcript,
  TranscriptSegment,
  VideoIntelligence,
} from "../types";

// A production bundle is served by FastAPI, so API traffic must stay on the
// same origin. The override is intentionally development-only for Vite and the
// deterministic browser-test server.
const API_BASE_URL = import.meta.env.PROD
  ? "/api/v1"
  : (import.meta.env.VITE_API_BASE_URL ?? "/api/v1");

/** Default timeout for normal API requests (ms). */
const DEFAULT_TIMEOUT_MS = 30_000;

/** Extended timeout for intelligence operations (ms). */
const INTELLIGENCE_TIMEOUT_MS = 150_000;

interface ErrorEnvelope {
  error?: {
    code?: string;
    message?: string;
  };
  detail?: string;
}

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly code: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function fetchWithTimeout(
  path: string,
  options?: RequestInit,
  timeoutMs: number = DEFAULT_TIMEOUT_MS,
): Promise<Response> {
  const controller = new AbortController();
  let timedOut = false;
  const timer = window.setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);
  const callerSignal = options?.signal;
  const abortFromCaller = () => controller.abort(callerSignal?.reason);
  if (callerSignal?.aborted) abortFromCaller();
  else callerSignal?.addEventListener("abort", abortFromCaller, { once: true });

  const headers = new Headers(options?.headers);
  const token = window.localStorage.getItem("token");
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  try {
    return await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers,
      signal: controller.signal,
    });
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (
      typeof error === "object" &&
      error !== null &&
      "name" in error &&
      error.name === "AbortError"
    ) {
      throw new ApiError(
        timedOut
          ? "The request timed out. The service may be busy — please retry."
          : "The request was canceled.",
        0,
        timedOut ? "request_timeout" : "request_aborted",
      );
    }
    throw new ApiError(
      "Unable to reach EnterpriseRAG. Check that the service is running and retry.",
      0,
      "network_error",
    );
  } finally {
    window.clearTimeout(timer);
    callerSignal?.removeEventListener("abort", abortFromCaller);
  }
}

async function responseError(response: Response): Promise<ApiError> {
  let payload: ErrorEnvelope = {};
  try {
    payload = (await response.json()) as ErrorEnvelope;
  } catch {
    // A proxy or network edge may return a non-JSON failure response.
  }
  return new ApiError(
    payload.error?.message ?? payload.detail ?? "The request could not be completed.",
    response.status,
    payload.error?.code ?? "request_failed",
  );
}

async function request<T>(
  path: string,
  options?: RequestInit,
  timeoutMs: number = DEFAULT_TIMEOUT_MS,
): Promise<T> {
  const response = await fetchWithTimeout(path, options, timeoutMs);
  if (!response.ok) throw await responseError(response);
  return (await response.json()) as T;
}

async function requestVoid(path: string, options?: RequestInit): Promise<void> {
  const response = await fetchWithTimeout(path, options);
  if (!response.ok) throw await responseError(response);
}

export function listKnowledgeBases(): Promise<KnowledgeBaseList> {
  return request<KnowledgeBaseList>("/knowledge-bases");
}

export function createKnowledgeBase(input: {
  name: string;
  description?: string;
}): Promise<KnowledgeBase> {
  return request<KnowledgeBase>("/knowledge-bases", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export function listDocuments(knowledgeBaseId: string): Promise<DocumentList> {
  return request<DocumentList>(`/knowledge-bases/${knowledgeBaseId}/documents`);
}

export function uploadDocument(
  knowledgeBaseId: string,
  file: File,
): Promise<DocumentRecord> {
  const body = new FormData();
  body.append("file", file);
  return request<DocumentRecord>(`/knowledge-bases/${knowledgeBaseId}/documents`, {
    method: "POST",
    body,
  });
}

export function getDocument(documentId: string): Promise<DocumentRecord> {
  return request<DocumentRecord>(`/documents/${documentId}`);
}

export function processDocument(documentId: string): Promise<DocumentRecord> {
  return request<DocumentRecord>(`/documents/${documentId}/process`, {
    method: "POST",
  });
}

export function retryDocument(documentId: string): Promise<DocumentRecord> {
  return request<DocumentRecord>(`/documents/${documentId}/retry`, {
    method: "POST",
  });
}

export function getProcessingStatus(documentId: string): Promise<DocumentRecord> {
  return request<DocumentRecord>(`/documents/${documentId}/processing`);
}

export function getExtraction(documentId: string): Promise<DocumentExtraction> {
  return request<DocumentExtraction>(`/documents/${documentId}/extraction`);
}

export function getDocumentPreview(documentId: string): Promise<DocumentPreview> {
  return request<DocumentPreview>(`/documents/${documentId}/preview?limit=20000`);
}

export function getDocumentChunks(
  documentId: string,
  page = 1,
  pageSize = 25,
): Promise<DocumentChunkList> {
  return request<DocumentChunkList>(
    `/documents/${documentId}/chunks?page=${page}&page_size=${pageSize}`,
  );
}

export function deleteDocument(documentId: string): Promise<void> {
  return requestVoid(`/documents/${documentId}`, { method: "DELETE" });
}

export function askKnowledgeBase(input: {
  knowledgeBaseId: string;
  question: string;
  sessionId?: string;
  debug?: boolean;
  responseMode?: "concise" | "detailed";
}): Promise<RagAnswer> {
  return request<RagAnswer>(
    `/knowledge-bases/${input.knowledgeBaseId}/ask`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question: input.question,
        session_id: input.sessionId,
        debug: input.debug ?? false,
        response_mode: input.responseMode ?? "concise",
      }),
    },
    INTELLIGENCE_TIMEOUT_MS,
  );
}

export async function listChatSessions(knowledgeBaseId?: string): Promise<ChatSession[]> {
  const query = knowledgeBaseId
    ? `?knowledge_base_id=${encodeURIComponent(knowledgeBaseId)}`
    : "";
  const response = await request<{ items: ChatSession[]; total: number }>(
    `/chat-sessions${query}`,
  );
  return response.items;
}

export function getChatSession(sessionId: string): Promise<ChatSessionDetail> {
  return request<ChatSessionDetail>(`/chat-sessions/${sessionId}`);
}

export function deleteChatSession(sessionId: string): Promise<void> {
  return requestVoid(`/chat-sessions/${sessionId}`, { method: "DELETE" });
}

export function createSummary(input: {
  knowledgeBaseId: string;
  documentIds: string[];
  kind: SummaryKind;
  sectionIndex?: number;
}): Promise<SummaryResult> {
  return request<SummaryResult>(
    "/intelligence/summaries",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        knowledge_base_id: input.knowledgeBaseId,
        document_ids: input.documentIds,
        kind: input.kind,
        section_index: input.sectionIndex,
      }),
    },
    INTELLIGENCE_TIMEOUT_MS,
  );
}

export function compareDocuments(input: {
  knowledgeBaseId: string;
  documentIds: string[];
}): Promise<ComparisonResult> {
  return request<ComparisonResult>(
    "/intelligence/comparisons",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        knowledge_base_id: input.knowledgeBaseId,
        document_ids: input.documentIds,
      }),
    },
    INTELLIGENCE_TIMEOUT_MS,
  );
}

export function createReport(input: {
  knowledgeBaseId: string;
  documentIds: string[];
  title: string;
  objective: string;
}): Promise<ReportResult> {
  return request<ReportResult>(
    "/intelligence/reports",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        knowledge_base_id: input.knowledgeBaseId,
        document_ids: input.documentIds,
        title: input.title,
        objective: input.objective,
      }),
    },
    INTELLIGENCE_TIMEOUT_MS,
  );
}

export function originalDocumentUrl(documentId: string): string {
  return `${API_BASE_URL}/documents/${documentId}/content`;
}

export function getRagConfiguration(): Promise<RagConfiguration> {
  return request<RagConfiguration>("/rag/config");
}

export function citationLocation(citation: Citation): string {
  if (citation.timestamp_start != null) {
    const minutes = Math.floor(citation.timestamp_start / 60);
    const seconds = Math.floor(citation.timestamp_start % 60);
    return `${minutes}:${seconds.toString().padStart(2, "0")}`;
  }
  if (citation.page_number != null) return `Page ${citation.page_number}`;
  if (citation.section_index != null) return `Section ${citation.section_index + 1}`;
  return "Source passage";
}

export function listMedia(knowledgeBaseId: string): Promise<MediaList> {
  return request<MediaList>(`/knowledge-bases/${knowledgeBaseId}/media`);
}

export function uploadMedia(
  knowledgeBaseId: string,
  file: File,
): Promise<MediaSource> {
  const body = new FormData();
  body.append("file", file);
  body.append("auto_process", "true");
  return request<MediaSource>(`/knowledge-bases/${knowledgeBaseId}/media`, {
    method: "POST",
    body,
  });
}

export function linkMedia(
  knowledgeBaseId: string,
  url: string,
): Promise<MediaSource> {
  return request<MediaSource>(`/knowledge-bases/${knowledgeBaseId}/media/from-url`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url, auto_process: true }),
  });
}

export function getMedia(mediaId: string): Promise<MediaDetail> {
  return request<MediaDetail>(`/media/${mediaId}`);
}

export function getTranscript(
  mediaId: string,
  offset = 0,
  limit = 250,
): Promise<Transcript> {
  return request<Transcript>(
    `/media/${mediaId}/transcript?offset=${offset}&limit=${limit}&include_full_text=false`,
  );
}

export async function searchTranscript(
  mediaId: string,
  query: string,
): Promise<TranscriptSegment[]> {
  const result = await request<{
    results: Array<{ segment: TranscriptSegment }>;
  }>(
    `/media/${mediaId}/transcript/search?query=${encodeURIComponent(query)}`,
  );
  return result.results.map((value) => value.segment);
}

export function getVideoIntelligence(mediaId: string): Promise<VideoIntelligence> {
  return request<VideoIntelligence>(`/media/${mediaId}/intelligence`);
}

export function retryMedia(mediaId: string): Promise<MediaSource> {
  return request<MediaSource>(`/media/${mediaId}/retry`, { method: "POST" });
}

export function askMedia(
  mediaId: string,
  question: string,
  sessionId?: string,
): Promise<RagAnswer> {
  return request<RagAnswer>(
    `/media/${mediaId}/ask`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question,
        session_id: sessionId,
        debug: true,
        response_mode: "concise",
      }),
    },
    INTELLIGENCE_TIMEOUT_MS,
  );
}

export function mediaContentUrl(mediaId: string): string {
  return `${API_BASE_URL}/media/${mediaId}/content`;
}

export function mediaExportUrl(mediaId: string, kind: string): string {
  return `${API_BASE_URL}/media/${mediaId}/export/${kind}`;
}

export function seedDemoWorkspace(): Promise<{ status: string; knowledge_base_id: string; message: string }> {
  return request("/demo/seed", { method: "POST" });
}

export function listTemplates(): Promise<Array<{
  id: string;
  title: string;
  description: string;
  category: string;
  prompt_instruction: string;
  supported_source_types: string[];
  output_schema_type: string;
  safety_classification: string;
  icon_name: string;
}>> {
  return request("/templates");
}

export function submitFeedback(input: {
  knowledgeBaseId: string;
  question: string;
  answer: string;
  rating: string;
  category?: string;
  comment?: string;
  chatMessageId?: string;
}): Promise<{ id: string; status: string }> {
  return request("/feedback", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      knowledge_base_id: input.knowledgeBaseId,
      question: input.question,
      answer: input.answer,
      rating: input.rating,
      category: input.category ?? "other",
      comment: input.comment,
      chat_message_id: input.chatMessageId,
    }),
  });
}

export function getFeedbackAnalytics(): Promise<{
  total_feedback: number;
  helpful_count: number;
  unhelpful_count: number;
  helpful_rate: number;
  complaint_categories: Record<string, number>;
}> {
  return request("/feedback/analytics");
}

export function convertFeedbackToEval(feedbackId: string, datasetId: string): Promise<{ case_id: string; status: string }> {
  return request(`/feedback/${feedbackId}/convert-to-eval`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dataset_id: datasetId }),
  });
}

export function listEvaluationDatasets(): Promise<Array<{
  id: string;
  knowledge_base_id: string;
  name: string;
  description: string | null;
  case_count: number;
}>> {
  return request("/evaluation/datasets");
}

export function listEvaluationRuns(): Promise<Array<{
  id: string;
  dataset_id: string;
  engine: string;
  model_name: string;
  total_cases: number;
  passed_cases: number;
  failed_cases: number;
  correctness_rate: number;
  faithfulness_rate: number;
  citation_accuracy: number;
  median_latency_ms: number;
  p95_latency_ms: number;
}>> {
  return request("/evaluation/runs");
}

export function runEvaluation(datasetId: string): Promise<{
  id: string;
  dataset_id: string;
  engine: string;
  model_name: string;
  total_cases: number;
  passed_cases: number;
  failed_cases: number;
  correctness_rate: number;
  faithfulness_rate: number;
  citation_accuracy: number;
  median_latency_ms: number;
  p95_latency_ms: number;
}> {
  return request(`/evaluation/runs?dataset_id=${encodeURIComponent(datasetId)}`, {
    method: "POST",
  }, INTELLIGENCE_TIMEOUT_MS);
}

export function registerUser(input: {
  email: string;
  password: string;
  full_name?: string;
}): Promise<{ id: string; email: string; full_name: string; role: string; is_active: boolean }> {
  return request("/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export function loginUser(input: {
  email: string;
  password: string;
}): Promise<{ access_token: string; token_type: string; user_id: string; email: string; role: string }> {
  return request("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}
