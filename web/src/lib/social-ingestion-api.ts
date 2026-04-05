import { clearAuth, getToken } from "@/lib/auth";

const SOCIAL_INGEST_URL =
  process.env.NEXT_PUBLIC_SOCIAL_INGESTION_URL ?? "http://localhost:8012";

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
    if (typeof window !== "undefined") window.location.href = "/login";
    throw new Error("Session expired");
  }
  return res;
}

export interface AccountStatus {
  platform: string;
  is_connected: boolean;
  platform_username: string | null;
  connected_at: string | null;
  last_sync_at: string | null;
  items_ingested: number;
}

export interface SyncResult {
  platform: string;
  status: string;
  items_ingested: number;
  message: string;
}

export async function fetchConnectedAccounts(): Promise<AccountStatus[]> {
  const res = await authFetch(`${SOCIAL_INGEST_URL}/connect/accounts`, {
    headers: bearerHeaders(),
  });
  if (!res.ok) throw new Error("Failed to fetch accounts");
  const data = await res.json();
  return data.accounts;
}

export async function connectPlatform(
  platform: string,
  accessToken: string,
  platformUsername?: string,
): Promise<void> {
  const res = await authFetch(`${SOCIAL_INGEST_URL}/connect/${platform}`, {
    method: "POST",
    headers: bearerHeaders(true),
    body: JSON.stringify({
      platform,
      access_token: accessToken,
      platform_username: platformUsername,
    }),
  });
  if (!res.ok) throw new Error("Failed to connect account");
}

export async function disconnectPlatform(platform: string): Promise<void> {
  const res = await authFetch(
    `${SOCIAL_INGEST_URL}/connect/disconnect/${platform}`,
    { method: "POST", headers: bearerHeaders() },
  );
  if (!res.ok) throw new Error("Failed to disconnect");
}

export async function deletePlatformData(
  platform: string,
): Promise<{ items_deleted: number }> {
  const res = await authFetch(
    `${SOCIAL_INGEST_URL}/connect/data/${platform}`,
    { method: "DELETE", headers: bearerHeaders() },
  );
  if (!res.ok) throw new Error("Failed to delete data");
  return res.json();
}

export async function syncPlatform(platform: string): Promise<SyncResult> {
  const res = await authFetch(
    `${SOCIAL_INGEST_URL}/ingest/sync/${platform}`,
    { method: "POST", headers: bearerHeaders() },
  );
  if (!res.ok) throw new Error("Sync failed");
  return res.json();
}

export async function syncAll(): Promise<void> {
  const res = await authFetch(`${SOCIAL_INGEST_URL}/ingest/sync-all`, {
    method: "POST",
    headers: bearerHeaders(),
  });
  if (!res.ok) throw new Error("Sync all failed");
}

export async function checkSocialIngestionHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${SOCIAL_INGEST_URL}/health`);
    return res.ok;
  } catch {
    return false;
  }
}
