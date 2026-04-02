const AUTH_URL = process.env.NEXT_PUBLIC_AUTH_URL ?? "http://localhost:8006";
const TOKEN_KEY = "versionai_token";
const USER_KEY = "versionai_auth_user";

export interface AuthUser {
  user_id: string;
  username: string;
  onboarding_completed: boolean;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user_id: string;
  username: string;
  onboarding_completed: boolean;
}

export interface SignupResponse {
  id: string;
  username: string;
  email: string | null;
  is_active: boolean;
  onboarding_completed: boolean;
}

export interface OnboardingProfile {
  user_id: string;
  full_name: string | null;
  age: number | null;
  gender: string | null;
  location: string | null;
  personality_traits: Record<string, unknown> | null;
  communication_style: Record<string, unknown> | null;
  beliefs: Record<string, unknown> | null;
  voice_tone: Record<string, unknown> | null;
  life_experiences: string | null;
  onboarding_completed: boolean;
}

function authHeaders(): HeadersInit {
  const token = getToken();
  const h: HeadersInit = { "Content-Type": "application/json" };
  if (token) h["Authorization"] = `Bearer ${token}`;
  return h;
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function getAuthUser(): AuthUser | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function saveAuth(token: string, user: AuthUser): void {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearAuth(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  localStorage.removeItem("versionai_user_id");
  localStorage.removeItem("versionai_conversation_id");
}

export async function apiSignup(
  username: string,
  password: string,
  email?: string
): Promise<SignupResponse> {
  const res = await fetch(`${AUTH_URL}/auth/signup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password, email: email || null }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
    throw new Error(err.detail ?? "Signup failed");
  }
  return res.json();
}

export async function apiLogin(username: string, password: string): Promise<LoginResponse> {
  const res = await fetch(`${AUTH_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
    throw new Error(err.detail ?? "Login failed");
  }
  return res.json();
}

export async function apiGetMe(): Promise<AuthUser & { email: string | null }> {
  const res = await fetch(`${AUTH_URL}/auth/me`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error("Not authenticated");
  const data = await res.json();
  return {
    user_id: data.id,
    username: data.username,
    email: data.email,
    onboarding_completed: data.onboarding_completed,
  };
}

export async function apiSubmitOnboarding(data: Record<string, unknown>): Promise<OnboardingProfile> {
  const res = await fetch(`${AUTH_URL}/onboarding`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
    throw new Error(err.detail ?? "Onboarding submission failed");
  }
  return res.json();
}

export async function apiGetProfile(): Promise<OnboardingProfile> {
  const res = await fetch(`${AUTH_URL}/onboarding`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error("Failed to fetch profile");
  return res.json();
}
