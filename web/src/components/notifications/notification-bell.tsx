"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Bell,
  BrainCircuit,
  CheckCheck,
  HelpCircle,
  Settings,
  TrendingUp,
  Users,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/components/auth/auth-provider";
import {
  type Notification,
  type UnreadCount,
  CATEGORY_STYLES,
  connectNotificationSocket,
  fetchNotifications,
  fetchUnreadCount,
  markAllRead,
  markRead,
} from "@/lib/notification-api";

const CATEGORY_ICONS: Record<string, typeof Bell> = {
  social: Users,
  faq: HelpCircle,
  viral: TrendingUp,
  ai_evolution: BrainCircuit,
  system: Settings,
};

function timeAgo(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diff = Math.max(0, now - then);
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "now";
  if (mins < 60) return `${mins}m`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h`;
  const days = Math.floor(hrs / 24);
  return `${days}d`;
}

export function NotificationBell() {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [unread, setUnread] = useState<UnreadCount>({ total: 0, by_category: {} });
  const [loading, setLoading] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);
  const cleanupWsRef = useRef<(() => void) | null>(null);

  const loadUnread = useCallback(async () => {
    try {
      const data = await fetchUnreadCount();
      setUnread(data);
    } catch {
      // silent
    }
  }, []);

  const loadNotifications = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchNotifications(undefined, 30);
      setNotifications(data.items);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, []);

  // WebSocket connection with auto-reconnect
  useEffect(() => {
    if (!user) return;

    const cleanup = connectNotificationSocket(
      (notif) => {
        setNotifications((prev) => [notif, ...prev]);
        setUnread((prev) => ({
          total: prev.total + 1,
          by_category: {
            ...prev.by_category,
            [notif.category]: (prev.by_category[notif.category] || 0) + 1,
          },
        }));

        if (notif.priority === "critical") {
          toast(notif.title, { description: notif.message });
        }
      },
      () => loadUnread(),
    );

    cleanupWsRef.current = cleanup;
    loadUnread();

    return cleanup;
  }, [user, loadUnread]);

  // Poll unread count every 30s as fallback
  useEffect(() => {
    if (!user) return;
    const interval = setInterval(loadUnread, 30000);
    return () => clearInterval(interval);
  }, [user, loadUnread]);

  // Close panel on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    if (open) document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  const handleOpen = () => {
    setOpen(!open);
    if (!open) loadNotifications();
  };

  const handleMarkAllRead = async () => {
    await markAllRead();
    setUnread({ total: 0, by_category: {} });
    setNotifications((prev) => prev.map((n) => ({ ...n, status: "read" })));
  };

  const handleMarkRead = async (id: string) => {
    await markRead([id]);
    setNotifications((prev) =>
      prev.map((n) => (n.id === id ? { ...n, status: "read" } : n))
    );
    setUnread((prev) => ({ ...prev, total: Math.max(0, prev.total - 1) }));
  };

  if (!user) return null;

  return (
    <div className="relative" ref={panelRef}>
      {/* Bell button */}
      <button
        onClick={handleOpen}
        className="relative rounded-full p-2 text-muted-foreground hover:bg-muted transition-colors"
      >
        <Bell className="h-5 w-5" />
        {unread.total > 0 && (
          <span className="absolute -top-0.5 -right-0.5 flex h-5 min-w-5 items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-bold text-white">
            {unread.total > 99 ? "99+" : unread.total}
          </span>
        )}
      </button>

      {/* Dropdown panel */}
      {open && (
        <div className="absolute right-0 top-full mt-2 w-96 max-h-[70vh] overflow-hidden rounded-xl border bg-card shadow-xl z-50 flex flex-col">
          {/* Header */}
          <div className="flex items-center justify-between border-b px-4 py-3">
            <h3 className="text-sm font-semibold">Notifications</h3>
            <div className="flex items-center gap-1">
              {unread.total > 0 && (
                <button
                  onClick={handleMarkAllRead}
                  className="flex items-center gap-1 rounded-md px-2 py-1 text-xs text-muted-foreground hover:bg-muted transition-colors"
                >
                  <CheckCheck className="h-3 w-3" />
                  Mark all read
                </button>
              )}
              <button
                onClick={() => setOpen(false)}
                className="rounded-md p-1 text-muted-foreground hover:bg-muted"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>

          {/* Category badges */}
          {unread.total > 0 && (
            <div className="flex gap-1.5 px-4 py-2 border-b overflow-x-auto">
              {Object.entries(unread.by_category).map(([cat, count]) => {
                const style = CATEGORY_STYLES[cat] || CATEGORY_STYLES.system;
                return (
                  <span
                    key={cat}
                    className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium ${style.bgColor} ${style.color}`}
                  >
                    {style.label} {count}
                  </span>
                );
              })}
            </div>
          )}

          {/* Notification list */}
          <div className="flex-1 overflow-y-auto">
            {loading ? (
              <div className="space-y-2 p-4">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="h-16 animate-pulse rounded-lg bg-muted" />
                ))}
              </div>
            ) : notifications.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12">
                <Bell className="h-8 w-8 text-muted-foreground/30 mb-2" />
                <p className="text-xs text-muted-foreground">No notifications yet</p>
              </div>
            ) : (
              notifications.map((notif) => (
                <NotificationItem
                  key={notif.id}
                  notification={notif}
                  onRead={() => handleMarkRead(notif.id)}
                />
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function NotificationItem({
  notification: n,
  onRead,
}: {
  notification: Notification;
  onRead: () => void;
}) {
  const Icon = CATEGORY_ICONS[n.category] || Bell;
  const style = CATEGORY_STYLES[n.category] || CATEGORY_STYLES.system;
  const isUnread = n.status === "unread";
  const isAiEvolution = n.category === "ai_evolution";

  return (
    <button
      onClick={isUnread ? onRead : undefined}
      className={`flex w-full items-start gap-3 px-4 py-3 text-left transition-colors border-b last:border-0 ${
        isUnread ? "bg-primary/5 hover:bg-primary/10" : "hover:bg-muted/50"
      } ${isAiEvolution ? "border-l-2 border-l-purple-500" : ""}`}
    >
      <div
        className={`mt-0.5 shrink-0 rounded-full p-2 ${style.bgColor}`}
      >
        <Icon className={`h-4 w-4 ${style.color}`} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <p
            className={`text-sm truncate ${
              isUnread ? "font-semibold" : "font-medium"
            }`}
          >
            {n.title}
          </p>
          {isAiEvolution && (
            <span className="rounded bg-purple-100 dark:bg-purple-900/30 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider text-purple-600 dark:text-purple-400 shrink-0">
              AI Evolving
            </span>
          )}
        </div>
        <p className="mt-0.5 text-xs text-muted-foreground line-clamp-2">
          {n.message}
        </p>
        <p className="mt-1 text-[10px] text-muted-foreground/60">
          {timeAgo(n.created_at)}
          {n.priority === "critical" && (
            <span className="ml-1.5 text-red-500 font-medium">PRIORITY</span>
          )}
        </p>
      </div>
      {isUnread && (
        <div className="mt-2 h-2 w-2 shrink-0 rounded-full bg-primary" />
      )}
    </button>
  );
}
