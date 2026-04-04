import { clearAuth, getToken } from "@/lib/auth";

const FEEDBACK_URL =
  process.env.NEXT_PUBLIC_FEEDBACK_URL ?? "http://localhost:8011";

function bearerHeaders(json = false): HeadersInit {
  const t = getToken();
  const h: Record<string, string> = {};
  if (json) h["Content-Type"] = "application/json";
  if (t) h["Authorization"] = `Bearer ${t}`;
  return h;
}

async function authFetch(
  input: RequestInfo | URL,
  init?: RequestInit,
): Promise<Response> {
  const res = await fetch(input, init);
  if (res.status === 401) {
    clearAuth();
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
    throw new Error("Session expired — redirecting to login");
  }
  return res;
}

export interface FaqCategoryItem {
  category: string;
  question_count: number;
  sample_questions: string[];
}

export interface FaqListResponse {
  items: FaqCategoryItem[];
  total: number;
}

export interface FaqActionResponse {
  category: string;
  action: string;
  status: string;
}

export async function fetchFaqList(): Promise<FaqListResponse> {
  const res = await authFetch(`${FEEDBACK_URL}/faq/list`, {
    headers: bearerHeaders(),
  });
  if (!res.ok) throw new Error("Failed to load FAQ data");
  return res.json();
}

export async function submitFaqAction(
  category: string,
  action: "answer" | "skip",
  answerText?: string,
): Promise<FaqActionResponse> {
  const body: Record<string, unknown> = { category, action };
  if (answerText) body.answer_text = answerText;

  const res = await authFetch(`${FEEDBACK_URL}/faq/action`, {
    method: "POST",
    headers: bearerHeaders(true),
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error("Failed to submit FAQ action");
  return res.json();
}

export async function checkFeedbackHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${FEEDBACK_URL}/health`);
    return res.ok;
  } catch {
    return false;
  }
}
