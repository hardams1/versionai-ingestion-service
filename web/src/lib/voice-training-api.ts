const VOICE_TRAINING_URL =
  process.env.NEXT_PUBLIC_VOICE_TRAINING_URL ?? "http://localhost:8008";

function authHeaders(): HeadersInit {
  const token =
    typeof window !== "undefined"
      ? localStorage.getItem("versionai_token")
      : null;
  const h: HeadersInit = {};
  if (token) h["Authorization"] = `Bearer ${token}`;
  return h;
}

export const SUPPORTED_LANGUAGES: Record<string, string> = {
  en: "English",
  es: "Spanish",
  fr: "French",
  ar: "Arabic",
  zh: "Mandarin Chinese",
  hi: "Hindi",
  pt: "Portuguese",
  bn: "Bengali",
  ru: "Russian",
  ja: "Japanese",
  yo: "Yoruba",
  pcm: "Nigerian Pidgin",
};

export interface ScriptSection {
  title: string;
  instruction: string;
  prompts: string[];
}

export interface TrainingScript {
  language: string;
  language_name: string;
  sections: ScriptSection[];
  estimated_duration_minutes: number;
}

export interface VoiceSampleResponse {
  sample_id: string;
  duration_seconds: number;
  status: string;
  message: string;
}

export interface VoiceProfile {
  user_id: string;
  elevenlabs_voice_id: string | null;
  voice_name: string | null;
  cloning_status: string;
  primary_language: string;
  preferred_languages: string[];
  total_samples: number;
  total_duration_seconds: number;
  avg_pitch_hz: number | null;
  speaking_rate_wpm: number | null;
  voice_service_synced: boolean;
}

export interface CloneVoiceResponse {
  user_id: string;
  elevenlabs_voice_id: string | null;
  cloning_status: string;
  message: string;
}

export async function fetchTrainingScript(
  language: string = "en"
): Promise<TrainingScript> {
  const res = await fetch(
    `${VOICE_TRAINING_URL}/voice/training-script?language=${language}`,
    { headers: authHeaders() }
  );
  if (!res.ok) throw new Error("Failed to fetch training script");
  return res.json();
}

export async function uploadVoiceSample(
  audioBlob: Blob,
  filename: string = "recording.webm"
): Promise<VoiceSampleResponse> {
  const formData = new FormData();
  formData.append("file", audioBlob, filename);

  const token =
    typeof window !== "undefined"
      ? localStorage.getItem("versionai_token")
      : null;

  const res = await fetch(`${VOICE_TRAINING_URL}/voice/upload-sample`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: formData,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
    throw new Error(err.detail ?? "Upload failed");
  }
  return res.json();
}

export async function cloneVoice(
  voiceName?: string
): Promise<CloneVoiceResponse> {
  const res = await fetch(`${VOICE_TRAINING_URL}/voice/clone`, {
    method: "POST",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify({ voice_name: voiceName || null }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
    throw new Error(err.detail ?? "Cloning failed");
  }
  return res.json();
}

export async function fetchVoiceProfile(): Promise<VoiceProfile> {
  const res = await fetch(`${VOICE_TRAINING_URL}/voice/profile`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error("Failed to fetch voice profile");
  return res.json();
}

export async function retrainVoice(): Promise<CloneVoiceResponse> {
  const res = await fetch(`${VOICE_TRAINING_URL}/voice/retrain`, {
    method: "POST",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
    throw new Error(err.detail ?? "Retrain failed");
  }
  return res.json();
}

export async function updateLanguagePreference(
  primaryLanguage: string,
  preferredLanguages: string[] = []
): Promise<void> {
  const res = await fetch(`${VOICE_TRAINING_URL}/voice/language`, {
    method: "PUT",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify({
      primary_language: primaryLanguage,
      preferred_languages: preferredLanguages,
    }),
  });
  if (!res.ok) throw new Error("Failed to update language");
}
