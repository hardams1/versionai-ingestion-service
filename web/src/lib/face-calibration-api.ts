const AVATAR_SERVICE_URL =
  process.env.NEXT_PUBLIC_AVATAR_SERVICE_URL || "http://localhost:8004";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("token");
}

async function avatarFetch(path: string, init?: RequestInit): Promise<Response> {
  const token = getToken();
  const headers: Record<string, string> = {
    ...(init?.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  return fetch(`${AVATAR_SERVICE_URL}${path}`, { ...init, headers });
}

export interface CalibrationPrompt {
  instruction: string;
  duration_seconds: number;
  icon: string;
}

export interface CalibrationSequence {
  prompts: CalibrationPrompt[];
  total_duration_seconds: number;
  min_video_duration_seconds: number;
  max_video_size_mb: number;
}

export interface CalibrationStatus {
  user_id: string;
  face_scan_status: "none" | "uploading" | "processing" | "ready" | "failed";
  calibration_video_path: string | null;
  face_model_path: string | null;
  blendshape_profile_path: string | null;
  has_calibration_video: boolean;
}

export interface CalibrationUploadResult {
  user_id: string;
  video_path: string;
  face_scan_status: string;
  message: string;
}

export async function fetchCalibrationSequence(): Promise<CalibrationSequence> {
  const resp = await avatarFetch("/api/v1/calibration/sequence");
  if (!resp.ok) throw new Error("Failed to fetch calibration sequence");
  return resp.json();
}

export async function fetchCalibrationStatus(
  userId: string
): Promise<CalibrationStatus> {
  const resp = await avatarFetch(`/api/v1/calibration/${userId}/status`);
  if (!resp.ok) throw new Error("Failed to fetch calibration status");
  return resp.json();
}

export async function uploadCalibrationVideo(
  userId: string,
  videoBlob: Blob
): Promise<CalibrationUploadResult> {
  const formData = new FormData();
  const ext = videoBlob.type.includes("mp4") ? "mp4" : "webm";
  formData.append("video", videoBlob, `calibration.${ext}`);

  const resp = await avatarFetch(`/api/v1/calibration/${userId}/upload`, {
    method: "POST",
    body: formData,
  });

  if (!resp.ok) {
    const data = await resp.json().catch(() => null);
    throw new Error(data?.detail || "Failed to upload calibration video");
  }
  return resp.json();
}

export async function deleteCalibration(userId: string): Promise<void> {
  const resp = await avatarFetch(`/api/v1/calibration/${userId}`, {
    method: "DELETE",
  });
  if (!resp.ok) throw new Error("Failed to delete calibration data");
}
