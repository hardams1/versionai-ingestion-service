const NOTIFICATION_URL =
  process.env.NEXT_PUBLIC_NOTIFICATION_URL || "http://localhost:8013";
const NOTIFICATION_WS_URL =
  process.env.NEXT_PUBLIC_NOTIFICATION_WS_URL || "ws://localhost:8013";

function authHeaders(): Record<string, string> {
  const token =
    typeof window !== "undefined"
      ? localStorage.getItem("versionai_token")
      : null;
  const h: Record<string, string> = {};
  if (token) h["Authorization"] = `Bearer ${token}`;
  h["Content-Type"] = "application/json";
  return h;
}

function getToken(): string | null {
  return typeof window !== "undefined"
    ? localStorage.getItem("versionai_token")
    : null;
}

export interface Notification {
  id: string;
  user_id: string;
  type: string;
  category: string;
  title: string;
  message: string;
  priority: string;
  status: string;
  metadata: string;
  created_at: string;
}

export interface UnreadCount {
  total: number;
  by_category: Record<string, number>;
}

export interface NotificationListResponse {
  items: Notification[];
  total: number;
  limit: number;
  offset: number;
}

export async function fetchNotifications(
  status?: string,
  limit = 50,
  offset = 0
): Promise<NotificationListResponse> {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  params.set("limit", String(limit));
  params.set("offset", String(offset));
  const resp = await fetch(
    `${NOTIFICATION_URL}/api/v1/notifications?${params}`,
    { headers: authHeaders() }
  );
  if (!resp.ok) throw new Error("Failed to fetch notifications");
  return resp.json();
}

export async function fetchUnreadCount(): Promise<UnreadCount> {
  const resp = await fetch(
    `${NOTIFICATION_URL}/api/v1/notifications/unread-count`,
    { headers: authHeaders() }
  );
  if (!resp.ok) throw new Error("Failed to fetch unread count");
  return resp.json();
}

export async function markRead(ids: string[]): Promise<void> {
  await fetch(`${NOTIFICATION_URL}/api/v1/notifications/mark-read`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ notification_ids: ids }),
  });
}

export async function markAllRead(): Promise<void> {
  await fetch(`${NOTIFICATION_URL}/api/v1/notifications/mark-all-read`, {
    method: "POST",
    headers: authHeaders(),
  });
}

/**
 * Creates a self-reconnecting WebSocket connection for real-time notifications.
 * Returns a cleanup function (not the raw WebSocket).
 */
export function connectNotificationSocket(
  onNotification: (notif: Notification) => void,
  onConnect?: () => void,
  onDisconnect?: () => void
): () => void {
  const token = getToken();
  if (!token) return () => {};

  let ws: WebSocket | null = null;
  let reconnectTimer: ReturnType<typeof setTimeout> | undefined;
  let attempt = 0;
  let disposed = false;

  function connect() {
    if (disposed) return;
    try {
      ws = new WebSocket(`${NOTIFICATION_WS_URL}/ws/notifications`);
    } catch {
      scheduleReconnect();
      return;
    }

    ws.onopen = () => {
      attempt = 0;
      ws?.send(JSON.stringify({ token }));
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === "connected") onConnect?.();
        else if (msg.type === "notification") onNotification(msg.data);
      } catch {
        /* ignore malformed frames */
      }
    };

    ws.onclose = () => {
      onDisconnect?.();
      scheduleReconnect();
    };

    ws.onerror = () => {
      /* onclose will fire after onerror — reconnect handled there */
    };
  }

  function scheduleReconnect() {
    if (disposed) return;
    const delay = Math.min(2000 * 2 ** attempt, 30000);
    attempt++;
    reconnectTimer = setTimeout(connect, delay);
  }

  connect();

  return () => {
    disposed = true;
    clearTimeout(reconnectTimer);
    if (ws && ws.readyState <= WebSocket.OPEN) {
      ws.close();
    }
  };
}

export const CATEGORY_STYLES: Record<
  string,
  { label: string; color: string; bgColor: string; icon: string }
> = {
  social: {
    label: "Social",
    color: "text-blue-600",
    bgColor: "bg-blue-100 dark:bg-blue-900/30",
    icon: "users",
  },
  faq: {
    label: "FAQ",
    color: "text-amber-600",
    bgColor: "bg-amber-100 dark:bg-amber-900/30",
    icon: "help-circle",
  },
  viral: {
    label: "Viral",
    color: "text-rose-600",
    bgColor: "bg-rose-100 dark:bg-rose-900/30",
    icon: "trending-up",
  },
  ai_evolution: {
    label: "AI Evolution",
    color: "text-purple-600",
    bgColor: "bg-purple-100 dark:bg-purple-900/30",
    icon: "brain",
  },
  system: {
    label: "System",
    color: "text-gray-600",
    bgColor: "bg-gray-100 dark:bg-gray-900/30",
    icon: "settings",
  },
};
