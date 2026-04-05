const INGESTION_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const AVATAR_SERVICE_URL =
  process.env.NEXT_PUBLIC_AVATAR_SERVICE_URL || "http://localhost:8004";
const VOICE_TRAINING_URL =
  process.env.NEXT_PUBLIC_VOICE_TRAINING_URL || "http://localhost:8008";

const API_KEY = process.env.NEXT_PUBLIC_API_KEY;

function authHeaders(): Record<string, string> {
  const token =
    typeof window !== "undefined"
      ? localStorage.getItem("versionai_token")
      : null;
  const h: Record<string, string> = {};
  if (token) h["Authorization"] = `Bearer ${token}`;
  if (API_KEY) h["X-API-Key"] = API_KEY;
  return h;
}

// ---- Types ----

export interface ContentItem {
  ingestion_id: string;
  filename: string;
  category: string;
  size_bytes: number;
  mime_type: string;
  upload_date: string;
  s3_key: string;
  extension: string;
  has_thumbnail: boolean;
}

export interface CategorySummary {
  category: string;
  count: number;
  total_size_bytes: number;
}

export interface ContentSummaryResponse {
  categories: CategorySummary[];
  total_files: number;
  total_size_bytes: number;
}

export interface ContentListResponse {
  items: ContentItem[];
  total: number;
}

export interface TextPreview {
  ingestion_id: string;
  filename: string;
  preview_text: string;
}

export interface VoiceProfileInfo {
  user_id: string;
  total_samples: number;
  total_duration_seconds: number;
  cloning_status: string;
  voice_name: string | null;
}

export interface AvatarInfo {
  user_id: string;
  avatar_id: string;
  source_image_path: string;
  face_scan_status: string;
  has_calibration_video: boolean;
}

// ---- API calls ----

export async function fetchContentSummary(): Promise<ContentSummaryResponse> {
  const resp = await fetch(`${INGESTION_URL}/api/v1/content/summary`, {
    headers: authHeaders(),
  });
  if (!resp.ok) throw new Error("Failed to fetch content summary");
  return resp.json();
}

export async function fetchContentByCategory(
  category?: string
): Promise<ContentListResponse> {
  const qs = category ? `?category=${category}` : "";
  const resp = await fetch(`${INGESTION_URL}/api/v1/content${qs}`, {
    headers: authHeaders(),
  });
  if (!resp.ok) throw new Error("Failed to fetch content");
  return resp.json();
}

export function getThumbnailUrl(ingestionId: string): string {
  return `${INGESTION_URL}/api/v1/content/thumbnail/${ingestionId}`;
}

export function getFileUrl(ingestionId: string): string {
  return `${INGESTION_URL}/api/v1/content/file/${ingestionId}`;
}

export async function fetchTextPreview(
  ingestionId: string
): Promise<TextPreview> {
  const resp = await fetch(
    `${INGESTION_URL}/api/v1/content/preview/${ingestionId}`,
    { headers: authHeaders() }
  );
  if (!resp.ok) throw new Error("Failed to fetch preview");
  return resp.json();
}

export async function deleteContent(ingestionId: string): Promise<void> {
  const resp = await fetch(
    `${INGESTION_URL}/api/v1/content/${ingestionId}`,
    { method: "DELETE", headers: authHeaders() }
  );
  if (!resp.ok) throw new Error("Failed to delete content");
}

export async function fetchVoiceProfileInfo(): Promise<VoiceProfileInfo | null> {
  try {
    const resp = await fetch(`${VOICE_TRAINING_URL}/voice/profile`, {
      headers: authHeaders(),
    });
    if (!resp.ok) return null;
    return resp.json();
  } catch {
    return null;
  }
}

export async function fetchAvatarInfo(
  userId: string
): Promise<AvatarInfo | null> {
  try {
    const h: Record<string, string> = {};
    if (API_KEY) h["X-API-Key"] = API_KEY;
    const resp = await fetch(
      `${AVATAR_SERVICE_URL}/api/v1/avatars/${userId}`,
      { headers: h }
    );
    if (!resp.ok) return null;
    return resp.json();
  } catch {
    return null;
  }
}

export function formatFileSize(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
}

export function getAuthToken(): string | null {
  return typeof window !== "undefined"
    ? localStorage.getItem("versionai_token")
    : null;
}
