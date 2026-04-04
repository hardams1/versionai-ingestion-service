import { clearAuth, getToken } from "@/lib/auth";

const SOCIAL_URL =
  process.env.NEXT_PUBLIC_SOCIAL_GRAPH_URL ?? "http://localhost:8010";

function bearerHeaders(token?: string | null, json = false): HeadersInit {
  const t = token ?? getToken();
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

// ── Profile ──────────────────────────────────────────────────────────────

export interface SocialProfile {
  user_id: string;
  username: string | null;
  full_name: string | null;
  bio: string | null;
  image_url: string | null;
  is_private: boolean;
  ai_access_level: "public" | "followers_only" | "no_one";
  followers_count: number;
  following_count: number;
  is_following: boolean;
  is_follower: boolean;
  is_mutual: boolean;
  follow_request_pending: boolean;
}

export interface ProfileUpdate {
  username?: string;
  full_name?: string;
  bio?: string;
  image_url?: string;
  phone_number?: string;
  is_private?: boolean;
  ai_access_level?: "public" | "followers_only" | "no_one";
}

export async function fetchSocialProfile(userId: string): Promise<SocialProfile> {
  const res = await authFetch(`${SOCIAL_URL}/profile/${userId}`, {
    headers: bearerHeaders(),
  });
  if (!res.ok) throw new Error("Failed to fetch social profile");
  return res.json();
}

export async function fetchMySocialProfile(): Promise<SocialProfile> {
  const res = await authFetch(`${SOCIAL_URL}/profile/me`, {
    headers: bearerHeaders(),
  });
  if (!res.ok) throw new Error("Failed to fetch social profile");
  return res.json();
}

export async function updateSocialProfile(
  data: ProfileUpdate,
): Promise<SocialProfile> {
  const res = await authFetch(`${SOCIAL_URL}/profile/me`, {
    method: "PUT",
    headers: bearerHeaders(undefined, true),
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Failed to update social profile");
  return res.json();
}

// ── Follow ───────────────────────────────────────────────────────────────

export interface FollowResponse {
  status: string;
  message: string;
  target_user_id: string;
}

export async function followUser(
  targetUserId: string,
): Promise<FollowResponse> {
  const res = await authFetch(`${SOCIAL_URL}/follow`, {
    method: "POST",
    headers: bearerHeaders(undefined, true),
    body: JSON.stringify({ target_user_id: targetUserId }),
  });
  if (!res.ok) throw new Error("Follow failed");
  return res.json();
}

export async function unfollowUser(
  targetUserId: string,
): Promise<FollowResponse> {
  const res = await authFetch(`${SOCIAL_URL}/follow/unfollow`, {
    method: "POST",
    headers: bearerHeaders(undefined, true),
    body: JSON.stringify({ target_user_id: targetUserId }),
  });
  if (!res.ok) throw new Error("Unfollow failed");
  return res.json();
}

export interface FollowerItem {
  user_id: string;
  username: string | null;
  full_name: string | null;
  image_url: string | null;
  is_mutual: boolean;
}

export interface FollowListResponse {
  items: FollowerItem[];
  total: number;
}

export async function getFollowers(
  userId: string,
  limit = 50,
  offset = 0,
): Promise<FollowListResponse> {
  const res = await authFetch(
    `${SOCIAL_URL}/follow/followers/${userId}?limit=${limit}&offset=${offset}`,
    { headers: bearerHeaders() },
  );
  if (!res.ok) throw new Error("Failed to fetch followers");
  return res.json();
}

export async function getFollowing(
  userId: string,
  limit = 50,
  offset = 0,
): Promise<FollowListResponse> {
  const res = await authFetch(
    `${SOCIAL_URL}/follow/following/${userId}?limit=${limit}&offset=${offset}`,
    { headers: bearerHeaders() },
  );
  if (!res.ok) throw new Error("Failed to fetch following");
  return res.json();
}

// ── Requests ─────────────────────────────────────────────────────────────

export interface FollowRequestItem {
  id: string;
  requester_id: string;
  username: string | null;
  full_name: string | null;
  image_url: string | null;
  status: string;
  created_at: string;
}

export async function getPendingRequests(): Promise<{
  items: FollowRequestItem[];
  total: number;
}> {
  const res = await authFetch(`${SOCIAL_URL}/requests`, {
    headers: bearerHeaders(),
  });
  if (!res.ok) throw new Error("Failed to fetch requests");
  return res.json();
}

export async function handleFollowRequest(
  requestId: string,
  action: "accept" | "reject",
): Promise<{ status: string; message: string }> {
  const res = await authFetch(`${SOCIAL_URL}/requests/${requestId}`, {
    method: "POST",
    headers: bearerHeaders(undefined, true),
    body: JSON.stringify({ action }),
  });
  if (!res.ok) throw new Error("Failed to handle request");
  return res.json();
}

// ── Discovery ────────────────────────────────────────────────────────────

export interface SearchResult {
  user_id: string;
  username: string | null;
  full_name: string | null;
  bio: string | null;
  image_url: string | null;
  followers_count: number;
  is_private: boolean;
  ai_access_level: string;
}

export interface DiscoveryResponse {
  items: SearchResult[];
  total: number;
}

export async function searchUsers(
  query: string,
  limit = 20,
  offset = 0,
): Promise<DiscoveryResponse> {
  const res = await authFetch(
    `${SOCIAL_URL}/discover/search?q=${encodeURIComponent(query)}&limit=${limit}&offset=${offset}`,
    { headers: bearerHeaders() },
  );
  if (!res.ok) throw new Error("Search failed");
  return res.json();
}

export async function getSuggestedUsers(
  limit = 20,
): Promise<DiscoveryResponse> {
  const res = await authFetch(
    `${SOCIAL_URL}/discover/suggested?limit=${limit}`,
    { headers: bearerHeaders() },
  );
  if (!res.ok) throw new Error("Failed to fetch suggestions");
  return res.json();
}

export async function getTrendingUsers(
  limit = 20,
): Promise<DiscoveryResponse> {
  const res = await authFetch(
    `${SOCIAL_URL}/discover/trending?limit=${limit}`,
    { headers: bearerHeaders() },
  );
  if (!res.ok) throw new Error("Failed to fetch trending");
  return res.json();
}
