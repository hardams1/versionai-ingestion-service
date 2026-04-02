export type FileCategory = "video" | "audio" | "text" | "pdf" | "document";

export type IngestionStatus =
  | "pending"
  | "validating"
  | "uploading"
  | "queued"
  | "processing"
  | "completed"
  | "failed";

export type ProcessingPipeline =
  | "transcription"
  | "frame_extraction"
  | "embedding"
  | "ocr";

export interface UploadResponse {
  ingestion_id: string;
  filename: string;
  file_category: FileCategory;
  size_bytes: number;
  mime_type: string;
  s3_key: string;
  status: IngestionStatus;
  pipelines: ProcessingPipeline[];
  created_at: string;
}

export interface UploadBatchResponse {
  files: UploadResponse[];
  total: number;
}

export interface HealthResponse {
  status: string;
  version: string;
  environment: string;
}

export interface ApiError {
  detail: string;
  code?: string;
}

export interface FileWithPreview extends File {
  preview?: string;
  id: string;
}

export type UploadState = "idle" | "uploading" | "success" | "error";

export interface FileUploadItem {
  id: string;
  file: File;
  state: UploadState;
  progress: number;
  response?: UploadResponse;
  error?: string;
}

// ---------------------------------------------------------------------------
// Chat (Brain Service)
// ---------------------------------------------------------------------------

export interface ChatRequest {
  user_id: string;
  query: string;
  conversation_id?: string;
  personality_id?: string;
  include_sources?: boolean;
  include_audio?: boolean;
  include_video?: boolean;
}

export interface SourceChunk {
  text: string;
  score: number;
  file_id?: string;
  chunk_index?: number;
  metadata?: Record<string, unknown>;
}

export interface ChatResponse {
  conversation_id: string;
  response: string;
  sources: SourceChunk[];
  safety_verdict: string;
  model_used: string;
  usage?: { prompt_tokens: number; completion_tokens: number; total_tokens: number };
  latency_ms: number;
  audio_base64?: string | null;
  video_base64?: string | null;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  audio_base64?: string | null;
  video_base64?: string | null;
  sources?: SourceChunk[];
  latency_ms?: number;
  model_used?: string;
  timestamp: Date;
  stage?: PipelineStage;
}

export interface ChatHistoryMessage {
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: string;
}

// ---------------------------------------------------------------------------
// Real-Time Orchestrator
// ---------------------------------------------------------------------------

export type PipelineStage =
  | "received"
  | "brain"
  | "voice"
  | "video"
  | "complete"
  | "error";

export type WSMessageType =
  | "query"
  | "ping"
  | "ack"
  | "text"
  | "audio"
  | "video"
  | "stage"
  | "complete"
  | "error"
  | "pong";

export interface WSOutgoingMessage {
  type: WSMessageType;
  request_id?: string;
  data: Record<string, unknown>;
  timestamp?: string;
}

export interface OrchestrateRequest {
  user_id: string;
  query: string;
  conversation_id?: string;
  personality_id?: string;
  include_audio?: boolean;
  include_video?: boolean;
  audio_format?: string;
  video_format?: string;
}

export interface StageResult {
  status: string;
  latency_ms: number;
  detail?: string;
}

export interface OrchestrateResponse {
  request_id: string;
  conversation_id: string;
  response_text: string;
  sources: SourceChunk[];
  audio_base64?: string | null;
  video_base64?: string | null;
  stages: Record<string, StageResult>;
  total_latency_ms: number;
}

export interface OrchestratorHealthResponse {
  status: string;
  version: string;
  environment: string;
  active_sessions: number;
  services: Record<string, { status: string; latency_ms?: number; detail?: string }>;
}
