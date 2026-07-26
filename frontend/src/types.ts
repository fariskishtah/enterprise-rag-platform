export interface KnowledgeBase {
  id: string;
  name: string;
  description: string | null;
  document_count: number;
  created_at: string;
  updated_at: string;
}

export interface KnowledgeBaseList {
  items: KnowledgeBase[];
  total: number;
}

export type DocumentType = "pdf" | "txt" | "docx";
export type DocumentStatus =
  | "uploaded"
  | "validating"
  | "extracting"
  | "extracted"
  | "chunking"
  | "embedding"
  | "vector_indexing"
  | "indexed"
  | "ready_for_chat"
  | "processing"
  | "ready"
  | "failed";

export interface DocumentRecord {
  id: string;
  knowledge_base_id: string;
  name: string;
  document_type: DocumentType;
  media_type: string;
  size_bytes: number;
  checksum_sha256: string;
  status: DocumentStatus;
  status_message: string | null;
  processing_error: string | null;
  extraction_warnings: string[];
  extraction_metadata: Record<string, unknown>;
  page_count: number | null;
  character_count: number;
  chunk_count: number;
  indexed_chunk_count: number;
  processing_attempts: number;
  embedding_model: string | null;
  processing_started_at: string | null;
  extraction_completed_at: string | null;
  indexing_completed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface DocumentList {
  items: DocumentRecord[];
  total: number;
}

export interface ExtractedSection {
  id: string;
  section_index: number;
  page_number: number | null;
  heading: string | null;
  text: string;
  start_char: number;
  end_char: number;
  metadata: Record<string, unknown>;
}

export interface DocumentExtraction {
  document_id: string;
  filename: string;
  document_type: DocumentType;
  status: DocumentStatus;
  page_count: number | null;
  character_count: number;
  extraction_completed_at: string | null;
  warnings: string[];
  error: string | null;
  metadata: Record<string, unknown>;
  sections: ExtractedSection[];
}

export interface DocumentPreview {
  document_id: string;
  text: string;
  offset: number;
  returned_characters: number;
  total_characters: number;
  truncated: boolean;
}

export interface DocumentChunk {
  id: string;
  document_id: string;
  knowledge_base_id: string;
  chunk_index: number;
  text: string;
  page_number: number | null;
  section_index: number | null;
  start_char: number | null;
  end_char: number | null;
  character_count: number;
  token_estimate: number;
  extraction_metadata: Record<string, unknown>;
  embedding_model: string | null;
  indexed_at: string | null;
}

export interface DocumentChunkList {
  items: DocumentChunk[];
  page: number;
  page_size: number;
  total: number;
}

export type VerificationStatus =
  | "supported"
  | "partially_supported"
  | "unsupported";

export interface Verification {
  status: VerificationStatus;
  claim_support?:
    | "fully_supported"
    | "partially_supported"
    | "unsupported"
    | "contradiction_detected"
    | "missing_answer";
  explanation: string;
  unsupported_statements: string[];
  supported_statements?: string[];
  contradiction_detected?: boolean;
  claim_scores?: Record<string, number>;
}

export interface Citation {
  document_id: string;
  document_name: string;
  chunk_id: string;
  passage: string;
  similarity_score: number;
  page_number: number | null;
  section_index: number | null;
  timestamp_start: number | null;
  timestamp_end: number | null;
  media_source_id: string | null;
  support_score: number;
}

export interface RetrievedSource {
  chunk_id: string;
  document_id: string;
  document_name: string;
  text: string;
  score: number;
  page_number: number | null;
  section_index: number | null;
  chunk_index: number;
  metadata: Record<string, unknown>;
  dense_score: number;
  lexical_score: number;
  reranking_score: number;
  query_coverage: number;
}

export interface RagDebug {
  original_question: string;
  rewritten_query: string;
  final_context: string;
  prompt_template: string;
  embedding_model: string;
  generation_model: string;
  model_device: string;
  timings_ms: Record<string, number>;
  retrieval_diagnostics: {
    strategy?: string;
    candidate_pool?: number;
    selected_chunk_ids?: string[];
    scores?: Array<Record<string, string | number>>;
  };
}

export interface RagAnswer {
  session_id: string;
  message_id: string;
  answer: string;
  direct_answer: string;
  supporting_explanation: string;
  citations: Citation[];
  retrieved_sources: RetrievedSource[];
  verification: Verification;
  retrieval_quality: string;
  confidence: number;
  support_status:
    | "fully_supported"
    | "partially_supported"
    | "unsupported"
    | "contradiction_detected"
    | "missing_answer";
  retrieved_chunk_ids: string[];
  generation_model: string;
  model_used: string;
  response_time: number;
  response_time_ms: number;
  not_found: boolean;
  output_language: "ar" | "en";
  created_at: string;
  debug: RagDebug | null;
}

export interface ChatSession {
  id: string;
  knowledge_base_id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface ChatMessage {
  id: string;
  session_id: string;
  role: "user" | "assistant";
  content: string;
  original_question: string | null;
  rewritten_query: string | null;
  citations: Citation[];
  model_metadata: Record<string, unknown>;
  verification: Partial<Verification>;
  created_at: string;
}

export interface ChatSessionDetail extends ChatSession {
  messages: ChatMessage[];
}

export type SummaryKind =
  | "whole_document"
  | "knowledge_base"
  | "section"
  | "key_points"
  | "executive_summary";

export interface SummaryResult {
  kind: SummaryKind;
  content: string;
  citations: Citation[];
  verification: Verification;
  model_used: string;
  output_language: "ar" | "en";
}

export interface ComparisonResult {
  common_themes: string;
  differences: string;
  contradictions: string;
  methodologies: string;
  conclusions: string;
  limitations: string;
  citations: Citation[];
  verification: Verification;
  model_used: string;
  elapsed_ms?: number;
  generation_calls?: number;
  partial?: boolean;
  output_language: "ar" | "en";
}

export interface ReportResult {
  title: string;
  objective: string;
  executive_summary: string;
  findings: string;
  comparison: string;
  risks_and_limitations: string;
  conclusions: string;
  cited_sources: Citation[];
  verification: Verification;
  markdown: string;
  model_used: string;
  elapsed_ms?: number;
  generation_calls?: number;
  partial?: boolean;
  output_language: "ar" | "en";
}

export interface RagConfiguration {
  embedding_model: string;
  generation_model: string;
  rag_engine: "custom" | "langchain";
  quantization: "none" | "4bit" | "8bit";
  model_device: string;
  embedding_model_cached: boolean;
  generation_model_cached: boolean;
  model_warm: boolean;
  embedding_model_status: "cold" | "loading" | "ready" | "failed";
  generation_model_status: "cold" | "loading" | "ready" | "failed";
  warmup_status: "cold" | "loading" | "ready" | "failed";
  vector_store: string;
  top_k: number;
  candidate_pool: number;
  similarity_threshold: number;
  retrieval_strategy: string;
  score_weights: Record<string, number>;
  chunk_size: number;
  chunk_overlap: number;
  temperature: number;
  generation_top_k: number;
  top_p: number;
  maximum_new_tokens: number;
  repetition_penalty: number;
  do_sample: boolean;
  maximum_context_characters: number;
  conversation_history_messages: number;
  runtime_profile?: string;
  generation_queue_active?: number;
  generation_queue_queued?: number;
  generation_timeout_seconds?: number;
  embedding_reindex_required: boolean;
}

export type MediaStatus =
  | "uploaded_or_linked"
  | "validating"
  | "fetching_metadata"
  | "downloading_or_extracting_subtitles"
  | "extracting_audio"
  | "transcribing"
  | "transcript_ready"
  | "chunking"
  | "embedding"
  | "indexing"
  | "summarising"
  | "ready"
  | "failed";

export interface MediaSource {
  id: string;
  knowledge_base_id: string;
  transcript_document_id: string | null;
  source_kind: "upload" | "public_url" | "youtube";
  original_url: string | null;
  original_filename: string | null;
  media_type: string | null;
  size_bytes: number | null;
  source_platform: string | null;
  title: string;
  author: string | null;
  duration_seconds: number | null;
  detected_language: string | null;
  thumbnail_url: string | null;
  subtitle_source: string | null;
  transcription_status: string;
  status: MediaStatus;
  status_message: string | null;
  progress_stage: number;
  warnings: string[];
  metadata: Record<string, unknown>;
  error_code: string | null;
  safe_error_message: string | null;
  retryable: boolean;
  processing_attempts: number;
  ingestion_date: string | null;
  created_at: string;
  updated_at: string;
}

export interface MediaList {
  items: MediaSource[];
  total: number;
}

export interface MediaDetail extends MediaSource {
  transcript_jobs: Array<{
    id: string;
    status: "queued" | "running" | "complete" | "failed";
    model_name: string;
    detected_language: string | null;
    started_at: string | null;
    completed_at: string | null;
  }>;
  attempt_history: Array<{
    attempt_number: number;
    started_at: string;
    completed_at: string | null;
    final_stage: string | null;
    succeeded: boolean;
    error_code: string | null;
  }>;
  segment_count: number;
  chapter_count: number;
  has_summary: boolean;
}

export interface TranscriptSegment {
  id: string;
  segment_index: number;
  start_time: number;
  end_time: number;
  text: string;
  detected_language: string | null;
  confidence: number | null;
}

export interface Transcript {
  media_source_id: string;
  title: string;
  language: string | null;
  duration_seconds: number | null;
  full_text: string;
  segments: TranscriptSegment[];
  total_segments: number;
  offset: number;
  limit: number;
}

export interface VideoIntelligence {
  media_source_id: string;
  short_summary: string;
  detailed_summary: string;
  key_points: string[];
  chapters: Array<{
    chapter_index: number;
    start_time: number;
    end_time: number;
    title: string;
    summary: string;
  }>;
  action_items: Array<{
    text: string;
    owner: string | null;
    deadline: string | null;
    timestamp: number | null;
  }>;
  decisions: string[];
  entities: Array<{ name: string; category: string; mentions: number }>;
  important_quotes: string[];
  lecture_outline: string[];
  explained_concepts: string[];
  definitions: Record<string, string>;
  examples: string[];
  quiz_questions: string[];
  revision_notes: string[];
  glossary: Record<string, string>;
  important_timestamps: number[];
  meeting_summary: string;
  unresolved_issues: string[];
  language: string | null;
  output_language: "ar" | "en";
  generated_at: string;
  model_name: string;
}
