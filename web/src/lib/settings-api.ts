const PROFILE_URL = process.env.NEXT_PUBLIC_PROFILE_SETTINGS_URL ?? "http://localhost:8007";

function authHeaders(): HeadersInit {
  const token = typeof window !== "undefined" ? localStorage.getItem("versionai_token") : null;
  const h: HeadersInit = {};
  if (token) h["Authorization"] = `Bearer ${token}`;
  return h;
}

export interface UserProfile {
  user_id: string;
  username: string | null;
  full_name: string | null;
  email: string | null;
  bio: string | null;
  image_url: string | null;
  avatar_synced: boolean;
}

export interface UserSettings {
  user_id: string;
  output_mode: "chat" | "voice" | "video" | "immersive";
  response_length: "short" | "medium" | "long";
  creativity_level: "low" | "medium" | "high";
  notifications_enabled: boolean;
  voice_id: string | null;
  personality_intensity: "subtle" | "balanced" | "strong";
}

export interface ImageUploadResult {
  image_url: string;
  status: string;
  avatar_synced: boolean;
}

export async function fetchProfile(): Promise<UserProfile> {
  const res = await fetch(`${PROFILE_URL}/profile`, { headers: authHeaders() });
  if (!res.ok) throw new Error("Failed to fetch profile");
  return res.json();
}

export async function updateProfile(data: Partial<UserProfile>): Promise<UserProfile> {
  const res = await fetch(`${PROFILE_URL}/profile`, {
    method: "PUT",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Failed to update profile");
  return res.json();
}

export async function uploadProfileImage(file: File): Promise<ImageUploadResult> {
  const formData = new FormData();
  formData.append("image", file);
  const token = typeof window !== "undefined" ? localStorage.getItem("versionai_token") : null;

  const res = await fetch(`${PROFILE_URL}/profile/upload-image`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
    throw new Error(err.detail ?? "Image upload failed");
  }
  return res.json();
}

export async function fetchSettings(): Promise<UserSettings> {
  const res = await fetch(`${PROFILE_URL}/settings`, { headers: authHeaders() });
  if (!res.ok) throw new Error("Failed to fetch settings");
  return res.json();
}

export async function updateSettings(data: Partial<UserSettings>): Promise<UserSettings> {
  const res = await fetch(`${PROFILE_URL}/settings/update`, {
    method: "POST",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Failed to update settings");
  return res.json();
}
