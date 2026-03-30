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
