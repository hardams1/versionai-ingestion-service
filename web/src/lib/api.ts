import type {
  ApiError,
  ChatRequest,
  ChatResponse,
  HealthResponse,
  OrchestrateRequest,
  OrchestrateResponse,
  OrchestratorHealthResponse,
  UploadResponse,
  WSOutgoingMessage,
} from "./types";

const INGESTION_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const BRAIN_URL = process.env.NEXT_PUBLIC_BRAIN_API_URL ?? "http://localhost:8002";
const ORCHESTRATOR_URL = process.env.NEXT_PUBLIC_ORCHESTRATOR_URL ?? "http://localhost:8005";
const ORCHESTRATOR_WS_URL = process.env.NEXT_PUBLIC_ORCHESTRATOR_WS_URL ?? "ws://localhost:8005";
const API_KEY = process.env.NEXT_PUBLIC_API_KEY;

function headers(): HeadersInit {
  const h: HeadersInit = {};
  if (API_KEY) h["X-API-Key"] = API_KEY;
  return h;
}

function jsonHeaders(): HeadersInit {
  return { ...headers(), "Content-Type": "application/json" };
}

// ---------------------------------------------------------------------------
// Ingestion Service
// ---------------------------------------------------------------------------

export async function uploadFile(
  file: File,
  onProgress?: (percent: number) => void
): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  return new Promise<UploadResponse>((resolve, reject) => {
    const xhr = new XMLHttpRequest();

    xhr.upload.addEventListener("progress", (e) => {
      if (e.lengthComputable && onProgress) {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    });

    xhr.addEventListener("load", () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText));
      } else {
        try {
          const err: ApiError = JSON.parse(xhr.responseText);
          reject(new Error(err.detail));
        } catch {
          reject(new Error(`Upload failed with status ${xhr.status}`));
        }
      }
    });

    xhr.addEventListener("error", () =>
      reject(new Error("Network error – is the ingestion service running?"))
    );

    xhr.addEventListener("abort", () => reject(new Error("Upload cancelled")));

    xhr.open("POST", `${INGESTION_URL}/api/v1/upload/`);
    if (API_KEY) xhr.setRequestHeader("X-API-Key", API_KEY);
    xhr.send(formData);
  });
}

export async function checkHealth(): Promise<HealthResponse> {
  const res = await fetch(`${INGESTION_URL}/health`, { headers: headers() });
  if (!res.ok) throw new Error("Service unavailable");
  return res.json();
}

// ---------------------------------------------------------------------------
// Brain Service (Chat) — direct fallback
// ---------------------------------------------------------------------------

export async function checkBrainHealth(): Promise<HealthResponse> {
  const res = await fetch(`${BRAIN_URL}/health`, { headers: headers() });
  if (!res.ok) throw new Error("Brain service unavailable");
  return res.json();
}

export async function sendChatMessage(request: ChatRequest): Promise<ChatResponse> {
  const res = await fetch(`${BRAIN_URL}/api/v1/chat/`, {
    method: "POST",
    headers: jsonHeaders(),
    body: JSON.stringify(request),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
    throw new Error(err.detail ?? `Chat failed with status ${res.status}`);
  }

  return res.json();
}

// ---------------------------------------------------------------------------
// Real-Time Orchestrator (:8005)
// ---------------------------------------------------------------------------

export async function checkOrchestratorHealth(): Promise<OrchestratorHealthResponse> {
  const res = await fetch(`${ORCHESTRATOR_URL}/health`, { headers: headers() });
  if (!res.ok) throw new Error("Orchestrator unavailable");
  return res.json();
}

export async function orchestrate(request: OrchestrateRequest): Promise<OrchestrateResponse> {
  const res = await fetch(`${ORCHESTRATOR_URL}/api/v1/orchestrate`, {
    method: "POST",
    headers: jsonHeaders(),
    body: JSON.stringify(request),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
    throw new Error(err.detail ?? `Orchestration failed with status ${res.status}`);
  }

  return res.json();
}

export function createOrchestratorSocket(
  onMessage: (msg: WSOutgoingMessage) => void,
  onClose?: () => void,
  onError?: (err: Event) => void,
): WebSocket {
  const ws = new WebSocket(`${ORCHESTRATOR_WS_URL}/ws/orchestrate`);

  ws.onmessage = (event) => {
    try {
      const msg: WSOutgoingMessage = JSON.parse(event.data);
      onMessage(msg);
    } catch {
      // ignore unparseable frames
    }
  };

  ws.onclose = () => onClose?.();
  ws.onerror = (err) => onError?.(err);

  return ws;
}
